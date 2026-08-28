import unittest
from src.stage4 import IndependentEpisode
from src.stage5 import ARCHS,BASE_REC,PRIVACY,REGIMES,RandomizedPartitionORAM,Stage5Mediator,architecture_cost

class Stage5Tests(unittest.TestCase):
    def test_partition_correctness_and_remapping(self):
        p=RandomizedPartitionORAM(128,4,8);seen=[]
        for i in range(100):
            prior,t=p.access(7,"write",f"v{i}");seen.append(p.mapping[7][0]);p.assert_invariants()
        self.assertGreater(len(set(seen)),1);self.assertEqual(p.access(7)[0],"v99")
    def test_partition_determinism(self):
        def run():
            p=RandomizedPartitionORAM(64,8,4);return [[x["store"] for x in p.access(i%7)[1]] for i in range(20)]
        self.assertEqual(run(),run())
    def test_partition_abstraction_is_not_treated_as_privacy_valid(self):
        self.assertEqual(PRIVACY["RANDOMIZED-PARTITION"],"not_implemented")
    def test_all_architectures_functionally_equivalent(self):
        eps=[IndependentEpisode(2,0,True),IndependentEpisode(3,1,True),IndependentEpisode(4,1,False)];outs={}
        for a in ARCHS:
            m=Stage5Mediator(a,11);outs[a]=[m.execute(e)[0] for e in eps]
        self.assertTrue(all(outs[a]==outs[ARCHS[0]] for a in ARCHS));self.assertEqual(outs[ARCHS[0]][-1]["tool_outcome"],"denied")
    def test_naive_and_canonical_cost_identical(self):
        self.assertEqual(architecture_cost("NAIVE-FIXED",REGIMES["M"],BASE_REC),architecture_cost("CANONICAL-MODULAR",REGIMES["M"],BASE_REC))
    def test_fair_unified_capacity_and_block_rules(self):
        c=architecture_cost("UNIFIED-FIXED",REGIMES["M"],BASE_REC);self.assertGreater(c["tree_storage_bytes"],0);self.assertEqual(BASE_REC["data"],4096)

if __name__=="__main__":unittest.main()
