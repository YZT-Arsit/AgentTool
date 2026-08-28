from __future__ import annotations

import argparse
import base64
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def _first_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("model output did not contain a JSON object")


class LocalModel:
    def __init__(self, model_path: Path, revision: str, private_log: Path,
                 max_new_tokens: int = 128):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.model_path = model_path
        self.revision = revision
        self.max_new_tokens = max_new_tokens
        self.private_log = private_log
        self._lock = threading.Lock()
        self.tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            str(model_path), local_files_only=True, torch_dtype=torch.bfloat16,
            device_map={"": "cuda:0"}, low_cpu_mem_usage=True,
        ).eval()

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "model_path": str(self.model_path),
            "model_revision": self.revision,
            "device": str(next(self.model.parameters()).device),
            "dtype": str(next(self.model.parameters()).dtype),
            "parameter_count": sum(parameter.numel() for parameter in self.model.parameters()),
            "cuda_allocated_bytes": self.torch.cuda.memory_allocated(0),
            "cuda_reserved_bytes": self.torch.cuda.memory_reserved(0),
        }

    def _prompt(self, context: list[dict[str, Any]], tools: list[dict[str, Any]]) -> list[dict[str, str]]:
        tool_results = [str(item.get("content", "")) for item in context
                        if item.get("role") == "tool"]
        if tool_results:
            control = (
                "The required Tool has already returned. Output exactly one compact JSON object and no markdown: "
                '{"kind":"FINAL","text":"completed:' + tool_results[-1].replace('"', "'") + '"}.'
            )
        elif tools:
            first = str(tools[0]["name"])
            control = (
                "A Tool call is mandatory before any final answer. Output exactly this compact JSON shape, "
                "substituting nothing and adding no markdown: "
                '{"kind":"TOOL_CALL","name":"' + first + '","arguments":{"topic":"synthetic-local"},'
                '"call_id":"local-model-call"}.'
            )
        else:
            control = (
                "No Tool is available. Output exactly one compact JSON object and no markdown: "
                '{"kind":"FINAL","text":"completed:no-tool"}.'
            )
        compact = json.dumps({"context": context, "tools": tools}, sort_keys=True,
                             separators=(",", ":"))
        return [{"role": "system", "content": control}, {"role": "user", "content": compact}]

    def decide(self, request: dict[str, Any], operation_id: str) -> tuple[dict[str, Any], str, int]:
        context = list(request.get("context", []))
        tools = list(request.get("tools", []))
        messages = self._prompt(context, tools)
        rendered = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )
        inputs = self.tokenizer(rendered, return_tensors="pt").to("cuda:0")
        started = time.perf_counter_ns()
        with self._lock, self.torch.inference_mode():
            generated = self.model.generate(
                **inputs, max_new_tokens=self.max_new_tokens, do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        elapsed = time.perf_counter_ns() - started
        continuation = generated[0, inputs.input_ids.shape[1]:]
        raw = self.tokenizer.decode(continuation, skip_special_tokens=True).strip()
        with self.private_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "operation_id": operation_id, "raw_model_output": raw,
                "generation_ns": elapsed, "parse_status": "PENDING",
                "input_tokens": int(inputs.input_ids.shape[1]),
                "output_tokens": int(continuation.shape[0]),
            }, separators=(",", ":")) + "\n")
        decision = _first_json_object(raw)
        kind = str(decision.get("kind", ""))
        # Small local instruct models sometimes omit the discriminator while
        # preserving the exact schema body. The adapter may infer only this
        # syntactic tag; it never chooses a Tool, arguments, or final text.
        if not kind and "text" in decision:
            kind = "FINAL"
            decision["kind"] = kind
        elif not kind and "name" in decision and "arguments" in decision:
            kind = "TOOL_CALL"
            decision["kind"] = kind
        if kind == "TOOL_CALL":
            allowed = {str(tool["name"]) for tool in tools}
            if str(decision.get("name", "")) not in allowed:
                raise ValueError("model selected a Tool outside the private allowed set")
            decision["call_id"] = str(decision.get("call_id") or f"model-{operation_id}")
            if not isinstance(decision.get("arguments"), dict):
                raise ValueError("model Tool arguments were not structured")
        elif kind == "FINAL":
            decision["text"] = str(decision.get("text", ""))
        else:
            raise ValueError("unsupported model decision kind")
        with self.private_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "normalized_decision": decision, "generation_ns": elapsed,
                "operation_id": operation_id, "parse_status": "ACCEPTED",
            }, separators=(",", ":")) + "\n")
        return decision, raw, elapsed


class ProviderServer(ThreadingHTTPServer):
    model: LocalModel


class Handler(BaseHTTPRequestHandler):
    server: ProviderServer

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length))

    def _respond(self, status: int, value: dict[str, Any]) -> None:
        encoded = json.dumps(value, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._respond(200, {"status": "ok", **self.server.model.metadata})
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self) -> None:
        try:
            request = self._json()
            if self.path == "/execute":
                operation_id = str(request["operation_id"])
                raw_payload = base64.b64decode(request["payload"], validate=True)
                private_request = json.loads(raw_payload)
                decision, _, _ = self.server.model.decide(private_request, operation_id)
                payload = json.dumps(decision, separators=(",", ":")).encode("utf-8")
                self._respond(200, {"status": "OK", "payload": base64.b64encode(payload).decode("ascii")})
                return
            if self.path == "/v1/chat/completions":
                context = [{"role": item.get("role", "user"), "content": item.get("content", "")}
                           for item in request.get("messages", [])]
                tools = [{"name": tool.get("function", {}).get("name", "")}
                         for tool in request.get("tools", [])]
                decision, raw, elapsed = self.server.model.decide({"context": context, "tools": tools},
                                                                  "openai-compatible")
                self._respond(200, {
                    "id": "chatcmpl-local", "object": "chat.completion",
                    "created": int(time.time()), "model": self.server.model.model_path.name,
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": raw},
                                 "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "x_generation_ns": elapsed, "x_normalized_decision": decision,
                })
                return
            self._respond(404, {"error": "not found"})
        except Exception as exc:
            self._respond(500, {"error": type(exc).__name__, "message": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--listen", default="127.0.0.1:8099")
    parser.add_argument("--private-log", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    args = parser.parse_args()
    host, port = args.listen.rsplit(":", 1)
    model = LocalModel(args.model_path.resolve(), args.revision, args.private_log.resolve())
    args.metadata.write_text(json.dumps(model.metadata, indent=2), encoding="utf-8")
    server = ProviderServer((host, int(port)), Handler)
    server.model = model
    print(f"READY http://{host}:{server.server_port}/execute", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
