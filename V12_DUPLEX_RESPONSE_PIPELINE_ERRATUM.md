# V12 Duplex Response Pipeline Erratum

Status: frozen before the third functional requalification attempt.

V4R1 used one goroutine for response commitment, fixed-size response
preparation, waiting for the public deadline, and response release. When the
public preparation lead exceeded the P10 period, that construction prevented
preparation of slot `i+1` while slot `i` was waiting for release. It also used a
25 ms lead, while two cold first-slot preparations required 34.882030 ms and
41.102944 ms.

V4R2 separates the stages into one serial public commitment lane, six fixed
bounded preparation lanes, and one serial public release lane. The public
response preparation lead is frozen at 50 ms. At the commitment cutoff the
content decision is immutable; the worker pool may only encode the already
committed response. At release, the critical path may only obtain that
fixed-size prepared frame and invoke the public write. A frame not ready at the
deadline fails closed; private preparation never moves the deadline.

This repair changes no protected statistical method and observes no protected
timing outcome. H, Delta candidates, R, M, the provider-completion bound, PIR
parameters, fixed cell sizes, and the forward effective public clock are
unchanged. All identities from the first two functional attempts remain
development exclusions.
