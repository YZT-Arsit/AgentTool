from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from action_privacy_v6.descriptor import AgentDescriptorV6, DescriptorCodec, PlacementClass
from action_privacy_v6.models import ActionKind, ProtectedActionIntent
from action_privacy_v6.trusted_module import LocalTrustedBackend
from cryptographic_closure.pir_backend import PIRRequest, run_simplepir
from privacy_kernel.protocol import ACTION_TOOL, CanonicalProfile, EnvelopeCodec


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results_v6" / "pir_to_gateway_smoke"


def main() -> None:
    if OUT.exists() and any(OUT.iterdir()):
        raise FileExistsError(f"refusing to overwrite {OUT}")
    OUT.mkdir(parents=True)
    count, selected, epoch = 1000, 42, 6
    descriptor_key, gateway_key = os.urandom(32), os.urandom(32)
    codec = DescriptorCodec(descriptor_key, epoch)
    registry = OUT / "encrypted_registry.bin"
    with registry.open("xb") as handle:
        for index in range(count):
            handle.write(codec.encode(AgentDescriptorV6(
                index, (f"cap-{index}",), "publisher", 1, PlacementClass.EXTERNAL,
                f"opaque-route-{index}", "OpenAI Agents SDK", ("lookup",), "SIGNED", epoch)))
    pir = run_simplepir(ROOT, registry, count, [PIRRequest("e2e", 0, selected, "REAL")], OUT / "simplepir")
    trusted = LocalTrustedBackend({f"cap-{selected}": selected}, descriptor_key, gateway_key, epoch)
    recovered = trusted.recover_descriptor(pir.recovered[0], selected)
    intent = ProtectedActionIntent(f"cap-{selected}", b'{"input":"synthetic"}', "session", "op-e2e-v6", ActionKind.TOOL)
    action_cell = trusted.make_action_cell(intent, recovered, public_profile="STRICT", public_slot=1)
    opened = trusted.open_action_cell(action_cell, public_profile="STRICT", public_slot=1)
    public = CanonicalProfile("V6-E2E-SMOKE", 1024, 3, 1, 10_000_000, 10_000_000,
                              2_000_000, 50_000_000, 5_000_000)
    envelope = EnvelopeCodec(gateway_key, public).encode_request(
        0, 1, action=ACTION_TOOL, provider=1, operation_id=opened.operation_id,
        payload=opened.protected_arguments)
    serialized = envelope.lower()
    forbidden_present = any(value in serialized for value in
                            (b"cap-42", b"opaque-route-42", b"synthetic", b"op-e2e-v6"))
    result = {
        "real_simplepir": True, "simplepir_correct": recovered.agent_id == selected,
        "simplepir_commit": pir.metrics["commit"], "descriptor_encrypted": True,
        "descriptor_fed_to_trusted_module": True, "action_cell_bytes": len(action_cell),
        "gateway_frame_bytes": len(envelope), "gateway_frame_secret_plaintext_visible": forbidden_present,
        "common_gateway_destination": "CommonActionGatewayV2",
        "live_gateway_process_execution": "NOT_COMPLETED_ENVIRONMENT_WINERROR_4551",
        "hardware_tee": "NOT_TESTED", "canonical_ir_dependency": "NONE",
        "public_frame_sha256": hashlib.sha256(envelope).hexdigest(),
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
