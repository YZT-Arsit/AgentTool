# OpenAI handoff V11

The native reference uses the pinned SDK's actual `agents.handoff` object, reaches one `HandoffOutputItem`, and ends with the target as `last_agent`. The canonical implementation maps target activation to private `AGENT_SERVICE/HANDOFF`, uses the accepted transport path, and returns the target result through handoff machinery without directly executing a remote target in the parent process. Projection equality passed.
