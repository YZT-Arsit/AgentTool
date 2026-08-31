# V12 non-timing official-sample compatibility

The existing frozen static matrix is preserved: nine workloads, 85 classified behaviors, **53 supported by current mediation, 28 shared-primitive-only, 4 unsupported, 0 outside claim**.

A fresh source-availability check on the authorized Linux instance found 8/9 declared source paths. Those available rows reproduce 81 behaviors as 51/26/4/0. The pinned Microsoft `tests/agents/test_agent.py` path is absent from this execution bundle, so the fresh whole-matrix audit is **PARTIAL_SOURCE_UNAVAILABLE**; the file was not downloaded, regenerated, or substituted. No sample was executed and no framework revision changed.
