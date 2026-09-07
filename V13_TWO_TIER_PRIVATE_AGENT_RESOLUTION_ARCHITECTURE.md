# Two-tier Private Agent Resolution Architecture

## Components

- **Protected Runtime** receives a planner-selected set of canonical Agent IDs.
- **Private Agent Availability Resolution** pads the candidate set to K=8 and
  invokes one PSI slot against the split-domain **Enterprise Agent Directory**.
- The **Enterprise Agent Directory** is modeled as a private inventory padded
  to the public E=1024 profile bucket. It stores canonical Agent ID, private
  enterprise-cloud execution handle, descriptor, and optional digest/version.
- The existing **Agent Library** remains separate and is accessed through one
  existing PIR slot.
- The **Trusted Gateway** is the sole handoff interface for both an
  enterprise-deployed Agent and a global-library Agent.

## Fixed public resolution profile

Every logical Agent-resolution opportunity has exactly one PSI slot and one
PIR slot. The candidate side uses the public K=8 size class; the enterprise
side uses the public padded E=1024 class.

- Enterprise-local hit: the PSI slot carries the padded candidate batch and
  the PIR slot retrieves the existing reserved padding row.
- Library fallback: the same PSI slot is executed and the PIR slot retrieves
  the selected global Agent descriptor.

The public structural projection contains only the profile ID, K/E size
classes, one PSI slot, one PIR slot, and the unchanged Gateway/Registry public
counts. It excludes candidate IDs, matches, branch bit, PIR real/padding
choice, descriptor, and execution handle.

## Implementation boundary

`v13_private_resolution` implements the profile, interfaces, orchestration,
existing SimplePIR adapter, and deterministic functional doubles. No vetted
cryptographic PSI library exists in the repository or active environment, so
the split-domain backend is **not cryptographically instantiated**. The mock
backend exposes raw values internally and is prohibited from deployment or
use as privacy evidence.

If the complete Enterprise Agent Directory resides within the same trusted
runtime, PSI is not required for that deployment mode; a private local
membership lookup is sufficient. The PSI-facing design applies to a
split-domain enterprise directory.

The existing fixed Gateway and Registry profiles remain unchanged: R=521 and
Q=100. The PSI control exchange is a logically separate Agent-resolution
profile and is not inserted into the existing Gateway transcript in this
phase.
