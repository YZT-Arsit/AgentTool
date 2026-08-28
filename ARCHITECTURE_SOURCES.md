# Architecture Sources

Stage 4 uses only the primary papers below. The local code is an architecture-
derived abstraction, not a reproduction of either system.

## System A: GAAP

- **Paper:** Robert Stanley, Avi Verma, Lillian Tsai, Konstantinos Kallas, and
  Sam Kumar, *An AI Agent Execution Environment to Safeguard User Data*.
- **Version/date:** arXiv:2604.19657v1, 21 April 2026.
- **Public sources:** [abstract/metadata](https://arxiv.org/abs/2604.19657),
  [paper PDF](https://arxiv.org/pdf/2604.19657).
- **Architecture elements used:** code artifacts access private values through a
  private-data key/value database; disclosures query a permission database; a
  persistent disclosure log records disclosures and is queried to reconstruct
  transitive/indirect taints across calls and tasks; the runtime intercepts MCP
  calls and applies IFC before external disclosure.
- **Source locations used:** §§3.3.2–3.3.4 and §§4.2–4.5. The paper explicitly
  calls each of the private-data DB, permission DB, and disclosure log a database.

## System B: PAuth

- **Paper:** Reshabh K Sharma, Linxi Jiang, Shuo Chen, and Zhiqiang Lin,
  *Beyond OAuth: Task-Scoped Authorization for AI Agents via Natural Language
  Slices*.
- **Version/date:** arXiv:2603.17170v2, 25 August 2026. The v1/title surfaced in
  some indexes as *PAuth – Precise Task-Scoped Authorization For Agents*.
- **Public sources:** [abstract/metadata](https://arxiv.org/abs/2603.17170),
  [paper PDF](https://arxiv.org/pdf/2603.17170).
- **Architecture elements used:** each server derives an NL slice specifying its
  expected call; server-returned values use signed envelopes binding values to
  symbolic provenance; a receiving server verifies concrete operands and their
  provenance against its slice; inconsistent operations escalate to the user.
- **Source locations used:** §§I and III-B–III-D, especially the protocol flow,
  NL-slice derivation, and enveloped-value execution.

## Selection rationale

GAAP is a plaintext-confinement/IFC environment with three explicitly persistent
state components. PAuth is an authorization/provenance design whose envelopes
travel inline between independently verifying servers. This diversity is useful:
GAAP can test the modular persistent-store claim directly; PAuth tests whether
the project would incorrectly manufacture the same channel in an architecture
that does not document heterogeneous persistent mediator state.

No web content, repository, or external API was accessed by the executable
simulators. Web access was used only for this source audit.
