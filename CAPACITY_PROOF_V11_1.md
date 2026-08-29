# V11.1 delivery-capacity proof

The public profile fixes 50 admission slots, at most 50 real operations, 111
total slots, a 5 ms period, a declared 50 ms provider-completion bound, and one
terminal slot.  At most one operation is admitted per admission slot and at
most one result is carried per response slot.

Worst case, an operation admitted in slot 50 becomes eligible no later than 10
periods after its admission.  The profile has 61 response opportunities after
slot 50 (slots 51 through 111), enough to drain all 50 bounded admitted results
even if all become eligible together at the bound.  The durable and in-memory
result queues are each provisioned for `maximum_real_operations + 1`.

Multiplexing does not reduce response capacity: every configured request still
receives one fixed-size response opportunity, independently of other streams.
Any provider completion outside the declared bound, schedule miss, or
undelivered committed result produces an explicit non-`COMPLETE` status rather
than secret-dependent extension.
