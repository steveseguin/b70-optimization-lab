#!/usr/bin/env python3
"""CPU-only hostile receipt tests; synthetic clocks are never lab measurements."""
import copy
import json
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
import window
from summary import summarize, timing_stats, admission
from window_safety import environment_gate
from window import deadlines, ldd_preflight, distinct_owners


def fixture(kind="fusion", modes=None, payload=1024):
    modes = [0] if modes is None else modes
    label = "hc.a.norm" if kind == "fusion" else "route"
    candidate = "sg32" if kind == "fusion" else "p30.route.two.g1.wg32"
    registry = dict(repetitions=200,rotation_threshold_bytes=8*1024*1024,baseline_relative_tolerance=.15,minimum_relative_saving=.1,classes=[dict(klass=label,family=kind,candidates=[candidate],required_modes=modes,groups_per_token=48,anchor=dict(status="matched_class",expected_group_us=100,launches_per_group=2),resources=[label],dispatch=dict(section="classes",key="norm"))])
    environment = environment_gate(dict(OMP_NUM_THREADS="2",PATH="/usr/bin",HOME="/tmp",LD_LIBRARY_PATH="/synthetic/libs"))
    w=dict(schema="packet30.window.v1",window="G3",completed=True,device_executed=True,environment=environment,ldd_preflight=dict(argv=["ldd","binary"],returncode=0,stdout="libc.so resolved",stderr=""),deadlines=dict(expected_total_seconds=100,watchdog_seconds=400,submission_budget_seconds=dict(other=300)),owners=[])
    packets=[]
    for owner in range(2):
        w["owners"].append(dict(unit="owner%d"%owner,pid=100+owner,completed=True,returncode=0,child_still_running=False))
        native=dict(mode="G3",passed=True,completed=True,device_executed=True,safe_to_exit=True,live_bytes=0,in_flight=0,finite_element_gate_failures=0,teardown=dict(safe_to_exit=True,live_bytes=0,in_flight=0))
        exact=[];timing=[]
        for v in ["incumbent",candidate]:
            for mode in modes:exact.append(dict(klass=label,**{"class":label},workload=label,candidate=v,mode=mode,passed=True,new_current_bytes_equal=True,output_hashes="hash%d:"%mode))
            count=2 if v=="incumbent" or kind=="route" else 1
            duration=100000 if v=="incumbent" else 60000
            copies=8 if payload>8*1024*1024 else 1
            for rep in range(200):
                for index in range(count):timing.append({"class":label,"workload":label,"candidate":v,"repetition":rep,"event_index":index,"event_count":count,"start_ns":1000000+index*100000,"end_ns":1000000+index*100000+duration//count,"exact":True,"copies":copies,"copy_index":rep%copies,"payload_bytes":payload})
        packets.append(dict(native=native,exactness=exact,timing=timing))
    return w,packets,registry

class Protocol(unittest.TestCase):
    def result(self, f):return summarize(*f)
    def denied(self,f):self.assertFalse(self.result(f)["rows"][0]["qualified"])
    def test_success_sums_groups_not_launches(self):
        r=self.result(fixture());row=r["rows"][0]
        self.assertTrue(row["qualified"]);self.assertAlmostEqual(row["ms_per_token_saved"],1.92)
        self.assertEqual(row["owners"][0]["incumbent"]["median_us"],100)
        self.assertEqual(row["owners"][0]["candidate"]["p90_us"],60)
        self.assertEqual(r["dispatch"]["classes"],{"norm":"p30.fusion.sg32"})
    def test_exact_false(self):
        f=fixture();f[1][0]["exactness"][-1]["passed"]=False;self.denied(f)
    def test_bytes_false(self):
        f=fixture();f[1][1]["exactness"][-1]["new_current_bytes_equal"]=False;self.denied(f)
    def test_incumbent_host_failure(self):
        f=fixture();f[1][0]["exactness"][0]["passed"]=False;self.denied(f)
    def test_owner_hash_mismatch(self):
        f=fixture();f[1][1]["exactness"][-1]["output_hashes"]="changed";self.denied(f)
    def test_route_modes_required(self):
        f=fixture("route",[0,1,2]);self.assertTrue(self.result(f)["rows"][0]["qualified"])
        f[1][0]["exactness"].pop();self.denied(f)
    def test_duplicate_mode(self):
        f=fixture("route",[0,1,2]);f[1][0]["exactness"][-1]["mode"]=1;self.denied(f)
    def test_missing_event(self):
        f=fixture();f[1][0]["timing"].pop(0);self.denied(f)
    def test_duplicate_event(self):
        f=fixture();f[1][0]["timing"].append(dict(f[1][0]["timing"][0]));self.denied(f)
    def test_missing_repetition(self):
        f=fixture();f[1][1]["timing"]=[r for r in f[1][1]["timing"] if r["repetition"]!=199];self.denied(f)
    def test_extra_repetition(self):
        f=fixture();f[1][0]["timing"][-1]["repetition"]=200;self.denied(f)
    def test_fake_exact_timing(self):
        f=fixture();f[1][0]["timing"][-1]["exact"]=False;self.denied(f)
    def test_wrong_launch_count(self):
        f=fixture();r=f[1][0]["timing"][-1];r["event_count"]=2;self.denied(f)
    def test_consistent_wrong_incumbent_launch_count(self):
        # Preserve the exact per-group duration while replacing the two
        # incumbent events by one internally consistent event. The timing
        # median alone cannot prove the runtime launch identity.
        f=fixture()
        for packet in f[1]:
            kept=[]
            for row in packet["timing"]:
                if row["candidate"]!="incumbent":kept.append(row);continue
                if row["event_index"]:continue
                row["event_count"]=1;row["end_ns"]=row["start_ns"]+100000
                kept.append(row)
            packet["timing"]=kept
        self.denied(f)
    def test_baseline_mismatch(self):
        f=fixture();f[2]["classes"][0]["anchor"]["expected_group_us"]=200;self.denied(f)
    def test_post_p28_anchor_missing(self):
        f=fixture();f[2]["classes"][0]["anchor"]["expected_group_us"]=None;self.denied(f)
    def test_requires_saving_both_owners(self):
        f=fixture()
        for row in f[1][1]["timing"]:
            if row["candidate"]!="incumbent":row["end_ns"]=row["start_ns"]+95000
        self.denied(f)
    def test_rotation_above_8mb(self):
        f=fixture(payload=8*1024*1024+1);self.assertTrue(self.result(f)["rows"][0]["qualified"])
        f[1][0]["timing"][-1]["copies"]=1;self.denied(f)
    def test_rotation_index(self):
        f=fixture(payload=9*1024*1024);f[1][0]["timing"][-1]["copy_index"]=0;self.denied(f)
    def test_rotation_exact_threshold(self):
        self.assertTrue(self.result(fixture(payload=8*1024*1024))["rows"][0]["qualified"])
    def test_wrong_environment(self):
        f=fixture();f[0]["environment"]["native"]["ZE_DEBUG"]="1"
        with self.assertRaises(ValueError):self.result(f)
    def test_masked_environment(self):
        with self.assertRaises(ValueError):environment_gate(dict(OMP_NUM_THREADS="2",ZE_AFFINITY_MASK="0"))
    def test_wrong_threads(self):
        with self.assertRaises(ValueError):environment_gate(dict(OMP_NUM_THREADS="4"))
    def test_ldd(self):
        f=fixture();f[0]["ldd_preflight"]["stdout"]="libsycl.so => not found"
        with self.assertRaises(ValueError):self.result(f)
    def test_ldd_runner_rejection(self):
        class R:returncode=1;stdout="missing";stderr="failed"
        with self.assertRaises(ValueError):ldd_preflight("unused",runner=lambda *a,**k:R())
    def test_watchdog(self):
        f=fixture();f[0]["deadlines"]["watchdog_seconds"]=399
        with self.assertRaises(ValueError):self.result(f)
    def test_submission_budget(self):
        f=fixture();f[0]["deadlines"]["submission_budget_seconds"]["other"]=.01
        with self.assertRaises(ValueError):self.result(f)
    def test_window_budget_minimum(self):
        for mode in ["K0","G3"]:
            d=deadlines(mode);self.assertGreaterEqual(d["watchdog_seconds"],max(300,4*d["expected_total_seconds"]))
        with self.assertRaises(ValueError):deadlines("G3",300)
    def test_fresh_pids(self):
        f=fixture();f[0]["owners"][1]["pid"]=100
        with self.assertRaises(ValueError):self.result(f)
    def test_fresh_units(self):
        f=fixture();f[0]["owners"][1]["unit"]="owner0"
        with self.assertRaises(ValueError):self.result(f)
    def test_teardown(self):
        f=fixture();f[1][0]["native"]["live_bytes"]=1
        with self.assertRaises(ValueError):self.result(f)
    def test_unknown_class(self):
        f=fixture();f[1][0]["timing"][0]["class"]="unregistered"
        with self.assertRaises(ValueError):self.result(f)
    def test_generic_key_requires_all_classes(self):
        f=fixture();other=copy.deepcopy(f[2]["classes"][0]);other["klass"]="hc.f.norm";other["resources"]=["hc.f.norm"];f[2]["classes"].append(other)
        r=self.result(f);self.assertEqual(r["dispatch"]["classes"],{})
    def test_overlap_requires_explicit_choice(self):
        f=fixture();other=copy.deepcopy(f[2]["classes"][0]);other["klass"]="attn.combine+norm";other["dispatch"]=dict(section="fusions",key="attn.combine+norm");other["resources"]=["attn.combine","hc.a.norm"];f[2]["classes"].append(other)
        for p in f[1]:
            for key in ["exactness","timing"]:
                new=copy.deepcopy(p[key])
                for row in new:row["class"]=row["workload"]="attn.combine+norm"
                p[key]+=new
        r=self.result(f);self.assertEqual(r["dispatch"]["classes"],{});self.assertEqual(r["dispatch"]["fusions"],{});self.assertEqual(r["selected_ms_per_token_saved"],0)
        chosen=summarize(*f,overlap_selection=["fusions:attn.combine+norm"])
        self.assertEqual(chosen["dispatch"]["fusions"],{"attn.combine+norm":"p30.fusion.sg32"});self.assertAlmostEqual(chosen["selected_ms_per_token_saved"],1.92)
        with self.assertRaises(ValueError):summarize(*f,overlap_selection=["fusions:attn.combine+norm","classes:norm"])
    def test_continue_after_candidate_failure(self):
        f=fixture();f[2]["classes"][0]["candidates"].append("tiled")
        for packet,owner in zip(f[1],f[0]["owners"]):
            for kind in ["exactness","timing"]:
                addition=copy.deepcopy([r for r in packet[kind] if r["candidate"]=="sg32"])
                for row in addition:row["candidate"]="tiled"
                packet[kind]+=addition
            packet["exactness"][1]["passed"]=False
            packet["native"]["passed"]=False;packet["native"]["finite_element_gate_failures"]=1;owner["returncode"]=2
        r=self.result(f);by={row["raw_candidate"]:row for row in r["rows"]}
        self.assertFalse(by["sg32"]["qualified"]);self.assertTrue(by["tiled"]["qualified"])
        self.assertEqual(r["dispatch"]["classes"]["norm"],"p30.fusion.tiled")
    def test_failed_candidate_hash_variation_does_not_block(self):
        f=fixture();f[2]["classes"][0]["candidates"].append("tiled")
        for index,(packet,owner) in enumerate(zip(f[1],f[0]["owners"])):
            for kind in ["exactness","timing"]:
                addition=copy.deepcopy([r for r in packet[kind] if r["candidate"]=="sg32"])
                for row in addition:row["candidate"]="tiled"
                packet[kind]+=addition
            packet["exactness"][1]["passed"]=False
            packet["exactness"][1]["output_hashes"]="different-bad-output-"+str(index)
            packet["native"]["passed"]=False;packet["native"]["finite_element_gate_failures"]=1;owner["returncode"]=2
        result=self.result(f)
        self.assertEqual(result["dispatch"]["classes"],{"norm":"p30.fusion.tiled"})
        source=Path(__file__).with_name("window.py").read_text()
        self.assertNotIn('len({r["exactness_sha256"]',source)
    def test_unknown_selection(self):
        with self.assertRaises(ValueError):summarize(*fixture(),overlap_selection=["invented"])
    def test_library_path_required_and_unchanged(self):
        env = dict(HOME="/tmp", PATH="/usr/bin", OMP_NUM_THREADS="2")
        for value in (None, ""):
            if value is not None: env["LD_LIBRARY_PATH"] = value
            with self.assertRaisesRegex(ValueError, "LD_LIBRARY_PATH"):
                environment_gate(env)
        env.update(LD_LIBRARY_PATH="/a:/b::/a", LC_TIME="C", XDG_RUNTIME_DIR="/bus", DBUS_SESSION_BUS_ADDRESS="bus")
        native = environment_gate(env)["native"]
        self.assertEqual(native["LD_LIBRARY_PATH"], "/a:/b::/a")
        self.assertEqual(native["LC_TIME"], "C")
        self.assertNotIn("XDG_RUNTIME_DIR", native)
        self.assertNotIn("DBUS_SESSION_BUS_ADDRESS", native)
        for key in ("TMPDIR", "LD_PRELOAD", "SYCL_DEVICE_FILTER", "SHELL"):
            with self.assertRaises(ValueError): environment_gate(dict(env, **{key:"x"}))
    def test_lazy_library_empty_and_partial_path(self):
        with self.assertRaisesRegex(ValueError, "LD_LIBRARY_PATH"):
            window.lazy_library_preflight("")
        with tempfile.TemporaryDirectory(dir=window.HERE/"build") as directory:
            root = Path(directory)
            for index, name in enumerate(window.LAZY_LIBRARIES):
                with self.assertRaisesRegex(ValueError, name):
                    window.lazy_library_preflight(str(root))
                (root/name).write_bytes(b"filesystem fixture, never loaded")
            result = window.lazy_library_preflight(str(root))
            self.assertTrue(result["passed"])
            self.assertEqual(set(result["libraries"]), set(window.LAZY_LIBRARIES))
    def test_ldd_uses_native_environment(self):
        class R: returncode=0; stdout="resolved"; stderr=""
        env=fixture()[0]["environment"]["native"]
        with patch("subprocess.run", return_value=R()) as run:
            ldd_preflight("unused", runner=run, environment=env)
            self.assertEqual(run.call_args.kwargs["env"], env)
    def test_unit_forwards_library_path(self):
        env=fixture()[0]["environment"]
        with patch.object(window.subprocess, "Popen") as popen:
            window.NativeChild(["never-executed"], stdout=None, environment=env)
            command=popen.call_args.args[0]
            self.assertIn("LD_LIBRARY_PATH="+env["native"]["LD_LIBRARY_PATH"], command)
            self.assertIn("-i", command)
    def test_k0_binds_library_path_hash(self):
        with tempfile.TemporaryDirectory(dir=window.HERE/"build") as directory:
            path=Path(directory)/"window.json"
            prior=dict(window="K0", passed=True, ld_library_path_sha256="old")
            path.write_text(json.dumps(prior))
            with self.assertRaisesRegex(ValueError, "ld_library_path_sha256"):
                window.k0_gate(path, dict(ld_library_path_sha256="new"))
    def test_kernel_empty_markers_only(self):
        for text in ("", "\n", "-- No entries --\n-- No entries --\n"):
            self.assertTrue(window.kernel_delta_empty(text))
        for text in ("Fault response", "[1.0] ordinary kernel entry", "journal unavailable"):
            self.assertFalse(window.kernel_delta_empty(text))
    def simulated_failure(self, contacted, kernel_text="", mode="K0", journal_error=False):
        # Every operational boundary is mocked: no device, journal, or unit runs.
        with tempfile.TemporaryDirectory(dir=window.HERE/"build") as directory:
            root=Path(directory);(root/"build").mkdir();binary=root/"binary";binary.write_text("not executable")
            (root/"build-receipt.json").write_text("{}")
            for name in window.LAZY_LIBRARIES:(root/name).write_bytes(b"fixture")
            env=environment_gate(dict(OMP_NUM_THREADS="2", LD_LIBRARY_PATH=str(root)))
            class Child:
                unit="mock-unit";pid=123
                def __init__(self, command, **kwargs):
                    native=Path(command[-1]);native.mkdir(parents=True)
                    if contacted is not None:
                        (native/"failure.json").write_text(json.dumps(dict(passed=False,device_contacted=contacted,error="mock")))
            def supervise(child, seconds, cursor, kernel, failure, reasons):
                kernel.write(kernel_text);kernel.flush()
                if journal_error:reasons.append("kernel journal failed: mock")
                return dict(returncode=1,child_still_running=False,journal_cursor="mock")
            with patch.multiple(window, HERE=root, environment_gate=lambda:env,
                    sealed_build=lambda:(binary,{}), ldd_preflight=lambda *a,**k:{},
                    journal=lambda:("", "mock"), NativeChild=Child, supervise=supervise,
                    k0_gate=lambda *a:None), patch.object(window.os,"getpriority",return_value=19), \
                    patch.object(window.subprocess,"check_output",return_value="idle"), \
                    patch.object(window.signal,"signal"):
                args=["--authorized-device-window","--window",mode,"--card","2","--output",str(root/"out")]
                if mode=="G3":
                    k0=root/"k0.json";k0.write_text("{}");args += ["--k0",str(k0)]
                self.assertEqual(window.main(args),1)
            record=json.loads((root/"out/window.json").read_text())
            return record,(root/"build/device-fault-latch.json").exists()
    def test_no_contact_failure_never_latches(self):
        for mode in ("K0", "G3"):
            for kernel in ("", "-- No entries --\n"):
                record,latched=self.simulated_failure(False,kernel,mode)
                self.assertFalse(latched)
                self.assertFalse(record["passed"])
                self.assertFalse(record["device_contacted"])
                self.assertEqual(record["failure_class"],"preflight")
    def test_contacted_and_unknown_failures_latch(self):
        for contacted in (True,None):
            record,latched=self.simulated_failure(contacted)
            self.assertTrue(latched)
    def test_nonempty_or_unavailable_journal_latches(self):
        for kernel in ("Fault response\n", "[1.0] unrelated kernel entry\n"):
            self.assertTrue(self.simulated_failure(False,kernel)[1])
        self.assertTrue(self.simulated_failure(False,journal_error=True)[1])
    def test_unknown_or_running_owner_cannot_clear_fault(self):
        owner=dict(device_contacted=False,child_still_running=False,kernel_delta_empty=True)
        self.assertTrue(window.precontact_failure([owner]))
        for key,value in (("device_contacted",None),("device_contacted",True),("child_still_running",True),("kernel_delta_empty",False)):
            self.assertFalse(window.precontact_failure([dict(owner,**{key:value})]))
        self.assertFalse(window.precontact_failure([]))
    def test_safety_precedes_latch(self):
        source=Path(__file__).with_name("window.py").read_text();main=source[source.index("def main("):]
        self.assertLess(main.index("loader = ldd_preflight"),main.index("latch ="))
        self.assertLess(main.index("lazy_loader = lazy_library_preflight"),main.index("latch ="))
        self.assertLess(main.index("environment = environment_gate"),main.index("latch ="))

if __name__=="__main__":unittest.main(verbosity=2)
