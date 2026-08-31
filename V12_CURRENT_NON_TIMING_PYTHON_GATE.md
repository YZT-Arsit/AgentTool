# Current non-timing Python gates

The reachability-corrected 46-node manifest ran once serially through the frozen Python interpreter and passed **46/46**, with zero failures and zero skips. The two canonical cadence routing nodes were excluded by the pre-frozen timing classification.

The subsequent default-mode console entrypoint failed before collection: **0/46 executed, seven collection errors**. `.venv-linux/bin/pytest` did not place the repository root on `sys.path`, so each selected module import failed. The command was not replaced or rerun after observation. Consequently the required default gate is FAIL even though the serial current-runtime tests are green.
