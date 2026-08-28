from pathlib import Path

import numpy as np

from timing_closure.interrupted_analysis import (
    _gateway_blocks,
    pir_repeated_observation_pairs,
)


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results_timing_closure"


def test_pir_aggregation_uses_only_constant_target_profiles() -> None:
    for count in (10, 50, 100):
        X, y, groups = pir_repeated_observation_pairs(RESULTS / "confirmatory_pir", count)
        assert X.shape[0] == y.shape[0] == groups.shape[0]
        assert set(np.unique(y)) == {0, 1}
        assert X.shape[1] == 2 * count + 8


def test_tool_blocks_exclude_padding_slots() -> None:
    for count, blocks_per_episode in ((10, 10), (50, 2), (100, 1)):
        X, y, groups = _gateway_blocks(RESULTS / "confirmatory_final_tool_sequences", count)
        assert len(X) == 30 * blocks_per_episode
        assert len(set(groups)) == 30
        assert set(y) == {"TSEQ0", "TSEQ1", "TSEQ2", "TSEQ3", "TSEQ4"}

