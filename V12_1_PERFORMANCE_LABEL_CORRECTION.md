# V12.1 performance terminology correction

This append-only correction changes no numerical result. `B4_PIR_PLUS_FIXED_TRANSCRIPT_EXTERNAL` was 150/150 functional; `B5_FULL_STRICT` was 146/150 functional; together they were 296/300. The historical JSON field `full_strict_successful_sessions=296` was semantically mislabelled: it denotes the combined fixed-transcript population, not B5 alone.
