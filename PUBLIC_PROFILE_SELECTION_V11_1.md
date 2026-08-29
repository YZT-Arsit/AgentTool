# V11.1 development profile selection

Before stress, the candidate periods were fixed to 5, 10, and 20 ms, with
identical capacity, 111 rounds, fixed message sizes, and OHTTP suite.  The rule
was to select the smallest candidate with 20/20 complete TOOL_1 development
sessions and zero scheduler misses.

The existing 5 ms profile passed 20/20.  Each session had 111 requests and
responses, one connection per HTTP/2 hop, zero pending results, zero silent
committed-result loss, and zero dummy/provider overflow events.  Therefore 5
ms was retained with a 3 ms scheduler tolerance and a separate hard rule that
an expired slot (`slip >= period`) is never submitted.  The larger candidates
were not run.  This is pre-holdout
development selection, not label-driven tuning or timing-privacy evidence.
