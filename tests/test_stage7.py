import json
import multiprocessing
import tempfile
import threading
import unittest
from pathlib import Path

from system_stage7.durable_oram import CRASH_POINTS,CrashInjected,DurablePathORAM,ORAMCoordinator,SecurityError,atomic_json,read_json
from system_stage7.effects import AuthoritativeDisclosureLog,EffectAuditProtocol,EffectFailure,IdempotentTool
from system_stage7.faults import LocalFaultInjector,fail_closed_authorization
from system_stage7.hybrid import EnterpriseAuthority,HybridRecoveryClient
from system_stage7.worker import durable_oram_worker

class Stage7SecurityTests(unittest.TestCase):
    def make_oram(self,name="oram",n=16):
        root=Path(tempfile.mkdtemp(prefix="stage7_test_"))/name
        return root,DurablePathORAM(root,n_blocks=n,seed=7,height=4,domain=name)
    def mutate_envelope(self,field,value):
        root,oram=self.make_oram();data=read_json(oram.server/oram.active_server_file);data["envelopes"][0][field]=value;atomic_json(oram.server/oram.active_server_file,data)
        with self.assertRaisesRegex(SecurityError,"verification failed"):DurablePathORAM.open_existing(root,domain="oram")
    def test_authenticated_block_integrity_and_ciphertext_corruption(self):
        root,oram=self.make_oram();data=read_json(oram.server/oram.active_server_file);data["envelopes"][0]["ciphertext"]+="A";atomic_json(oram.server/oram.active_server_file,data)
        with self.assertRaisesRegex(SecurityError,"verification failed"):DurablePathORAM.open_existing(root,domain="oram")
    def test_authentication_tag_and_version_corruption(self):
        self.mutate_envelope("tag","00"*32);self.mutate_envelope("version",999)
    def test_missing_and_duplicated_bucket_detection(self):
        for mode in ("missing","duplicate"):
            root,oram=self.make_oram(mode);data=read_json(oram.server/oram.active_server_file)
            if mode=="missing":data["envelopes"].pop()
            else:data["envelopes"].append(data["envelopes"][0])
            atomic_json(oram.server/oram.active_server_file,data)
            with self.assertRaises(SecurityError):DurablePathORAM.open_existing(root,domain=mode)
    def test_old_tree_and_block_replay_detection(self):
        root,oram=self.make_oram();old=oram.active_server_bytes();oram.access(3,"write","current");oram.replace_active_server_bytes(old)
        with self.assertRaises(SecurityError):DurablePathORAM.open_existing(root,domain="oram")
    def test_key_rotation_rejects_old_blocks(self):
        root,oram=self.make_oram();old=oram.active_server_bytes();oram.rotate_key();oram.replace_active_server_bytes(old)
        with self.assertRaises(SecurityError):DurablePathORAM.open_existing(root,domain="oram")
    def test_position_map_and_stash_recovery(self):
        root,oram=self.make_oram(n=32);expected={}
        for i in range(10):expected[i]=f"value-{i}";oram.access(i,"write",expected[i])
        position=dict(oram.oram.position);stash={k:v.value for k,v in oram.oram.stash.items()};recovered=DurablePathORAM.open_existing(root,domain="oram")
        self.assertEqual(recovered.oram.position,position);self.assertEqual({k:v.value for k,v in recovered.oram.stash.items()},stash)
        for k,v in expected.items():self.assertEqual(recovered.peek(k),v)
    def test_all_crash_points_recover_safely(self):
        for point in CRASH_POINTS:
            root=Path(tempfile.mkdtemp(prefix="stage7_crash_"))/point;oram=DurablePathORAM(root,n_blocks=16,seed=9,height=4,domain=point);oram.access(0,"write","committed")
            with self.assertRaises(CrashInjected):oram.access(0,"write","new-value",inject_crash=point)
            recovered=DurablePathORAM.open_existing(root,domain=point);expected="new-value" if point=="after_client_checkpoint_before_ack" else "committed"
            self.assertEqual(recovered.peek(0),expected);recovered.oram.assert_invariants()
    def test_recovery_trace_is_privacy_preserving(self):
        root,oram=self.make_oram();recovered=DurablePathORAM.open_existing(root,domain="oram");trace=json.dumps(recovered.recovery_trace)
        self.assertIn("full_oblivious_recovery_scan",trace);self.assertNotIn("block_id",trace);self.assertNotIn("CONTACT_",trace)
    def test_error_messages_are_secret_independent(self):
        root,oram=self.make_oram();data=read_json(oram.server/oram.active_server_file);data["envelopes"][0]["tag"]="bad";atomic_json(oram.server/oram.active_server_file,data)
        try:DurablePathORAM.open_existing(root,domain="oram")
        except SecurityError as exc:
            message=str(exc);self.assertNotIn("bucket-",message);self.assertNotIn("block",message.lower());self.assertNotIn("permission",message.lower())
    def test_hybrid_stale_cache_restart_rejects_revocation(self):
        authority=EnterpriseAuthority();client=HybridRecoveryClient(authority);self.assertEqual(client.authorize(),"ALLOW");old=client.snapshot();authority.set_permission(False)
        restored=HybridRecoveryClient(authority);restored.restore(old);self.assertFalse(restored.cache_valid);self.assertEqual(restored.recover(),"ready");self.assertEqual(restored.authorize(),"DENY")
    def test_cross_device_history_recovery(self):
        authority=EnterpriseAuthority();device_b=HybridRecoveryClient(authority,with_history=True);device_b.recover();old=device_b.snapshot();authority.append("event-a","device-A")
        restored=HybridRecoveryClient(authority,with_history=True);restored.restore(old);self.assertEqual(restored.recover(),"ready");self.assertEqual(restored.history_version,1);self.assertEqual(restored.history[0]["event_id"],"event-a");self.assertEqual(restored.last_recovery["rtts"],2)
    def test_fail_closed_when_permission_unavailable(self):
        authority=EnterpriseAuthority();client=HybridRecoveryClient(authority);client.authorize();authority.available=False
        self.assertEqual(client.authorize(),"DEFER");self.assertEqual(client.recover(),"defer");self.assertFalse(client.cache_valid)
    def test_concurrent_history_appends_no_loss_or_duplicates(self):
        for count in (2,8,32):
            authority=EnterpriseAuthority();threads=[threading.Thread(target=authority.append,args=(f"event-{i}",f"device-{i%2}")) for i in range(count)]
            for t in threads:t.start()
            for t in threads:t.join()
            self.assertEqual(len(authority.history),count);self.assertEqual([e["version"] for e in authority.history],list(range(1,count+1)))
            authority.append("event-0");self.assertEqual(len(authority.history),count)
    def test_effect_succeeds_log_commit_fails_then_reconciles(self):
        root=Path(tempfile.mkdtemp(prefix="effect_a_"));p=EffectAuditProtocol(root);p.log.fail_commit=True
        with self.assertRaises(EffectFailure):p.execute("op-a",{"message":"synthetic"})
        self.assertIsNotNone(p.tool.query("op-a"));self.assertEqual(p.reconcile(),"committed");self.assertEqual(p.log.status("op-a"),"COMMITTED")
    def test_log_prepare_succeeds_effect_fails_without_false_commit(self):
        root=Path(tempfile.mkdtemp(prefix="effect_b_"));tool=IdempotentTool();tool.fail_mode="before_effect";p=EffectAuditProtocol(root,tool=tool)
        with self.assertRaises(EffectFailure):p.execute("op-b",{})
        self.assertEqual(p.reconcile(),"aborted");self.assertEqual(p.log.status("op-b"),"ABORTED")
    def test_crash_after_effect_and_ambiguous_timeout_reconcile(self):
        for mode in ("crash","timeout"):
            root=Path(tempfile.mkdtemp(prefix="effect_amb_"));tool=IdempotentTool();p=EffectAuditProtocol(root,tool=tool)
            if mode=="timeout":tool.fail_mode="timeout_after_effect"
            with self.assertRaises((CrashInjected,TimeoutError)):p.execute("op-"+mode,{},crash_after_effect=mode=="crash")
            tool.fail_mode=None;self.assertEqual(p.reconcile(),"committed");self.assertEqual(len(tool.effects),1);self.assertEqual(p.log.status("op-"+mode),"COMMITTED")
    def test_duplicate_effect_retry_executes_once(self):
        root=Path(tempfile.mkdtemp(prefix="effect_dup_"));p=EffectAuditProtocol(root);first=p.execute("op",{});second=p.execute("op",{})
        self.assertFalse(first["duplicate"]);self.assertTrue(second["duplicate"]);self.assertEqual(len(p.tool.effects),1);self.assertEqual(len(p.log.committed()),1)
        with self.assertRaisesRegex(EffectFailure,"payload mismatch"):p.tool.execute("op",{"different":True})
    def test_disclosure_log_service_restart(self):
        root=Path(tempfile.mkdtemp(prefix="log_restart_"));path=root/"log.json";log=AuthoritativeDisclosureLog(path);log.prepare("op");log.commit("op");restarted=AuthoritativeDisclosureLog(path)
        self.assertEqual(restarted.status("op"),"COMMITTED")
    def test_permission_and_history_authority_restart(self):
        root=Path(tempfile.mkdtemp(prefix="authority_restart_"));path=root/"authority.json";authority=EnterpriseAuthority(path);authority.set_permission(False);authority.append("event-a","device-A")
        restarted=EnterpriseAuthority(path);self.assertFalse(restarted.permission()["allow"]);self.assertEqual(restarted.permission()["version"],2);self.assertEqual(restarted.sync(0)["events"][0]["event_id"],"event-a")
    def test_idempotent_tool_registry_survives_restart(self):
        root=Path(tempfile.mkdtemp(prefix="tool_restart_"));path=root/"tool.json";tool=IdempotentTool(path);tool.execute("op",{})
        restarted=IdempotentTool(path);result=restarted.execute("op",{});self.assertTrue(result["duplicate"]);self.assertEqual(len(restarted.effects),1)
    def test_storage_process_termination_and_restart(self):
        root,oram=self.make_oram("process-crash");oram.access(0,"write","committed");ctx=multiprocessing.get_context("spawn");commands=ctx.Queue();results=ctx.Queue()
        process=ctx.Process(target=durable_oram_worker,args=(str(root),"process-crash",commands,results));process.start();commands.put({"op":"access","block_id":0,"operation":"write","value":"new","crash":"after_server_write_before_client_checkpoint"});process.join(10)
        self.assertEqual(process.exitcode,91)
        restarted=ctx.Process(target=durable_oram_worker,args=(str(root),"process-crash",commands,results));restarted.start();commands.put({"op":"peek","block_id":0});answer=results.get(timeout=10);commands.put({"op":"stop"});restarted.join(10)
        self.assertEqual(answer["value"],"committed");self.assertNotEqual(answer["pid"],process.pid)
    def test_local_service_failures_are_fail_closed_and_duplicate_safe(self):
        faults=LocalFaultInjector()
        for service in ("private","permission","history"):
            for mode in ("timeout","connection_drop","unavailable"):
                try:faults.call(service,"op",mode)
                except Exception as exc:self.assertEqual(fail_closed_authorization(error=exc),"DEFER")
        duplicated=faults.call("tool","effect","duplicate_response");self.assertEqual(duplicated[0]["operation_id"],duplicated[1]["operation_id"])
        start=__import__("time").perf_counter();faults.call("history","slow","delayed",delay_ms=5);self.assertGreaterEqual(__import__("time").perf_counter()-start,.005)
    def test_multi_client_oram_coordinator_serializes(self):
        root,oram=self.make_oram(n=32);coordinator=ORAMCoordinator(oram);errors=[]
        def worker(i):
            try:coordinator.access(i%32,"write",f"client-{i}")
            except Exception as exc:errors.append(exc)
        threads=[threading.Thread(target=worker,args=(i,)) for i in range(16)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertFalse(errors);self.assertEqual(len(coordinator.wait_samples),16);oram.oram.assert_invariants()

if __name__=="__main__":unittest.main()
