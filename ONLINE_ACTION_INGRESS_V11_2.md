# Online action ingress V11.2

The bounded ingress channel accepts at most 50 unique resolved operations. The framework adapter calls `session.submit(intent)` only when pinned framework machinery reaches that action. Arrival order and operation IDs are retained in private lifecycle evidence. The startup plan contains zero actions and the pre-T0 action queue count is zero.

Late or excess actions receive explicit private `PROFILE_ADMISSION_CLOSED` or `PROFILE_CAPACITY_EXCEEDED` outcomes. They do not extend the schedule or start a replacement session.
