# V11.4 aborted prequalification harness run

This evidence is preserved but is not a period-qualification result. Before any candidate reached its predeclared 500-session gate, the initial launcher suffered two independent experiment-harness failures: the SSH-controlled foreground process ended after 174 complete sessions, and a resumed process exhausted its file-descriptor limit after 277 complete session directories. The latter exposed missing explicit closure of `subprocess.PIPE` objects in the Python orchestration layer.

No completed or partial session was retried, and no period was selected from this run. The raw evidence remains on the authorized Linux host under `results_v11_4_aborted_prequalification`. The repair closes every SimplePIR and online-runner pipe after process completion. The official qualification uses a new empty result directory and new operation-ID namespace while retaining the exact candidate set, order, 500-session rule, public profile fields, and attacker-independent engineering gates.

Classification: `ABORTED_PREQUALIFICATION_HARNESS_FAILURE`; analyses from this run must not be cited as period qualification.
