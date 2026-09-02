# V12 Duplex Private-Acknowledgement Quiescence Erratum

The pre-execution race gate found that an asynchronous private delivery-acknowledgement goroutine could append to the private event log while `RunOnline` copied that log into evidence. No V4R5 functional identity or protected timing identity had executed.

The repair counts each acknowledgement goroutine and waits for acknowledgement quiescence after the fixed public response-release clock has completed, before constructing the private diagnostic evidence snapshot. This does not delay, reshape, or otherwise alter any public request or response release. It adds no observer field and changes no observer projection.
