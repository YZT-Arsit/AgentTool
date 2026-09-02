# V12 V4R7 residual timing source attribution freeze

This is a post-outcome development diagnostic. It creates no new session, changes no runtime, and has no privacy-pass authority.

The immutable 640-session V4R7 smoke dataset and its existing selected 30 TRAIN / 30 EVAL matched blocks are reused exactly. The focus comparisons are T7/Microsoft/Relay and T9/OpenAI/Relay; T7/OpenAI/Relay and T9/Microsoft/Relay are negative controls.

The ten predeclared feature families are exact slices of the frozen strengthened Relay vector. A/B/C/D each retain that boundary's slot-indexed relative timeline, chronological inter-arrival gaps, and existing twelve summaries. AB/BC/CD retain the existing paired latency sequence and summaries. REQUEST_SIDE is A+B+AB; RESPONSE_SIDE is C+D+CD; ALL is the exact original 5,860-dimensional vector. Only ALL contains the original global total-session-span element because it is not attributable to one boundary.

The four-model family, grouped five-fold TRAIN-only selection, TRAIN-only orientation, selected blocks, and 10,000 complete-EVAL-block bootstrap are unchanged. No feature, slot, window, lag, model, hyperparameter, identity, or seed search is allowed.

Deadline misses, public slots, and release slips are private development diagnostics only and never enter an attacker feature vector. Slot-level class medians use the selected EVAL blocks and cannot be used to select a classifier input.
