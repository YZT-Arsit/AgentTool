#!/usr/bin/env bash
set -euo pipefail

repo=/root/autodl-tmp/mediation_trace_validation
go_root=/root/autodl-tmp/go1.26.5
gopath=/root/autodl-tmp/v9-gopath

"${go_root}/bin/go" version
uname -srmo

cd "${repo}/third_party/ohttp-go"
GOTOOLCHAIN=local GOPROXY=off GONOSUMDB='*' GOFLAGS=-mod=vendor \
  "${go_root}/bin/go" test -count=1 -v ./...

cd "${gopath}/src/common-action-gateway-v2/v8"
GO111MODULE=off GOPATH="${gopath}" GOPROXY=off GONOSUMDB='*' \
  "${go_root}/bin/go" test -count=1 -v

cd "${gopath}/src/common-action-gateway-v2/v9ohttp"
GO111MODULE=off GOPATH="${gopath}" GOPROXY=off GONOSUMDB='*' \
  "${go_root}/bin/go" test -count=1 -v
