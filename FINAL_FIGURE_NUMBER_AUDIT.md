# Final figure number audit

Every figure reads `FINAL_PAPER_PLOT_DATA.csv`; each row below was copied mechanically from the listed machine-readable source row.

| Figure / panel | Plotted metric | Source file / row | Value | CI or p95 | Status |
|---|---|---|---:|---:|---|
| FIG2 / a_access_linking | Same-Agent (AUC) | `V15E_ACCESS_PRIVACY_RESULTS.csv` / `SAME_AGENT_WITHIN_SESSION|ALL` | 0.486525 | [0.446, 0.526] | ESTABLISHED |
| FIG2 / a_access_linking | Cross-session
same (AUC) | `V15E_ACCESS_PRIVACY_RESULTS.csv` / `CROSS_SESSION_SAME_SLOT|ALL` | 0.518796 | [0.490, 0.547] | ESTABLISHED |
| FIG2 / a_access_linking | Cross-session
cross (AUC) | `V15E_ACCESS_PRIVACY_RESULTS.csv` / `CROSS_SESSION_CROSS_SLOT|ALL` | 0.472096 | [0.444, 0.501] | ESTABLISHED |
| FIG2 / a_access_linking | Rare
insertion (AUC) | `V15E_SEQUENCE_RESULTS.csv` / `RARE_INSERTION_AAA_VS_AAB|ALL` | 0.5246 | [0.467, 0.582] | ESTABLISHED |
| FIG2 / a_access_linking | Recurrence (AUC) | `V15E_SEQUENCE_RESULTS.csv` / `RECURRENCE_AAA_VS_ABC|ALL` | 0.46345 | [0.407, 0.521] | ESTABLISHED |
| FIG2 / a_access_linking | Return
pattern (AUC) | `V15E_SEQUENCE_RESULTS.csv` / `RETURN_PATTERN_ABA_VS_ABC|ALL` | 0.55125 | [0.495, 0.608] | NOT_ESTABLISHED |
| FIG2 / b_sequence_structure | Access
OAE (Accuracy) | `V15E_SEQUENCE_RESULTS.csv` / `FOUR_CLASS_ORDERING_RECURRENCE|ALL` | 0.25625 | [0.226, 0.286] | EMPIRICALLY_SUPPORTED |
| FIG2 / b_sequence_structure | Access
control (Accuracy) | `V15E_SEQUENCE_RESULTS.csv` / `FOUR_CLASS_ORDERING_RECURRENCE|UNPROTECTED_VISIBLE_AGENT_ID_POSITIVE_CONTROL` | 1 | [1.000, 1.000] | EMPIRICALLY_SUPPORTED |
| FIG2 / b_sequence_structure | Trajectory
OAE (Accuracy) | `FINAL_SEQUENCE_RESULTS.csv` / `FOUR_CLASS_EXECUTION_TRAJECTORY|FINAL_OAE_STRUCTURAL_COMPOSITION` | 0.2125 | [0.150, 0.275] | EMPIRICALLY_SUPPORTED |
| FIG2 / b_sequence_structure | Trajectory
control (Accuracy) | `FINAL_SEQUENCE_RESULTS.csv` / `FOUR_CLASS_EXECUTION_TRAJECTORY|UNNORMALIZED_VISIBLE_ACTION_ENDPOINT_POSITIVE_CONTROL` | 1 | [1.000, 1.000] | EMPIRICALLY_SUPPORTED |
| FIG2 / c_realized_timing | Branch
timing (Accuracy) | `FINAL_PRIVACY_RESULTS.csv` / `PROVISIONED_UNPROVISIONED_IDLE|TIMING` | 0.663333 | [0.610, 0.717] | NOT_ESTABLISHED |
| FIG2 / c_realized_timing | Tool/Agent
OAI|OAE (AUC) | `FINAL_TIMING_RESULTS.csv` / `TOOL_VS_AGENT_AS_TOOL|OpenAI Agents SDK|FINAL_OAE_BIDIRECTIONAL_SHAPING` | 0.6225 | [0.440, 0.787] | NOT_ESTABLISHED |
| FIG2 / c_realized_timing | Tool/Agent
OAI|One-sided control (AUC) | `FINAL_TIMING_RESULTS.csv` / `TOOL_VS_AGENT_AS_TOOL|OpenAI Agents SDK|HISTORICAL_ONE_SIDED_POSITIVE_CONTROL` | 0.980764 | [0.968, 0.991] | POSITIVE_CONTROL |
| FIG2 / c_realized_timing | Tool/Agent
MAF|OAE (AUC) | `FINAL_TIMING_RESULTS.csv` / `TOOL_VS_AGENT_AS_TOOL|Microsoft Agent Framework|FINAL_OAE_BIDIRECTIONAL_SHAPING` | 0.645 | [0.465, 0.818] | NOT_ESTABLISHED |
| FIG2 / c_realized_timing | Tool/Agent
MAF|One-sided control (AUC) | `FINAL_TIMING_RESULTS.csv` / `TOOL_VS_AGENT_AS_TOOL|Microsoft Agent Framework|HISTORICAL_ONE_SIDED_POSITIVE_CONTROL` | 0.969306 | [0.947, 0.988] | POSITIVE_CONTROL |
| FIG2 / c_realized_timing | Provider
OAI|OAE (AUC) | `FINAL_TIMING_RESULTS.csv` / `PROVIDER_READINESS|OpenAI Agents SDK|FINAL_OAE_BIDIRECTIONAL_SHAPING` | 0.4425 | [0.253, 0.630] | NOT_ESTABLISHED |
| FIG2 / c_realized_timing | Provider
OAI|One-sided control (AUC) | `FINAL_TIMING_RESULTS.csv` / `PROVIDER_READINESS|OpenAI Agents SDK|HISTORICAL_ONE_SIDED_POSITIVE_CONTROL` | 0.977986 | [0.958, 0.993] | POSITIVE_CONTROL |
| FIG2 / c_realized_timing | Provider
MAF|OAE (AUC) | `FINAL_TIMING_RESULTS.csv` / `PROVIDER_READINESS|Microsoft Agent Framework|FINAL_OAE_BIDIRECTIONAL_SHAPING` | 0.55625 | [0.366, 0.739] | NOT_ESTABLISHED |
| FIG2 / c_realized_timing | Provider
MAF|One-sided control (AUC) | `FINAL_TIMING_RESULTS.csv` / `PROVIDER_READINESS|Microsoft Agent Framework|HISTORICAL_ONE_SIDED_POSITIVE_CONTROL` | 0.990278 | [0.981, 0.997] | POSITIVE_CONTROL |
| SCALE / online_latency | 1000 (PSI) | `FINAL_SCALE_RESULTS.csv` / `N=1000|PSI` | 41.4959 | p95=45.060 | ESTABLISHED |
| SCALE / online_latency | 1000 (PIR) | `FINAL_SCALE_RESULTS.csv` / `N=1000|PIR` | 2.17058 | p95=3.349 | ESTABLISHED |
| SCALE / online_latency | 1000 (Combined) | `FINAL_SCALE_RESULTS.csv` / `N=1000|Combined` | 41.5443 | p95=45.106 | ESTABLISHED |
| SCALE / online_latency | 10000 (PSI) | `FINAL_SCALE_RESULTS.csv` / `N=10000|PSI` | 51.5139 | p95=60.665 | ESTABLISHED |
| SCALE / online_latency | 10000 (PIR) | `FINAL_SCALE_RESULTS.csv` / `N=10000|PIR` | 10.2252 | p95=16.701 | ESTABLISHED |
| SCALE / online_latency | 10000 (Combined) | `FINAL_SCALE_RESULTS.csv` / `N=10000|Combined` | 51.5715 | p95=60.734 | ESTABLISHED |
| SCALE / online_latency | 50000 (PSI) | `FINAL_SCALE_RESULTS.csv` / `N=50000|PSI` | 48.3693 | p95=51.001 | ESTABLISHED |
| SCALE / online_latency | 50000 (PIR) | `FINAL_SCALE_RESULTS.csv` / `N=50000|PIR` | 31.5982 | p95=32.040 | ESTABLISHED |
| SCALE / online_latency | 50000 (Combined) | `FINAL_SCALE_RESULTS.csv` / `N=50000|Combined` | 48.4239 | p95=51.052 | ESTABLISHED |
| SCALE / online_latency | 100000 (PSI) | `FINAL_SCALE_RESULTS.csv` / `N=100000|PSI` | 50.5606 | p95=58.811 | ESTABLISHED |
| SCALE / online_latency | 100000 (PIR) | `FINAL_SCALE_RESULTS.csv` / `N=100000|PIR` | 56.9372 | p95=61.575 | ESTABLISHED |
| SCALE / online_latency | 100000 (Combined) | `FINAL_SCALE_RESULTS.csv` / `N=100000|Combined` | 57.1729 | p95=61.818 | ESTABLISHED |
| TRAFFIC / base_profile | APSI (MiB) | `FINAL_OVERHEAD_RESULTS.csv` / `APSI_bytes_per_profile|AGENT_ACCESS` | 8.68924 |  | ESTABLISHED |
| TRAFFIC / base_profile | SimplePIR (MiB) | `FINAL_OVERHEAD_RESULTS.csv` / `SimplePIR_bytes_per_profile|AGENT_ACCESS` | 0.28064 |  | ESTABLISHED |
| TRAFFIC / base_profile | Gateway (MiB) | `FINAL_OVERHEAD_RESULTS.csv` / `bytes_per_profile|GATEWAY` | 0.933608 |  | ESTABLISHED |
