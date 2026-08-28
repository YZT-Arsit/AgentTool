from __future__ import annotations

import csv
import json
import random
import shutil
from pathlib import Path

from agent_control_virtualization.ir import AgentCapsule, CAPSULE_BYTES
from agent_control_virtualization.runtime import AgentControlExecutor
from cryptographic_closure.pir_backend import PIRRequest, run_simplepir
from timing_closure.gateway import ActionSpec, EpisodeSpec, PublicProfile, latency_for, run_native_gateway


PRIMARY_IO_PROFILE = PublicProfile("STANDARD", slots=24, delta_ms=50.0, response_lag_ms=25.0)
LONG_IO_PROFILE = PublicProfile("LONG_SEQUENCE", slots=200, delta_ms=10.0, response_lag_ms=5.0)
VERY_SLOW_PROFILE = PublicProfile("VERY_SLOW_VALIDATION", slots=64, delta_ms=50.0, response_lag_ms=25.0)
PIR_DELTA_MS = 5.0
PIR_SLOTS = 100
FRAME_BYTES = 1024


def _tokens(seed: int):
    rng = random.Random(seed)
    while True:
        yield rng.getrandbits(63) | 1


def single_action_episodes(seed: int, repetitions: int) -> list[EpisodeSpec]:
    rng = random.Random(seed)
    tokens = _tokens(seed + 91)
    episodes: list[EpisodeSpec] = []
    for label in ("AGENT", "LLM", "TOOL", "NOOP"):
        for _ in range(repetitions):
            if label == "LLM": provider = "MEDIUM"
            elif label == "TOOL": provider = "SLOW"
            else: provider = "NONE"
            episodes.append(EpisodeSpec(next(tokens), "ACTION_TYPE", label,
                                        (ActionSpec(label, provider, latency_for(provider, rng)),)))
    for label, provider in (("LOCAL", "FAST"), ("REMOTE", "MEDIUM"), ("CLOUD", "SLOW")):
        for _ in range(repetitions):
            episodes.append(EpisodeSpec(next(tokens), "TOOL_CLASS", label,
                                        (ActionSpec("TOOL", provider, latency_for(provider, rng)),)))
    rng.shuffle(episodes)
    return episodes


def latency_matrix_episodes(seed: int, repetitions: int = 3) -> list[EpisodeSpec]:
    rng = random.Random(seed); tokens = _tokens(seed + 7); episodes = []
    for provider in ("FAST", "MEDIUM", "SLOW", "VERY_SLOW", "JITTERED"):
        for _ in range(repetitions):
            episodes.append(EpisodeSpec(next(tokens), "LATENCY_MATRIX", provider,
                                        (ActionSpec("TOOL", provider, latency_for(provider, rng)),)))
    rng.shuffle(episodes)
    return episodes


def tool_sequence_episodes(seed: int, repetitions: int) -> list[EpisodeSpec]:
    rng = random.Random(seed); tokens = _tokens(seed + 13); episodes = []
    tool = {
        "LOCAL": lambda: ActionSpec("TOOL", "FAST", latency_for("FAST", rng)),
        "REMOTE": lambda: ActionSpec("TOOL", "MEDIUM", latency_for("MEDIUM", rng)),
        "CLOUD": lambda: ActionSpec("TOOL", "SLOW", latency_for("SLOW", rng)),
    }
    for repetition in range(repetitions):
        sequences: dict[str, list[str]] = {
            "TSEQ0": ["LOCAL"] * 100,
            "TSEQ1": ["REMOTE"] * 100,
            "TSEQ2": ["REMOTE"] * 50 + ["LOCAL"] * 50,
            "TSEQ3": (["LOCAL", "REMOTE", "CLOUD"] * 34)[:100],
            "TSEQ4": (["REMOTE", "LOCAL", "CLOUD"] * 34)[:100],
        }
        sequences["TSEQ1"][rng.randrange(100)] = "LOCAL"
        rng.shuffle(sequences["TSEQ2"])
        for label, names in sequences.items():
            episodes.append(EpisodeSpec(next(tokens), "TOOL_SEQUENCE", label,
                                        tuple(tool[name]() for name in names)))
    rng.shuffle(episodes)
    return episodes


def make_dummy_registry(source: Path, target: Path, real_records: int = 1000, dummy_records: int = 64) -> None:
    raw = source.read_bytes()
    if len(raw) != real_records * CAPSULE_BYTES:
        raise AssertionError("unexpected source registry shape")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw + b"\0" * (dummy_records * CAPSULE_BYTES))


