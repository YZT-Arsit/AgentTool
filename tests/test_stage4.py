import json
import unittest
from src.stage4 import FORBIDDEN,VARIANTS,DerivedMediator_GAAP,DerivedMediator_PAuth,IndependentEpisode

class Stage4Tests(unittest.TestCase):
    def test_gaap_functional_and_authorization_equivalence(self):
        eps=[IndependentEpisode(3,0,True),IndependentEpisode(4,1,True),IndependentEpisode(5,1,False)];outs={}
        for v in VARIANTS:
            m=DerivedMediator_GAAP(v,8);outs[v]=[m.execute(e)[0] for e in eps]
        self.assertTrue(all(outs[v]==outs[VARIANTS[0]] for v in VARIANTS));self.assertEqual(outs[VARIANTS[0]][-1]["tool_outcome"],"denied")
    def test_pauth_functional_and_authorization_equivalence(self):
        eps=[IndependentEpisode(3,0,True),IndependentEpisode(4,1,True),IndependentEpisode(5,1,False)];outs={}
        for v in VARIANTS:
            m=DerivedMediator_PAuth(v,9);outs[v]=[m.execute(e)[0] for e in eps]
        self.assertTrue(all(outs[v]==outs[VARIANTS[0]] for v in VARIANTS));self.assertEqual(outs[VARIANTS[0]][-1]["tool_outcome"],"denied")
    def test_development_provenance_not_host_visible(self):
        for cls in (DerivedMediator_GAAP,DerivedMediator_PAuth):
            m=cls("MODULAR-ORAM",2);_,host,dev,_=m.execute(IndependentEpisode(1,1));hp=json.dumps(host);dp=json.dumps(dev)
            self.assertTrue(all(x not in hp for x in FORBIDDEN));self.assertIn("source_semantic_step",dp);self.assertIn("source_architecture_component",dp)
    def test_canonical_and_unified_invariants(self):
        for cls in (DerivedMediator_GAAP,DerivedMediator_PAuth):
            for variant in ("CANONICAL-MODULAR","UNIFIED-ORAM","UNIFIED-ORAM-PAD"):
                traces=[];m=cls(variant,5)
                for h in (0,1):traces.append(m.execute(IndependentEpisode(7,h))[1])
                if variant=="CANONICAL-MODULAR":self.assertEqual([[(x["store"],x["operation"]) for x in t] for t in traces][0],[[(x["store"],x["operation"]) for x in t] for t in traces][1])
                if "UNIFIED" in variant:self.assertTrue(all(x["store"]=="UNIFIED_ORAM" for t in traces for x in t))
    def test_deterministic_regeneration_and_fair_parameters(self):
        def seq(cls,v):
            m=cls(v,77);return [[x["leaf"] for x in m.execute(IndependentEpisode(i,i%2))[1]] for i in range(10)]
        for cls in (DerivedMediator_GAAP,DerivedMediator_PAuth):
            for v in VARIANTS:self.assertEqual(seq(cls,v),seq(cls,v))
            mods=DerivedMediator_GAAP("MODULAR-ORAM",1).storage.orams if cls is DerivedMediator_GAAP else DerivedMediator_PAuth("MODULAR-ORAM",1).storage.orams
            uni=cls("UNIFIED-ORAM",1).storage.orams
            self.assertTrue(all(o.z==4 for o in list(mods.values())+list(uni.values())))

if __name__=="__main__":unittest.main()
