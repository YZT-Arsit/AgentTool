
# V11.1 Linux reliability stress

All rows are non-holdout development repetitions on the qualified Linux host.
The accepted campaign used Linux binary `17e1a497788ac6261348a2dff728b83188661ad9b4117bd5272b1d9575a22c56` and the
5 ms / 111-slot development profile.

| Gate | Passed |
|---|---:|
| DIRECT_AGENT_SERVICE | 20/20 |
| EARLY_VS_LATE_READY | 20/20 |
| EXTERNAL_HTTP | 20/20 |
| INTERNAL_VS_EXTERNAL_STRICT | 20/20 |
| MICROSOFT_AGENT_AS_TOOL | 20/20 |
| OPENAI_AGENT_AS_TOOL | 20/20 |
| OPENAI_HANDOFF | 20/20 |
| STRUCTURED_MULTI_ARGUMENT_TOOL | 20/20 |
| TOOL_1 | 100/100 |
| TOOL_10 | 50/50 |
| TOOL_50 | 20/20 |
| TRUSTED_MODULE_LOCAL_AGENT | 20/20 |

The three core Tool gates are 100/100,
50/50, and
20/20.  The remaining full-scope
gate repetitions are 180/180 (220 underlying sessions
because the two paired gates execute two sessions per repetition).

Accepted-session totals: dummy heavy operations 0; profile overflow
0; scheduler misses 0; silent committed-result losses 0.

Result: **PASS**.  Timing privacy remains open.
