import unittest
from src.path_oram import PathORAM
from src.stage2 import CANONICAL,ORAMMediator,matched_episodes,structural_schedule

class PathORAMTests(unittest.TestCase):
    def test_logical_reads_writes_and_invariants(self):
        o=PathORAM(64,1,4,6); expected={i:f"initial_{i}" for i in range(64)}
        for i in range(300):
            bid=(i*17)%64
            if i%3==0: expected[bid]=f"written_{i}";o.access(bid,"write",expected[bid])
            else: self.assertEqual(o.access(bid,"read")[0],expected[bid])
            o.assert_invariants()
        self.assertEqual(len(o.all_real_ids()),64)

    def test_determinism_and_random_remapping(self):
        def seq(seed):
            o=PathORAM(32,seed,4,5);return [o.access(7)[1]["leaf"] for _ in range(20)]
        self.assertEqual(seq(12),seq(12));self.assertNotEqual(seq(12),seq(13));self.assertGreater(len(set(seq(12))),1)

    def test_stage2_functional_equivalence_and_canonical_shape(self):
        eps=matched_episodes(100,5); outputs={}
        shapes=[];v3_events=[]
        for v in ("V2","V2-PAD","V2-HIST","V3"):
            m=ORAMMediator(90)
            outputs[v]=[]
            for e in eps:
                out,t,_=m.execute(e,v);outputs[v].append(out)
                if v=="V3":
                    shapes.append([(x["store"],x["operation"]) for x in t]);v3_events.extend(t)
        self.assertTrue(all(outputs[v]==outputs["V2"] for v in outputs))
        expected=[(s,o) for s,_,o in CANONICAL]
        self.assertTrue(all(x==expected for x in shapes))
        self.assertTrue(all("is_dummy" not in event and "block_id" not in event and "logical_id" not in event for event in v3_events))

    def test_matched_control_really_matches_histograms(self):
        eps=matched_episodes(20,2); schedules={c:structural_schedule(next(e for e in eps if e.structural_class==c)) for c in (0,1)}
        for c in (0,1):
            self.assertEqual(len(schedules[c]),9)
        self.assertEqual(sorted(s for s,_,_ in schedules[0]),sorted(s for s,_,_ in schedules[1]))
        self.assertEqual(sorted(o for _,_,o in schedules[0]),sorted(o for _,_,o in schedules[1]))
        self.assertNotEqual([(s,o) for s,_,o in schedules[0]],[(s,o) for s,_,o in schedules[1]])

if __name__=="__main__":unittest.main()
