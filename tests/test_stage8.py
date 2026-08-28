import inspect
import json
import random
import unittest

from stage8_real_traces.runtime import FORBIDDEN,VARIANTS,EnterpriseState,Episode,ServiceCluster,SourceFaithfulMediator,TraceTransport,UserTask,generate_episode,ground_truth

class Stage8RealTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.cluster=ServiceCluster()
    @classmethod
    def tearDownClass(cls):cls.cluster.close()
    def execute(self,e,variant,seed=1):return SourceFaithfulMediator(variant,TraceTransport(self.cluster,variant,seed)).execute(e)
    def episode(self,origin="direct_private_db",permission="ALLOW",consent="ALLOW",task="SEND_MESSAGE"):
        return Episode(1,EnterpriseState(7,3,origin,permission,consent,2,origin=="persistent_transitive"),UserTask(task,"peer"))
    def test_state_precedes_task_and_label_derivation(self):
        e=generate_episode(random.Random(9),1);self.assertEqual(e.generation_order,("state","task"));truth=ground_truth(e)
        self.assertEqual(truth["requires_history"],int(e.state.taint_origin=="persistent_transitive"))
        self.assertNotIn("label",inspect.signature(SourceFaithfulMediator.execute).parameters)
        harness=inspect.getsource(__import__("stage8_real_traces.experiment",fromlist=["run_stage8"]).run_stage8)
        self.assertLess(harness.index("captured.append"),harness.index("truth=ground_truth(e)"))
    def test_no_direct_label_branch_exists(self):
        source=inspect.getsource(SourceFaithfulMediator)
        self.assertNotIn("hidden_class",source);self.assertNotIn("private_label",source)
        self.assertIn("s.taint_origin==\"direct_private_db\"",source)
    def test_actual_localhost_process_boundaries(self):
        self.assertEqual(len(self.cluster.processes),9);self.assertTrue(all(p.is_alive() for p in self.cluster.processes))
        self.assertTrue(all(p.pid != __import__("os").getpid() for p in self.cluster.processes))
    def test_host_trace_private_separation(self):
        _,trace=self.execute(self.episode("persistent_transitive"),"ORIGINAL-MEDIATOR")
        encoded=json.dumps(trace)
        for field in FORBIDDEN:self.assertNotIn(field,encoded)
        self.assertNotIn("entity:7",encoded);self.assertNotIn("persistent_transitive",encoded)
    def test_natural_source_condition_changes_original_trace(self):
        _,direct=self.execute(self.episode("direct_private_db"),"ORIGINAL-MEDIATOR",2)
        _,transitive=self.execute(self.episode("persistent_transitive"),"ORIGINAL-MEDIATOR",3)
        self.assertEqual(direct[0]["destination_service"],"PRIVATE_DATA_DB")
        self.assertEqual(transitive[0]["destination_service"],"DISCLOSURE_LOG")
        self.assertEqual(len(direct),len(transitive))
    def test_per_service_oram_hides_address_not_service(self):
        _,direct=self.execute(self.episode("direct_private_db"),"PER-SERVICE-ORAM",4)
        _,transitive=self.execute(self.episode("persistent_transitive"),"PER-SERVICE-ORAM",5)
        self.assertEqual(direct[0]["operation_class"],"ORAM_ACCESS");self.assertIn("physical_path",direct[0]);self.assertNotIn("stable_address",direct[0])
        self.assertNotEqual(direct[0]["destination_service"],transitive[0]["destination_service"])
    def test_unified_and_fixed_per_action_shapes_hide_provenance(self):
        for variant in ("UNIFIED-OBLIVIOUS","FIXED-CANONICAL","TRUSTED-LOCAL"):
            _,a=self.execute(self.episode("direct_private_db"),variant,6);_,b=self.execute(self.episode("persistent_transitive"),variant,6)
            shape=lambda t:[(x["destination_service"],x["operation_class"],x["request_bytes"],x["response_bytes"]) for x in t]
            self.assertEqual(shape(a),shape(b),variant)
    def test_functional_equivalence_all_variants(self):
        for origin in ("direct_private_db","persistent_transitive"):
            for permission in ("ALLOW","DENY","MISSING"):
                e=self.episode(origin,permission,"ALLOW","SHARE_DOCUMENT");outputs=[self.execute(e,v,10+i)[0] for i,v in enumerate(VARIANTS)]
                self.assertTrue(all(x==outputs[0] for x in outputs[1:]))
    def test_adaptive_missing_permission_adds_action_and_prompt(self):
        for variant in VARIANTS:
            existing,te=self.execute(self.episode(permission="ALLOW"),variant,20);missing,tm=self.execute(self.episode(permission="MISSING",consent="ALLOW"),variant,21)
            self.assertEqual(existing["effect_count"],missing["effect_count"]);self.assertEqual(existing["attempts"],1);self.assertEqual(missing["attempts"],2)
            self.assertNotIn("USER_CONSENT",[x["destination_service"] for x in te]);self.assertIn("USER_CONSENT",[x["destination_service"] for x in tm])
    def test_effect_workflows_are_local_and_state_changing(self):
        endpoints=set()
        for task in ("SEND_MESSAGE","SHARE_DOCUMENT","CREATE_EVENT","FORWARD_INFORMATION"):
            output,trace=self.execute(self.episode(task=task),"ORIGINAL-MEDIATOR",30+len(endpoints));self.assertEqual(output["effect_count"],1)
            endpoints.add(next(x["destination_service"] for x in trace if x["operation_class"]=="EFFECT"))
        self.assertEqual(len(endpoints),4)

if __name__=="__main__":unittest.main()
