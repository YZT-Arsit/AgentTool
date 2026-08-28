# Hierarchical private resolution

The efficient design checks the resident trusted capability index and chooses
an internal or external registry. It explicitly leaks
`INTERNAL_EXTERNAL_ROUTE_CLASS`; V6 never calls it equivalent to STRICT.

`RESOLUTION_PARETO_V6.csv` combines measured 10K internal and 100K external
SimplePIR components over predeclared hit probabilities. It is a component
model, not an additional live deployment. Latency and bandwidth fall toward
the 10K cost as hit rate rises, while the route bit is always exposed.

No PSI is used because the exact internal capability catalog is resident in the
trusted module. Outsourced private membership remains future work.
