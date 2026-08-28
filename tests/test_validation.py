import json
import unittest

from src.simulator import Action, FORBIDDEN, compile_schema, make_actions, mediate

class ValidationTests(unittest.TestCase):
    def test_all_mediation_variants_are_functionally_equivalent(self):
        for i,a in enumerate(make_actions(200,7)):
            outputs=[mediate(a,v,i).concrete_args for v in ("V0","V1","V2","V3")]
            self.assertTrue(all(x==outputs[0] for x in outputs))

    def test_host_trace_has_no_forbidden_private_fields(self):
        for i,a in enumerate(make_actions(100,8)):
            for v in ("V0","V1","V2","V3"):
                payload=json.dumps(mediate(a,v,i).host_visible_trace)
                self.assertTrue(all(field not in payload for field in FORBIDDEN))
                self.assertNotIn("person",payload); self.assertNotIn("synthetic_account",payload)

    def test_v3_canonical_trace_invariants(self):
        traces=[mediate(a,"V3",i).host_visible_trace for i,a in enumerate(make_actions(200,9))]
        shapes=[[(e["store"],e["operation"]) for e in t] for t in traces]
        self.assertTrue(all(len(t)==len(compile_schema("SEND_MESSAGE")) for t in traces))
        self.assertTrue(all(s==shapes[0] for s in shapes))
        self.assertTrue(all("is_dummy" not in e and "record_token" not in e for t in traces for e in t))

    def test_oram_path_well_formed(self):
        a=make_actions(1,1)[0]
        for v in ("V2","V3"):
            for e in mediate(a,v,42).host_visible_trace:
                self.assertEqual(e["path_length"],6); self.assertEqual(len(e["path"]),6)

if __name__ == "__main__": unittest.main()
