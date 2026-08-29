# Dynamic slot preparation V11.2

Every slot has an immutable prebuilt NOOP and fresh OHTTP context before T0. A single trusted preparation worker preserves causal arrival order. For an accepted action it selects the earliest still-future admission slot, builds bounded BHTTP, fixed padding, and a fresh OHTTP request bound to that slot.

The public preparation lead is 2 ms. At cutoff the scheduler atomically commits either the completed REAL request or the prebuilt NOOP. The committed slot cannot be changed. Candidate contexts that miss cutoff are discarded and never reused. Private preparation never changes the deadline, slot count, connection, endpoint, or wire size.
