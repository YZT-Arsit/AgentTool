
# Final V11.1 scheduler-closure audit

## Decision

`ORIGINAL_SOFTWARE_DESIGN_SCOPE_COMPLETE = YES`

The scheduler gate is closed.  Profile
qualification was 20/20,
fault injection 2/2,
reliability stress 350/350,
semantic regression 38/38,
structural regression 11/11,
and multi-action 5/5.

This decision is limited to the original software architecture and declared
development functionality.  It is not an overall privacy GO.  Timing privacy,
packet-level timing, hardware TEE validation, source-body executability, and a
fresh holdout remain separate.  No final holdout was selected or executed.

An intermediate Windows run of the pre-final candidate passed 32/33 targeted
tests but observed one `canonical response final size mismatch` in TOOL_50.
Windows was predeclared as non-decisive for scheduler stability; the event is
preserved as negative development evidence and was not reinterpreted.  The
decision above uses the fresh final-binary Linux campaign only.

## Frozen limitations

- `TIMING_PRIVACY = OPEN / NOT TESTED`.
- `PACKET_LEVEL_TIMING = OPEN`.
- `HARDWARE_TEE = NOT_TESTED`.
- `SOURCE_BODY_EXECUTABLE_SUBSET = 0`, informational rather than a scheduler
  blocker.
- Corpus action mediation remains frozen at 894 MEDIATED, 473 PARTIAL, and 3
  UNSUPPORTED.
- The public preconnect proof covers the Go transport setup. The trusted caller
  creates the PIR-selected encrypted plan before invoking that process; the Go
  runner does not inspect private action material until after setup completes.

The V11.1 harness is frozen only after these gates. It is ready for a future
independent V11A holdout freeze, but this phase selected and executed zero
holdout cases.
