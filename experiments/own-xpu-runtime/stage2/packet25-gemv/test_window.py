#!/usr/bin/env python3
"""Mock-only timing/admission tests; never creates a device owner."""
import io
import json
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch
import window as w
from window_safety import environment_gate

class Clock:
    def __init__(self): self.value = 0.
    def now(self): return self.value
    def sleep(self, seconds): self.value += seconds

class Child:
    def __init__(self, clock, done=None, cooperative=True):
        self.clock, self.done, self.cooperative = clock, done, cooperative
        self.signals = []
    def poll(self):
        return 0 if self.done is not None and self.clock.now() >= self.done else None
    @property
    def returncode(self): return self.poll()
    def send_signal(self, sig):
        self.signals.append(sig)
        if self.cooperative: self.done = self.clock.now()+.5

class Tests(unittest.TestCase):
    def test_environment_closed(self):
        good = {"OMP_NUM_THREADS":"2", "PATH":"/usr/bin", "LD_LIBRARY_PATH":"/coordinator/libs", "CODEX_METADATA":"ignored"}
        self.assertEqual(set(environment_gate(good)["native"]), {"OMP_NUM_THREADS", "PATH", "LD_LIBRARY_PATH"})
        for name,value in [("NEOReadDebugKeys", ""), ("UNREGISTERED", "1"), ("SYCL_DEVICE_FILTER", "gpu")]:
            with self.assertRaises(ValueError): environment_gate(dict(good, **{name:value}))
        with self.assertRaises(ValueError): environment_gate({"OMP_NUM_THREADS":"4"})

    def test_ldd_failure(self):
        class R:
            returncode=0;stdout="libsycl.so => not found";stderr=""
        with self.assertRaises(ValueError): w.ldd_preflight("device", lambda *a,**k:R())
        R.stdout="libsycl.so => /lib/libsycl.so"
        self.assertEqual(w.ldd_preflight("device", lambda *a,**k:R())["returncode"], 0)
        R.returncode=1
        with self.assertRaises(ValueError): w.ldd_preflight("device", lambda *a,**k:R())

    def test_deadlines(self):
        for mode in ("K0", "G1"):
            r=w.deadlines(mode)
            self.assertGreaterEqual(r["watchdog_seconds"], 300)
            self.assertGreaterEqual(r["watchdog_seconds"], 4*r["expected_total_seconds"])
            self.assertFalse(r["expectation_enforced"])
            self.assertLess(max(r["submission_budget_seconds"].values()), 2)
            with self.assertRaises(ValueError): w.deadlines(mode, r["minimum_watchdog_seconds"]-1)

    def test_k0_identity(self):
        identity=dict(boot_id="boot",card=2,binary_sha256="binary",environment={"native":{}},build_receipt_sha256="build")
        row=dict(identity,window="K0",passed=True,owners=[dict(native_receipt_sha256="native")])
        with patch.object(w,"read", return_value=row), patch.object(w,"sha", return_value="native"), patch.object(w,"native_gate", return_value={}):
            self.assertEqual(w.k0_gate(Path("window.json"),identity), row)
            for key in identity:
                with self.assertRaises(ValueError): w.k0_gate(Path("window.json"),dict(identity,**{key:"changed"}))
            with self.assertRaises(ValueError): w.k0_gate(None,identity)

    def test_native_ownership_receipt(self):
        good=dict(passed=True,safe_to_exit=True,device_executed=True,live_bytes=0,in_flight=0,mode="K0")
        with patch.object(w,"read",return_value=good):
            self.assertEqual(w.native_gate(Path("mock"),"K0"),good)
        for key,value in (("passed",False),("safe_to_exit",False),("device_executed",False),("live_bytes",1),("in_flight",1),("mode","G1")):
            with patch.object(w,"read",return_value=dict(good,**{key:value})):
                with self.assertRaises(ValueError): w.native_gate(Path("mock"),"K0")

    def test_distinct_owners(self):
        w.distinct_owners([dict(unit="a",pid=1),dict(unit="b",pid=2)],2)
        with self.assertRaises(ValueError): w.distinct_owners([dict(unit="a",pid=1),dict(unit="a",pid=2)],2)
        with self.assertRaises(ValueError): w.distinct_owners([dict(unit="a",pid=1)],2)

    def supervise(self, child, clock, seconds=5., journal=lambda cursor:("", "cursor")):
        failures=[]; reasons=[]
        def fail(reason):
            failures.append((reason, list(child.signals)))
        result=w.supervise(child,seconds,"cursor",io.StringIO(),fail,reasons,
                           journal_fn=journal,now=clock.now,sleep=clock.sleep,drain_seconds=1)
        return result,failures,reasons

    def test_success_no_signal(self):
        clock=Clock();child=Child(clock,done=.5)
        result, failures,_=self.supervise(child,clock)
        self.assertEqual(result["returncode"],0);self.assertFalse(failures);self.assertFalse(child.signals)

    def test_watchdog_one_signal_failure_saved_first(self):
        clock=Clock();child=Child(clock)
        result, failures,_=self.supervise(child,clock)
        self.assertEqual(child.signals,[signal.SIGTERM]);self.assertTrue(result["sigterm_sent"])
        self.assertEqual(failures[0][1],[])

    def test_fault_fast_fails_and_does_not_hardkill(self):
        clock=Clock();child=Child(clock,cooperative=False)
        result, failures,reasons=self.supervise(child,clock,journal=lambda c:("xe Fault response",c))
        self.assertTrue(result["child_still_running"]);self.assertEqual(child.signals,[signal.SIGTERM])
        self.assertLess(result["elapsed_seconds"],5);self.assertEqual(failures[0][1],[])

    def test_journal_fail_closed(self):
        clock=Clock();child=Child(clock)
        def missing(cursor): raise OSError("denied")
        result,failures,_=self.supervise(child,clock,journal=missing)
        self.assertTrue(failures);self.assertEqual(child.signals,[signal.SIGTERM])

    def test_fault_signatures(self):
        for line in ("Fault response", "CAT error", "engine reset", "devcoredump"):
            self.assertRegex(line,w.FAULT)
        self.assertIsNone(w.FAULT.search("change detected; hanging decoration"))

    def test_ldd_before_latch(self):
        text=Path(w.__file__).read_text()
        main=text[text.index("def main("):]
        self.assertLess(main.index("loader = ldd_preflight"),main.index("latch ="))

if __name__ == "__main__":
    unittest.main()
