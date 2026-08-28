# Action-mediation corpus audit V6

The audit preserves the identical frozen 314-file, 7,386-behavior-instance
corpus. It changes the question from whole-program compilation to outbound
action-boundary interception.

| Disposition | Instances |
|---|---:|
| MEDIATED | 894 |
| PARTIAL | 473 |
| UNSUPPORTED | 3 |
| NOT_ACTION_RELEVANT | 6,016 |

There are 1,370 action-relevant instances. Fully mediated coverage is
**894/1,370 = 65.26%**. MEDIATED-or-PARTIAL reach is 1,367/1,370 = 99.78%, but
that second number is not a PASS rate: all 473 MCP-boundary instances remain
PARTIAL because only post-materialization function actions have a demonstrated
seam. Three OpenAI conditional handoff callbacks are unsupported.

Framework distribution among action-relevant instances:

- Microsoft: 654 MEDIATED, 413 PARTIAL;
- OpenAI: 240 MEDIATED, 60 PARTIAL, 3 UNSUPPORTED.

This is static, source-traceable evidence. It does not establish runtime
semantic preservation by itself. The historical 48.39% IR metric remains
unchanged and measures a different property.
