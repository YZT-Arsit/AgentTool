# Admission Runtime Binding — V9

`ADMISSION_BINDING_IMPLEMENTATION = PASS`

`ADMISSION_BINDING_RUNTIME = PASS`

Linux runtime tests accepted one fully matching public/admission profile and
failed closed when independently changing sessions, slots/session, response
slot interval, maximum operations, terminal slots, provider-completion bound,
or public lifetime. The test runs the frozen V8 binding implementation from the
V9 package; V8 source was not modified.

