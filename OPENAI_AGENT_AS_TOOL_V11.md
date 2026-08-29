# OpenAI Agent-as-Tool V11

The native development reference instantiates a child `Agent` and uses its actual `Agent.as_tool()` mechanism. The canonical implementation intercepts at the child Agent boundary, maps to private `AGENT_SERVICE/AGENT_AS_TOOL`, performs real SimplePIR and the accepted BHTTP/OHTTP/Relay/Gateway path, and returns the result through the parent framework Tool-result machinery. Runtime evidence confirms one child invocation and no direct remote child execution on the canonical path. Native/canonical projection equality passed.
