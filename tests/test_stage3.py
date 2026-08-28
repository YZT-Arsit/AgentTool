import json
import unittest
from src.stage3 import ARCHS,FORBIDDEN,Episode,RealAction,ReferenceTrustedAgentMediator,SMALL,execute_episode,matched_episodes

class Stage3Tests(unittest.TestCase):
    def test_functional_and_authorization_equivalence(self):
        episodes=matched_episodes(20,3)+[Episode(RealAction(16,1,2,1),True)]
        outputs={}
        for a in ARCHS:
            m=ReferenceTrustedAgentMediator(a,44,SMALL);outputs[a]=[execute_episode(m,e)[0] for e in episodes]
        self.assertTrue(all(outputs[a]==outputs[ARCHS[0]] for a in ARCHS))
        self.assertFalse(outputs[ARCHS[0]][-1]["authorized"]);self.assertEqual(outputs[ARCHS[0]][-1]["tool_outcome"]["status"],"denied")

    def test_unified_observability_and_private_separation(self):
        m=ReferenceTrustedAgentMediator("V2-UNIFIED",5,SMALL);_,trace,_=execute_episode(m,matched_episodes(1,2)[0])
        self.assertTrue(all(x["store"]=="UNIFIED_ORAM" for x in trace))
        payload=json.dumps(trace);self.assertTrue(all(f not in payload for f in FORBIDDEN))
        self.assertNotIn("OBJECT_STORE",payload);self.assertNotIn("CONTACT",payload)

    def test_canonical_trace_invariants_and_dummy_schema(self):
        eps=[Episode(RealAction(0,1,None,None),False),Episode(RealAction(1,2,3,2),True)]
        m=ReferenceTrustedAgentMediator("MODULAR-V3",7,SMALL);traces=[execute_episode(m,e)[1] for e in eps]
        shapes=[[(x["store"],x["operation"]) for x in t] for t in traces]
        self.assertEqual(shapes[0],shapes[1]);self.assertEqual(len(traces[0]),11)
        self.assertTrue(all("is_dummy" not in x and "logical_id" not in x and "block_id" not in x for t in traces for x in t))

    def test_matched_state_machine_control(self):
        eps=matched_episodes(30,8);m=ReferenceTrustedAgentMediator("MODULAR-V2",2,SMALL);by={}
        for e in eps:
            _,t,_=execute_episode(m,e);by[e.action.recipient%2]=t
        a,b=by[0],by[1]
        self.assertEqual(len(a),len(b));self.assertEqual(sorted(x["store"] for x in a),sorted(x["store"] for x in b));self.assertEqual(sorted(x["operation"] for x in a),sorted(x["operation"] for x in b));self.assertNotEqual([x["store"] for x in a],[x["store"] for x in b])

if __name__=="__main__":unittest.main()
