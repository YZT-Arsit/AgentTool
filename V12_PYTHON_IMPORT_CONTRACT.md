# V12 Python Import Contract

This append-only audit freezes the Python launch contract for the future V12 selected runtime. It does not change runtime code, timing behavior, tests, or holdout content.

The selected runtime is launched with `/root/autodl-tmp/mediation_trace_validation/.venv-linux/bin/python` from `/root/autodl-tmp/mediation_trace_validation`. The driver resolves its repository root from `scripts/run_v12_confirmatory.py` and inserts that root at the front of `sys.path` if needed. The repository is not installed as an editable package and `PYTHONPATH` is not set.

The pinned OpenAI and Microsoft framework imports are supplied by two already-existing `.pth` bindings in the frozen virtual environment. Import-only probes resolved `agents` and `agent_framework` inside their respective pinned source trees. The current runtime modules `v11a_confirmatory`, `v11_online`, and `canonical_v9_1` resolved inside the repository.

## Canonical default test entrypoint

From the frozen repository root, the canonical entrypoint is:

```text
/root/autodl-tmp/mediation_trace_validation/.venv-linux/bin/python -m pytest
```

This reproduces the selected runtime's repository-root import availability without adding `PYTHONPATH`, installing the repository, or changing production imports.

The previous `.venv-linux/bin/pytest` console entrypoint is preserved as a failed harness observation. Although it uses the same interpreter, console-script startup places the virtual-environment `bin` directory rather than the repository root at the initial import position. The resulting prior outcome remains `0/46 executed; 7 collection errors; FAIL_PRESERVED`.

No decisive test was executed while deriving this contract.
