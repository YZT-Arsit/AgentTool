# Unified private registry

STRICT stores internal and external service descriptors in one encrypted
SimplePIR database. The trusted capability map yields an ID; one query retrieves
the descriptor. The server cannot distinguish internal/external row class under
the stated PIR assumptions and cannot decrypt either row class.

The 100K experiment contains both placement classes and passed recovery. It
costs the full 100K query even for common internal Agents: approximately 52.240
ms online and 73,568 bytes per measured five-query-run accounting row. This is
the cleanest selection claim and the default STRICT choice.
