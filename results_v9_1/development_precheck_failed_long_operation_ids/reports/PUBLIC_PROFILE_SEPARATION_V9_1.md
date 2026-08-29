
# V9.1 Public-profile Separation

V9 is frozen by `V9_CANONICAL_FUNCTIONAL_FREEZE.json`. V9.1 does not edit its
runner or evidence. It replaces the privacy-use orchestration call
`capacity_profile(len(actions), ...)` with a preselected
`PublicCapacityProfile` passed separately from private actions.

The development profile is `V9_1-STRICT-H50-P1`: capacity
50, 111 rounds, one public
session, 1079-byte final OHTTP requests and
800-byte responses. The runner admitted and
functionally completed 1, 5, 10, 25, and 50 real actions under this exact one
profile. Unused admission slots were encrypted NOOP and unused response slots
were encrypted WAIT. No holdout was selected or executed.
