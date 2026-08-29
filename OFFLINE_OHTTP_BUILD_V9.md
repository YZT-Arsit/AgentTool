# Offline OHTTP Build — V9

Status: **PASS**

The authorized Linux host used an official Go 1.26.5 archive installed under
the data directory. Its SHA-256 matched the value published by go.dev:
`5c2c3b16caefa1d968a94c1daca04a7ca301a496d9b086e17ad77bb81393f053`.

Upstream source tests ran without module-network resolution:

```text
GOTOOLCHAIN=local GOPROXY=off GONOSUMDB=* GOFLAGS=-mod=vendor go test -count=1 -v ./...
```

Result: 18 passed, one skipped (`TestVectorVerify`: vectors not supplied), exit
status zero. V8 and V9 integration packages then ran in offline GOPATH mode so
that the upstream module's supplied `vendor/` tree resolved its dependencies.
V8: 4/4 tests passed. V9 adapter/integration: 11 top-level tests passed,
including seven admission-mismatch subtests.

Raw output: `results_v9/linux_offline_validation.txt`.