def pir_requests(seed: int, episodes_per_profile: int = 4) -> list[PIRRequest]:
    rng = random.Random(seed); episodes: list[list[PIRRequest]] = []
    dummy = list(range(1000, 1064))
    for profile in range(8):
        for episode_number in range(episodes_per_profile):
            name = f"M{profile}-E{episode_number:02d}-{seed}"
            if profile == 0: sequence = [17] * PIR_SLOTS
            elif profile == 1:
                sequence = [17] * PIR_SLOTS; sequence[rng.randrange(PIR_SLOTS)] = 23
            elif profile == 2:
                sequence = [17] * 50 + [23] * 50; rng.shuffle(sequence)
            elif profile == 3: sequence = [100 + rng.randrange(10) for _ in range(PIR_SLOTS)]
            elif profile == 4: sequence = [10 if i % 2 == 0 else 11 for i in range(PIR_SLOTS)]
            elif profile == 5: sequence = [10 if i % 2 == 0 else 12 for i in range(PIR_SLOTS)]
            elif profile == 6: sequence = [30 + episode_number % 4] * PIR_SLOTS
            else: sequence = [17 if i % 3 else 23 for i in range(PIR_SLOTS)]
            episodes.append([PIRRequest(name, slot, index, f"M{profile}:REAL")
                             for slot, index in enumerate(sequence)])
    for occupancy, real_count in (("PIR_REAL_100", 100), ("PIR_REAL_50", 50), ("PIR_REAL_1", 1)):
        for episode_number in range(episodes_per_profile):
            name = f"{occupancy}-E{episode_number:02d}-{seed}"
            real_positions = set(rng.sample(range(PIR_SLOTS), real_count))
            sequence = [17 if slot in real_positions else rng.choice(dummy) for slot in range(PIR_SLOTS)]
            episodes.append([PIRRequest(name, slot, index, occupancy + (":REAL" if slot in real_positions else ":DUMMY"))
                             for slot, index in enumerate(sequence)])
    rng.shuffle(episodes)
    return [request for episode in episodes for request in episode]


def run_pir_split(root: Path, split: str, seed: int, output: Path, episodes_per_profile: int = 4) -> None:
    registry = output.parent / "registry_1000_plus_64_dummy.bin"
    if not registry.exists():
        make_dummy_registry(root / "results_crypto_closure/smoke/registry.bin", registry)
    requests = pir_requests(seed, episodes_per_profile)
    artifacts = run_simplepir(root, registry, 1064, requests, output,
                              paced_delta_ms=PIR_DELTA_MS, paced_start_delay_ms=20.0)
    real = 0; dummy = 0
    for request, recovered in zip(requests, artifacts.recovered):
        if request.index < 1000:
            capsule = AgentCapsule.deserialize(recovered)
            AgentControlExecutor({capsule.logical_agent_id: capsule}).fixed_transcript(capsule.logical_agent_id)
            real += 1
        else:
            if recovered != b"\0" * CAPSULE_BYTES: raise AssertionError("dummy PIR row was not recovered")
            dummy += 1
    (output / "timing_profile.json").write_text(json.dumps({
        "split": split, "R_pir": PIR_SLOTS, "Delta_pir_ms": PIR_DELTA_MS,
        "real_queries": real, "dummy_queries": dummy, "dummy_rows": [1000, 1063],
        "backend": artifacts.metrics["backend"],
    }, indent=2), encoding="utf-8")


def run_cross_session(root: Path, output: Path, seed: int, sessions: int = 8) -> None:
    registry = output.parent / "registry_1000_plus_64_dummy.bin"
    rng = random.Random(seed); rows = []
    for session in range(sessions):
        target = (17, 101, 102, 17)[session % 4]
        name = f"S{session:02d}"
        requests = [PIRRequest(name, slot, target, "CROSS_SESSION") for slot in range(PIR_SLOTS)]
        folder = output / name
        run_simplepir(root, registry, 1064, requests, folder,
                      paced_delta_ms=PIR_DELTA_MS, paced_start_delay_ms=20.0)
        rows.append({"session": name, "private_target": target, "public_order": rng.randrange(1 << 30)})
    with (output / "private_session_ground_truth.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def run_all(root: Path, results: Path) -> None:
    results.mkdir(parents=True, exist_ok=True)
    profiles = {
        "STANDARD": PRIMARY_IO_PROFILE.__dict__, "LONG_SEQUENCE": LONG_IO_PROFILE.__dict__,
        "VERY_SLOW_VALIDATION": VERY_SLOW_PROFILE.__dict__,
        "PIR": {"R_pir": PIR_SLOTS, "Delta_pir_ms": PIR_DELTA_MS},
    }
    (results / "frozen_public_profiles.json").write_text(json.dumps(profiles, indent=2), encoding="utf-8")
    run_native_gateway(root, PRIMARY_IO_PROFILE, single_action_episodes(1001, 8), results / "development_single")
    run_native_gateway(root, VERY_SLOW_PROFILE, latency_matrix_episodes(1002, 3), results / "development_latency_matrix")
    run_native_gateway(root, LONG_IO_PROFILE, tool_sequence_episodes(1003, 6), results / "development_tool_sequences")
    run_pir_split(root, "DEVELOPMENT", 1004, results / "development_pir", episodes_per_profile=6)

    # The code/profile constants above are frozen before these independent seeds are run.
    run_native_gateway(root, PRIMARY_IO_PROFILE, single_action_episodes(9001, 8), results / "confirmatory_single")
    run_native_gateway(root, LONG_IO_PROFILE, tool_sequence_episodes(9003, 6), results / "confirmatory_tool_sequences")
    run_pir_split(root, "CONFIRMATORY", 9004, results / "confirmatory_pir", episodes_per_profile=6)
    run_cross_session(root, results / "confirmatory_cross_session", 9005, sessions=8)
    shutil.copyfile(results / "frozen_public_profiles.json", results / "confirmatory_frozen_configuration.json")
