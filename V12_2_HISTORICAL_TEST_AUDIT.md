# V12.2 historical and portability test audit

This audit was frozen from the prior Linux repository-wide run before V12.2 Class-A execution. That run reported **157 passed, 14 failed, and 9 skipped**. The 14 failures are not called current-system PASS, but none exercises the selected V12 runtime path.

| Frozen node | Class | Frozen reason |
|---|---|---|
| `tests/test_crypto_closure.py::test_real_pir_100k_was_correct_and_fully_preprocessed` | B | absent historical `results_crypto_closure` tree |
| `tests/test_crypto_closure.py::test_server_trace_excludes_private_labels_and_uses_fresh_queries` | B | absent historical `results_crypto_closure` tree |
| `tests/test_crypto_closure.py::test_recovered_capsule_feeds_the_common_executor` | B | absent historical `results_crypto_closure` tree |
| `tests/test_crypto_closure.py::test_action_structural_and_size_results_are_at_chance` | B | absent historical `results_crypto_closure` tree |
| `tests/test_interrupted_timing_analysis.py::test_pir_aggregation_uses_only_constant_target_profiles` | B | absent historical `results_timing_closure` tree |
| `tests/test_interrupted_timing_analysis.py::test_tool_blocks_exclude_padding_slots` | B | absent historical `results_timing_closure` tree |
| `tests/test_stage9.py::Stage9AdaptiveTests::test_l2_public_runtime_existing_approval_path` | C | Windows-only historical `.venv-stage9/Scripts/python.exe` layout |
| `tests/test_timing_closure.py::test_confirmatory_profiles_were_frozen` | B | absent historical `results_timing_closure` tree |
| `tests/test_timing_closure.py::test_gateway_host_trace_has_fixed_bidirectional_frames_and_one_destination` | B | absent historical `results_timing_closure` tree |
| `tests/test_timing_closure.py::test_noop_cover_does_not_produce_heavy_work_or_effect` | B | absent historical `results_timing_closure` tree |
| `tests/test_timing_closure.py::test_real_tool_operations_complete_once_without_dummy_heavy_ops` | B | absent historical `results_timing_closure` tree |
| `tests/test_timing_closure.py::test_pir_schedule_runs_real_and_dummy_queries_through_same_server_path` | B | absent historical `results_timing_closure` tree |
| `tests/test_timing_closure.py::test_pir_correctness_and_fresh_randomness_remain_intact` | B | absent historical `results_timing_closure` tree |
| `tests/test_timing_closure.py::test_nominal_public_deadlines_do_not_depend_on_private_label` | B | absent historical `results_timing_closure` tree |

Historical provenance remains present at base commit `bdbb35b873ebf5c660b288b391abe320c3963d99`. Representative immutable hashes are:

- `CRYPTOGRAPHIC_CLOSURE_FINAL_REPORT.md`: `604554e71f6d25dbb90da3dfc833352468b42b19d9072b3d353bfdd332f5ed90`
- `MULTIROUND_PRIVACY_REPORT.md`: `4c49f3f9b4d848a7ecec5c10497341cb0bca9386486386e7d1cd728725f4bd90`
- `INTERRUPTED_RUN_RECOVERY.md`: `c69f1d06c5e93d1c6eede3130f3bd6d99bc29cea2f5e702aead44b6e1331459d`
- `TIMING_CLOSURE_FINAL_REPORT.md`: `b9f51705547de2016d06d558d4865339fd09c7f73b3ff5a8361ce128f322a0c9`
- `TIMING_ROOT_CAUSE_REPORT.md`: `bd118e07d4d44a0bd6b99ac0663233de93d2b68f94980e26405c59366136d112`
- `results_stage9/public_runtime_probe.json`: `e1f5d7b46e5875e22cc1ffdead0e1d0f1d441665a9a7764d53b442040aef0e8a`
- `V12_1_TEST_SCOPE_AUDIT.md`: `8c325fe60b20ca53ee43be695d400009ee2dcbf9cc7b529cacc838396d321469`

The nine prior skips belong to the frozen Windows-layout Stage-10 file and remain Class C. No Class-A skip is permitted in the V12.2 Linux gates.
