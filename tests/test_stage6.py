import json
import os
import threading
import unittest

from system_stage6.protocol import branch_label,rpc
from system_stage6.runtime import ARCHITECTURES,Stage6Cluster

class Stage6SystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cluster=Stage6Cluster("LOCAL-LAN","SMALL").__enter__()
    @classmethod
    def tearDownClass(cls):
        cls.cluster.__exit__(None,None,None)
    def test_process_boundary_is_real(self):
        pids=self.cluster.pids
        self.assertGreaterEqual(len(pids),11);self.assertEqual(len(set(pids.values())),len(pids));self.assertNotIn(os.getpid(),pids.values())
        self.assertNotEqual(rpc(self.cluster.planner_port,{"op":"ping"}).response["pid"],os.getpid())
    def test_plaintext_never_sent_to_planner(self):
        result=self.cluster.action("FIXED-CANONICAL-MODULAR","plain-1",tenant="plain")
        serialized=json.dumps(result)
        self.assertNotIn("example.invalid",serialized);self.assertNotIn("synthetic_document",serialized);self.assertNotIn("Project Aurora quote",serialized)
    def test_authorization_all_architectures(self):
        for arch in ARCHITECTURES:
            tenant="auth-"+arch;self.cluster.set_permission(True,tenant)
            self.assertEqual(self.cluster.action(arch,"allow-"+arch,tenant=tenant)["status"],"ALLOW")
            self.assertEqual(self.cluster.action(arch,"bad-"+arch,tenant=tenant,document="INVALID_HANDLE")["status"],"DENY")
    def test_revocation_visible_all_protected_architectures(self):
        for arch in ARCHITECTURES[2:]:
            tenant="revoke-"+arch;self.cluster.set_permission(True,tenant)
            self.assertEqual(self.cluster.action(arch,"before-"+arch,tenant=tenant)["status"],"ALLOW")
            self.cluster.set_permission(False,tenant)
            self.assertEqual(self.cluster.action(arch,"after-"+arch,tenant=tenant)["status"],"DENY")
    def test_deny_to_allow_update_visible(self):
        for arch in ARCHITECTURES[2:]:
            tenant="update-"+arch;self.cluster.set_permission(False,tenant)
            self.assertEqual(self.cluster.action(arch,"deny-"+arch,tenant=tenant)["status"],"DENY")
            self.cluster.set_permission(True,tenant)
            self.assertEqual(self.cluster.action(arch,"newallow-"+arch,tenant=tenant)["status"],"ALLOW")
    def test_cross_device_history_visibility(self):
        tenant="devices";arch="HYBRID-PH";self.cluster.set_permission(True,tenant)
        self.cluster.action(arch,"device-a-event",device="employee_device_A",tenant=tenant)
        second=self.cluster.action(arch,"device-b-event",device="employee_device_B",tenant=tenant)
        self.assertEqual(second["status"],"ALLOW");self.assertEqual(second["metrics"]["history_sync_rtts"],1)
        self.assertEqual(self.cluster.history_snapshot(arch,tenant)["version"],2)
    def test_hybrid_ph_retains_synchronized_history(self):
        tenant="retained-history";arch="HYBRID-PH";self.cluster.set_permission(True,tenant)
        self.cluster.action(arch,"retain-one",device="employee_device_A",tenant=tenant)
        second=self.cluster.action(arch,"retain-two",device="employee_device_A",tenant=tenant)
        # SMALL uses 128-B permissions and 256-B history records. Two cached
        # events plus permission require at least 640 logical cache bytes.
        self.assertGreaterEqual(second["metrics"]["trusted_cache_bytes"],640)
    def test_no_lost_disclosure_updates(self):
        tenant="concurrent";arch="FIXED-CANONICAL-MODULAR";self.cluster.set_permission(True,tenant);results=[]
        threads=[threading.Thread(target=lambda i=i:results.append(self.cluster.action(arch,f"concurrent-{i}",tenant=tenant,device=f"device-{i%2}"))) for i in range(8)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(sum(x["status"]=="ALLOW" for x in results),8);self.assertEqual(self.cluster.history_snapshot(arch,tenant)["version"],8)
    def test_no_duplicate_mock_effect_or_log(self):
        tenant="retry";arch="UNIFIED-ORAM";self.cluster.set_permission(True,tenant)
        first=self.cluster.action(arch,"same-request",tenant=tenant);second=self.cluster.action(arch,"same-request",tenant=tenant)
        self.assertFalse(first["duplicate_effect"]);self.assertTrue(second["duplicate_effect"]);self.assertEqual(self.cluster.history_snapshot(arch,tenant)["version"],1)
    def test_functional_and_authorization_equivalence(self):
        statuses=[]
        for arch in ARCHITECTURES:
            tenant="equiv-"+arch;self.cluster.set_permission(True,tenant);statuses.append(self.cluster.action(arch,"equiv-"+arch,tenant=tenant)["status"])
        self.assertEqual(statuses,["ALLOW"]*len(ARCHITECTURES))
    def test_host_visible_trace_has_no_private_ids(self):
        for arch in ARCHITECTURES:
            result=self.cluster.action(arch,"trace-"+arch,tenant="trace-"+arch)
            trace=json.dumps(result["host_visible_trace"])
            for forbidden in ("CONTACT_","DOCUMENT_","example.invalid","synthetic_document","history_required"):
                self.assertNotIn(forbidden,trace)
    def test_protected_privacy_sanity(self):
        for arch in ARCHITECTURES:
            shapes={0:set(),1:set()}
            for i in range(12):
                rid=f"privacy-{arch}-{i}";result=self.cluster.action(arch,rid,tenant="privacy-"+arch)
                shape=tuple((e["endpoint"],e["operation"]) for e in result["host_visible_trace"]);shapes[branch_label(rid)].add(shape)
            if arch in ("DIRECT-MODULAR","INDEPENDENT-MODULAR-ORAM"):
                self.assertNotEqual(shapes[0],shapes[1])
            else:self.assertEqual(shapes[0],shapes[1])
    def test_wire_and_freshness_accounting(self):
        for arch in ARCHITECTURES:
            result=self.cluster.action(arch,"wire-"+arch,tenant="wire-"+arch);metrics=result["metrics"]
            expected=sum(x["request_bytes"]+x["response_bytes"] for x in result["host_visible_trace"])
            self.assertEqual(metrics["wire_bytes"],expected);self.assertGreater(expected,0)
        hp=self.cluster.action("HYBRID-P","fresh-p",tenant="fresh-p")["metrics"]
        hph=self.cluster.action("HYBRID-PH","fresh-ph",tenant="fresh-ph")["metrics"]
        self.assertEqual(hp["freshness_rtts"],1);self.assertEqual(hph["freshness_rtts"],1);self.assertEqual(hph["history_sync_rtts"],1)

if __name__=="__main__":unittest.main()
