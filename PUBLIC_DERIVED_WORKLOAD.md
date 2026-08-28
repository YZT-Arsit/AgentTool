# Public-derived paired mediation workload

The workload contains 40 distinct public semantic tasks in [PUBLIC_DERIVED_WORKLOAD.csv](PUBLIC_DERIVED_WORKLOAD.csv): 20 tau2-bench retail tasks and 20 AgentDojo workspace/Slack tasks. Sources are pinned to:

- tau2-bench, `a2c024725189473d2d7cea3a5cfdbcc67478e41f`, `https://github.com/sierra-research/tau2-bench`;
- AgentDojo, `089ed468cf3ed0322acc66b0211f26d9d90dbf60`, `https://github.com/ethz-spylab/agentdojo`.

Selection retained tasks with an explicit mutating reference action. The public prompt, effect type, reference arguments, and reference-action count come from the pinned source. The experiment does not market this as a benchmark.

Each task has four configurations: present/absent authorization and present/absent provenance-history. Paired runs keep the public task, intended effect, success result, and effect count fixed. Approval is native to both public runtimes. Provenance-history reconstruction is existing project mediator behavior over a task's reference-action prefix; it is not claimed as native upstream middleware, which is an external-validity limitation.

ToolPrivacyBench was inspected at `51d13355a8cb78d80c45b756dd347e94c40327e6`. Its repository states that code, data, and evaluation scripts are not yet released, so it was not used to invent extra tasks.

