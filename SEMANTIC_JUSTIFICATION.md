# Stage-3 Semantic Justification

The Reference Trusted Agent Mediator executes every access below as part of its
state machine. Trace events are emitted only by the storage backend; there is no
label-to-trace generator.

| State access | Why needed | Hidden dependency | Visibility |
|---|---|---|---|
| Recipient object | Materialize a confined opaque contact handle and learn its authorization requirements | Recipient handle and private recipient metadata | Private; modular endpoint only is visible |
| Recipient policy | Authorize disclosure to the resolved contact | Recipient-specific permission | Private; modular policy endpoint visible |
| Content object | Materialize confined message text | Content handle | Private; modular object endpoint visible |
| Attachment object | Materialize a document only when attached | Optional attachment handle | Private; modular object endpoint visible |
| Attachment policy | Authorize release of the resolved document | Attachment presence and document policy | Private; modular policy endpoint visible |
| Sender object | Materialize default or explicitly selected sender binding | Private account selection | Private; modular object endpoint visible |
| Purpose policy | Enforce tool/purpose-scoped authorization | Private authorization record | Private; modular policy endpoint visible |
| Sender policy | Authorize use of the selected sender identity | Private account binding | Private; modular policy endpoint visible |
| Credential | Obtain the credential profile needed by the mock mail transport | Default or explicit account binding | Private; modular credential endpoint visible |
| Disclosure history | Enforce recipient-specific repeat-disclosure tracking when enabled | Private history-sensitive policy state | Private; modular history endpoint visible |
| Audit write | Record every completed authorization decision | Successful or denied mediation attempt | Private payload; modular history endpoint and write operation visible |

## Natural ordering dependency

The recipient record contains private `preflight_required` metadata. A preflight
recipient requires its disclosure policy to be checked immediately after contact
resolution, before other private objects are materialized. A batch-safe recipient
permits the mediator to gather the remaining objects first and then run the same
policy checks. Both modes access the same records in the matched workload; their
different order follows the authorization dependency returned by the first real
object lookup.

The balanced matched dataset selects equal numbers of recipients with each
metadata value. The mediator never receives or tests an experimental class label.
The label used offline is derived only after execution from the private recipient
metadata rule.

## Scenarios

| Scenario | Object | Policy | Credential | History | Semantic reason |
|---|---:|---:|---:|---:|---|
| S0 minimal text | 3 | 3 | 1 | 1 write | Recipient/content/sender resolution, authorization, transport credential, audit |
| S1 attachment | 4 | 4 | 1 | 1 write | Adds document materialization and independent disclosure policy |
| S2 explicit account | 3 | 3 | 1 | 1 write | Selects different sender/credential records without adding a redundant stage |
| S3 attachment + explicit account | 4 | 4 | 1 | 1 write | Combines document policy with explicit account binding |
| S4 history-sensitive | corresponding S0–S3 counts | corresponding | 1 | 1 read + 1 write | Prior-disclosure enforcement plus mandatory audit |

Default accounts still require credential retrieval, so explicit account choice
changes the private logical record but not the number of mediation stages. This
avoids manufacturing a count difference merely to make account choice visible.
