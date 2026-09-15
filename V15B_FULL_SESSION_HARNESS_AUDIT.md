# V15B full-session harness audit

The first full-session harness invocation is preserved as an invalid
engineering attempt. It reused one stateful, one-shot framework
`ScriptedModel` instance for the three executions in `REPEATED_SAME_AGENT`.
The second invocation of that same object raised:

```
agents.testing.model.UnexpectedModelCall: Unexpected non-streaming model call #2: no scripted steps remain.
```

This occurred after successful cryptographic retrieval and was not a PSI,
SimplePIR, Gateway, artifact-authentication, public-schedule, or Agent semantic
failure. The correction reconstructs a fresh framework-native Agent from the
same authenticated artifact for each logical execution, which is the intended
AgentLoader contract. The failed output was not overwritten and remains under
the server-side directory `full_sessions_failed_scripted_model_reuse` until
the evidence is copied and checkpointed.

No privacy classifier or AUC computation was involved.
