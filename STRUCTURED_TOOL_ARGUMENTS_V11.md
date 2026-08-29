# Structured Tool arguments V11

One generic schema-driven adapter was exercised through both pinned frameworks for: one string, integer, boolean, optional string, two primitives, three primitives, and one bounded object `{label:string,count:int,enabled:bool}`. The adapter creates the callable mechanically before execution and validates exact keys/types. Results: 14/14 native-vs-canonical schema rows passed.

This is bounded development support, not arbitrary Python signature or source-body support. Oversize private payloads fail closed under the frozen public bucket.
