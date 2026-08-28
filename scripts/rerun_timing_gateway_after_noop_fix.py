from pathlib import Path

from timing_closure.gateway import run_native_gateway
from timing_closure.runner import (
    LONG_IO_PROFILE,
    PRIMARY_IO_PROFILE,
    VERY_SLOW_PROFILE,
    latency_matrix_episodes,
    single_action_episodes,
    tool_sequence_episodes,
)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    results = root / "results_timing_closure"
    run_native_gateway(root, PRIMARY_IO_PROFILE, single_action_episodes(1001, 8), results / "development_single")
    run_native_gateway(root, VERY_SLOW_PROFILE, latency_matrix_episodes(1002, 3), results / "development_latency_matrix")
    run_native_gateway(root, LONG_IO_PROFILE, tool_sequence_episodes(1003, 6), results / "development_tool_sequences")
    # New untouched seeds: the earlier confirmatory Gateway artifacts are retained but invalidated.
    run_native_gateway(root, PRIMARY_IO_PROFILE, single_action_episodes(19001, 8), results / "confirmatory_final_single")
    run_native_gateway(root, LONG_IO_PROFILE, tool_sequence_episodes(19003, 6), results / "confirmatory_final_tool_sequences")
