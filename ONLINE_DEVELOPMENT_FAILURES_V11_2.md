# V11.2 online development failures

This file preserves negative development evidence. It is not holdout evidence.

Campaign B was stopped after 354 of 380 planned sessions. Seventeen
`DYNAMIC_10_ACTION` sessions failed: fifteen native OpenAI workflows completed
9/10 actions and two completed 8/10. The Go public session itself retained 111
slots with no catch-up; the unresolved final private action reached the ingress
after the fixed H50 admission window and was explicitly rejected as
`PROFILE_ADMISSION_CLOSED`.

The observed slot progression showed that the original fixed 10-period
pre-start lead let the first action reach approximately slot 4, leaving
insufficient room for ten sequential, causally dependent framework actions.
The remediation was a public and secret-independent setup change: freeze the
pre-start lead at 20 periods. The 111-slot schedule, 50 admission slots, 5 ms
period, 1079/800-byte wire sizes, endpoints, and 555 ms scheduled lifetime were
not changed. A clean Campaign C is required; no Campaign B success row may be
reused as accepted evidence.

Machine-readable evidence is preserved under
`results_v11_2_development/linux_campaign_b_negative/`. The complete raw
session evidence remains on the authorized Linux host.

Campaign C used a fixed 20-period pre-start lead and was stopped after 344
sessions. Five `DYNAMIC_10_ACTION` sessions completed only 9/10 native actions,
even though the first action reached slot 1. Its machine-readable summary is
preserved under `results_v11_2_development/linux_campaign_c_negative/`.

The final development configuration used a fixed 50-period pre-start lead and
a 1 ms public preparation cutoff. A pre-freeze check passed 17/20 ten-action
sessions; three still ended with `PROFILE_ADMISSION_CLOSED` before the tenth
causal action. The clean required Campaign D subsequently passed 380/380,
including its predeclared 20/20 ten-action stratum, but it does not erase the
same-configuration 17/20 result. This reproducible negative evidence blocks the
V11.2 reliability gate and therefore blocks the execution-harness freeze.
