# Stage-6 Deployment Trade-off

Deployment coupling is intentionally qualitative; it is not collapsed into a
fabricated score.

| Requirement | Fixed canonical modular | Unified ORAM | HYBRID-P | HYBRID-PH |
| --- | --- | --- | --- | --- |
| Merge existing databases | No | **Yes** | No | No |
| Change service ownership | No | Usually yes/centralize | No | No |
| Common record layout | No | **Yes** | No | No |
| ORAM/backend change | Each service | Unified service | Data/history | Data only for point access |
| Policy copy on employee device | No | No | **Yes** | **Yes** |
| Global audit copy on device | No | No | No | **Yes** |
| Per-action freshness RPC | Normal policy read | Included in batch | **Yes, validation** | **Yes, validation** |
| Per-action history synchronization | Normal point read | Included in batch | Normal point read | **Yes, delta sync** |
| Cache invalidation channel | No | No | Validation substitutes for push | Validation/sync substitutes for push |
| Cache recovery/persistence work | No | No | Permission cache can be rebuilt | Permission/history caches must be rebuilt |

## Observed consequences

- HYBRID-PH minimizes steady-state wire (229 KiB/action in MEDIUM) but its
  device cache and sync traffic grow with unseen global events. At 1,000 unseen
  history entries it transfers 560 KiB/action and caches 286,464 B; at 128 new
  devices the aggregate mediator cache reaches 2,279,808 B.
- HYBRID-P avoids global-history cache growth while retaining the small
  validated policy cache. It is the robust choice under frequent cross-device
  audit updates in this prototype.
- Fixed canonical preserves separate service ownership and has no employee-side
  authoritative-state cache. It is a meaningful deployment-specific point even
  though HYBRID-P uses fewer bytes in the measured steady state.
- Unified reduces service requests from five to three but moves larger common
  ORAM paths: 604 KiB/action versus 293 KiB for fixed modular in MEDIUM. It also
  requires the strongest organizational/data-layout coupling.

## Decision rule

Choose HYBRID-PH for bounded, low-churn histories where a trusted cache and
rebuild protocol are acceptable. Choose HYBRID-P when audit state is large or
shared updates are frequent. Choose fixed canonical when preserving existing
authoritative service ownership and avoiding client policy/audit caches is a
hard deployment constraint. Unified is not preferred by these measurements,
but remains a design option where consolidation is already acceptable and
network request count matters more than transferred path bytes.

