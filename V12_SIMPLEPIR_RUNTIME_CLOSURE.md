# V12 SimplePIR runtime dependency closure

The V11B failure was a launcher defect: `OnlineSimplePIRResolver.__enter__`
checked for `go` and `gcc` before selecting the already-frozen prebuilt bridge.
The compilers are build-time dependencies for this Linux artifact, not runtime
dependencies.

The V12 path selects `acv-simplepir-online` first and invokes that exact binary.
Linux fails closed if it is absent; selected execution cannot fall back to
`go run`. Windows retains an explicitly development-only source path. The live
Linux development probe used a PATH containing neither Go nor GCC, verified the
bridge SHA-256, recovered authenticated descriptor 17 correctly, exited with
FD count 4 -> 4, and executed no selected V12 manifest.

The frozen bridge remains
`2ceacc5f772c908dfdd696cfdaf35e60ed6477f70d8a4367868ba0f0cfa0305b`.
Linux `ldd` reports only the system C library, ELF loader, and virtual DSO;
neither Go nor GCC is a dynamic runtime dependency.
