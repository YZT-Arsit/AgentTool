# Structural generator validation V11

The validator mechanically constructs a `ProtectedActionIntent`, obtains the authenticated canonical descriptor, invokes the frozen trusted resolver, and compares manifest effect semantics with the resolved route. `tool.a/READ_ONLY` and `tool.b/IDEMPOTENT_EFFECT` pass; the old `tool.b/READ_ONLY` design fails closed. No selected structural holdout was loaded or executed.
