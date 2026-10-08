"""Synthetic CPU fixtures; no Docker, network, GPU or privileged reads."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import calibration as c
import screen
from memory_watchdog import MemoryWatchdog


def sample(t=0, phase='plateau', pressure=70_000_000_000):
    return dict(monotonic=t, phase=phase, accounted_pressure_bytes=pressure,
                mem_available_bytes=40*c.GIB, committed_as_bytes=100*c.GIB,
                mlocked_bytes=60*c.GIB, unevictable_bytes=61*c.GIB,
                cgroup_memory_current_bytes=65*c.GIB, cgroup_memory_peak_bytes=66*c.GIB,
                worker_rss_bytes=[16*c.GIB]*4, vram_free_bytes_per_rank=[4*c.GIB]*4,
                accounting_errors=[])


def samples():
    return [sample(-.5, 'loading')] + [sample(i*.5) for i in range(41)]


class ParsingTests(unittest.TestCase):
    def test_meminfo_units_and_not_summed(self):
        s = c.parse_meminfo('MemTotal: 100 kB\nMemAvailable: 60 kB\nCommitted_AS: 200 kB\nMlocked: 10 kB\nUnevictable: 11 kB\n')
        self.assertEqual(s['accounted_pressure_bytes'], 40*1024)
        self.assertEqual(s['committed_as_bytes'], 200*1024)
        self.assertEqual(s['mlocked_bytes'], 10*1024)
        self.assertEqual(s['unevictable_bytes'], 11*1024)
        self.assertEqual(s['meminfo_bytes']['MemAvailable'], 60*1024)

    def test_driver_meminfo_preserved_without_double_count(self):
        s = c.parse_meminfo('MemTotal: 100 kB\nMemAvailable: 60 kB\nCommitted_AS: 200 kB\nMlocked: 10 kB\nUnevictable: 11 kB\nGPUActive: 30 kB\nGPUReclaim: 2 kB\n')
        self.assertEqual(s['meminfo_bytes']['GPUActive'], 30*1024)
        self.assertEqual(s['meminfo_bytes']['GPUReclaim'], 2*1024)
        self.assertEqual(s['accounted_pressure_bytes'], 40*1024)

    def test_missing_meminfo_fails(self):
        with self.assertRaises(ValueError): c.parse_meminfo('MemTotal: 12 kB\n')

    def test_proc_and_cgroup_four_ranks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); proc=root/'proc'; cg=root/'cg'/'docker-test'
            proc.mkdir(); cg.mkdir(parents=True)
            (proc/'meminfo').write_text('MemTotal: 100 kB\nMemAvailable: 60 kB\nCommitted_AS: 20 kB\nMlocked: 1 kB\nUnevictable: 2 kB\n')
            (proc/'1').mkdir(); (proc/'1'/'cgroup').write_text('0::/docker-test\n')
            (cg/'cgroup.procs').write_text('2\n3\n4\n5\n')
            (cg/'memory.current').write_text('120'); (cg/'memory.peak').write_text('140')
            (cg/'memory.stat').write_text('anon 80\nfile 40\npgfault 7\n')
            for rank in range(4):
                p=proc/str(rank+2); p.mkdir()
                (p/'comm').write_text(f'vLLM::Worker_TP{rank}')
                (p/'cmdline').write_bytes(b'python\0worker')
                (p/'status').write_text(f'VmRSS: {10+rank} kB\n')
            sampler=c.Sampler(proc, root/'cg', root/'drm'); sampler.container_pid=1
            s=sampler()
            self.assertEqual(s['worker_rss_bytes'], [10240,11264,12288,13312])
            self.assertEqual(s['cgroup_memory_current_bytes'],120)
            self.assertEqual(s['cgroup_memory_peak_bytes'],140)
            self.assertEqual(s['cgroup_memory_stat'], {'anon':80, 'file':40, 'pgfault':7})
            self.assertEqual(s['vram_free_bytes_per_rank'],[None]*4)
            (proc/'3'/'status').unlink()
            self.assertIsNone(sampler()['worker_rss_bytes'][1])
            (cg/'memory.stat').unlink()
            missing = sampler()
            self.assertIsNone(missing['cgroup_memory_stat'])
            self.assertTrue(missing['attribution_errors'])
            self.assertEqual(missing['accounted_pressure_bytes'], 40*1024)

    def test_sysfs_counter_units_and_unknowns(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for rank in range(4):
                dev=root/f'card{rank}'/'device'; dev.mkdir(parents=True)
                # Real /sys symlinks have unique PCI target names.
                actual=root/f'0000:{rank:02}:00.0'; dev.rename(actual); dev.symlink_to(actual, target_is_directory=True)
                (dev/'vendor').write_text('0x8086')
                (dev/'mem_info_vram_total').write_text(str(32*c.GIB))
                (dev/'mem_info_vram_used').write_text(str(27*c.GIB))
            self.assertEqual(c.read_vram(root)[0], [5*c.GIB]*4)
            (root/'card1/device/mem_info_vram_used').unlink()
            self.assertIsNone(c.read_vram(root)[0][1])


class RescueTests(unittest.TestCase):
    def test_pressure_is_change_not_absolute_peak(self):
        from rescue_calibration import summarize_pressure
        result=summarize_pressure('timestamp\tmem_available_kib\na\t100\nb\t40\nc\t90\n')
        self.assertEqual(result['pressure_increase_from_first_sample_bytes'],60*1024)
        self.assertEqual(result['minimum_timestamp'],'b')


class ThresholdTests(unittest.TestCase):
    def test_available_boundary(self):
        s=sample(); s['mem_available_bytes']=24*c.GIB
        self.assertIsNone(c.trip_reason(s))
        s['mem_available_bytes']-=1
        self.assertIn('24 GiB',c.trip_reason(s))

    def test_any_rank_vram_boundary(self):
        for rank in range(4):
            s=sample(); s['vram_free_bytes_per_rank'][rank]=2*c.GIB
            self.assertIsNone(c.trip_reason(s))
            s['vram_free_bytes_per_rank'][rank]-=1
            self.assertIn(f'rank {rank}',c.trip_reason(s))
        s['vram_free_bytes_per_rank']=[None]*4
        self.assertIsNone(c.trip_reason(s))

    def test_watchdog_custom_interval_one_stop(self):
        stops=[]
        with tempfile.TemporaryDirectory() as d:
            s=sample(); s['mem_available_bytes']=23*c.GIB
            w=MemoryWatchdog(d,stops.append,lambda:s,threshold=c.trip_reason,interval=.5)
            w.check(); w.check()
            self.assertEqual(len(stops),1)
            self.assertEqual(json.loads((Path(d)/'memory-watchdog-event.json').read_text())['interval_seconds'],.5)


class VerdictTests(unittest.TestCase):
    def verdict(self, rows=None, **kw):
        return c.verdict(samples() if rows is None else rows, ready=True,clean_exit=True,**kw)

    def test_pass_and_peak_accounting(self):
        v=self.verdict()
        self.assertTrue(v['passed'],v)
        self.assertEqual(v['plateau_plus_15_percent_bytes'],80_500_000_000)
        self.assertEqual(v['phase_peaks']['plateau']['accounted_pressure_bytes'],70_000_000_000)

    def test_margin_and_boundary(self):
        rows=samples(); rows[5]['accounted_pressure_bytes']=78_260_869_565
        self.assertTrue(self.verdict(rows)['passed'])
        rows[5]['accounted_pressure_bytes']+=1
        self.assertFalse(self.verdict(rows)['passed'])

    def test_no_plateau_or_short_plateau(self):
        self.assertFalse(self.verdict([])['passed'])
        self.assertFalse(self.verdict(samples()[:-1])['passed'])

    def test_loading_peak_is_not_hidden(self):
        rows=samples(); rows[0]['accounted_pressure_bytes']=c.HOST_LIMIT+1
        self.assertFalse(self.verdict(rows)['passed'])

    def test_unknown_or_low_vram_any_phase_refuses(self):
        for value in (None,4*c.GIB-1):
            for i in (0,10):
                rows=samples(); rows[i]['vram_free_bytes_per_rank'][2]=value
                self.assertFalse(self.verdict(rows)['passed'])

    def test_incomplete_worker_or_cgroup_refuses(self):
        rows=samples(); rows[10]['worker_rss_bytes'][2]=None
        self.assertFalse(self.verdict(rows)['passed'])
        rows=samples(); rows[10]['cgroup_memory_current_bytes']=None
        self.assertFalse(self.verdict(rows)['passed'])

    def test_sampling_gap_refuses(self):
        rows=samples(); rows[4]['monotonic']=-10
        self.assertFalse(self.verdict(rows)['passed'])

    def test_stop_or_unclean_refuses(self):
        self.assertFalse(self.verdict(watchdog_reason='trip')['passed'])
        self.assertFalse(self.verdict(failure='fault')['passed'])
        self.assertFalse(c.verdict(samples(),ready=True,clean_exit=False)['passed'])

    def test_receipt_recomputed_and_hash_bound(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); raw=root/'host-memory-samples.jsonl'; raw.write_text(''.join(json.dumps(s)+'\n' for s in samples()))
            receipt=dict(schema='neural.download.screen1b-calibration-load.v1',identity={'x':1},
                         generation_requests=0,ready=True,clean_exit=True,watchdog_reason=None,
                         failure=None,samples_sha256=c.file_hash(raw),verdict={'passed':False})
            path=root/'calibration-load.json'; path.write_text(json.dumps(receipt))
            self.assertTrue(c.enforce_receipt(path,{'x':1})['passed'])
            with self.assertRaisesRegex(RuntimeError,'identity'): c.enforce_receipt(path,{'x':2})
            raw.write_text(raw.read_text()+'\n')
            with self.assertRaisesRegex(RuntimeError,'hash'): c.enforce_receipt(path,{'x':1})


class ControllerTests(unittest.TestCase):
    def test_launch_identical_to_mtp1(self):
        run=Path('/tmp/fixture')
        self.assertEqual(screen.launch(SimpleNamespace(mode='calibrate-load',port=19988),run),
                         screen.launch(SimpleNamespace(mode='mtp1',port=19988),run))

    def test_calibration_preflight_bypasses_prediction_only(self):
        args=SimpleNamespace(mode='calibrate-load',port=19988,run_dir=Path('/tmp/fixture'))
        with patch.object(screen.socket,'gethostname',return_value='steve-b70s'), \
             patch.object(screen,'call',return_value=SimpleNamespace(stdout='main')), \
             patch.object(screen,'storage'), patch.object(screen,'overlay_check'), \
             patch.object(screen,'memory_prediction',return_value={'refusal_reasons':['unknown']}), \
             patch.object(screen,'enforce_prediction') as gate, \
             patch.object(screen,'idle') as idle,patch.object(screen,'journal',return_value='clean'), \
             patch.object(screen.socket,'socket'),patch.object(c,'parse_meminfo',return_value=sample()), \
             contextlib.redirect_stdout(io.StringIO()):
            screen.preflight(args,True)
            gate.assert_not_called(); idle.assert_called_once()
            args.mode='mtp1'; screen.preflight(args,True)
            gate.assert_called_once()

    def test_calibration_supervisor_zero_requests_one_sigint(self):
        self.run_load()

    def test_deferred_container_visibility_still_one_sigint(self):
        self.run_load(defer=True)

    def run_load(self, defer=False):
        args=SimpleNamespace(mode='calibrate-load',port=19988)
        commands=[]; urls=[]; clock=[0.0]; events=[]; running_probes=[0]
        class Process:
            def poll(self): return None
            def wait(self,timeout): return 0
        class Response(io.BytesIO): status=200
        def http(url,**kw):
            urls.append(url)
            return Response(b'{"data":[{"id":"qwen38-flash-next-fp8-tp4"}]}')
        def run(cmd,**kw):
            commands.append(cmd)
            out='false'
            if '{{.State.Running}}' in cmd and not any(x[:2]==['docker','kill'] for x in commands):
                running_probes[0]+=1
                out='false' if defer and running_probes[0]==1 else 'true'
            if '{{.State.Pid}}' in cmd: out='123'
            if '{{json .State}}' in cmd: out=json.dumps(dict(ExitCode=0,OOMKilled=False,Error=''))
            return SimpleNamespace(returncode=0,stdout=out,stderr='')
        def sleep(seconds): clock[0]+=seconds
        class Watchdog:
            reason=None
            def __init__(self,*a,**k): pass
            def check(self): return None
            def start(self): events.append('watchdog')
            def close(self): pass
        def popen(*a,**kw): events.append('launch'); return Process()
        with tempfile.TemporaryDirectory() as d, \
             patch.object(screen,'preflight'),patch.object(screen,'call'), \
             patch.object(screen,'collect_observations',return_value={}), \
             patch.object(screen,'MemoryWatchdog',Watchdog),patch.object(screen,'check_live'), \
             patch.object(screen,'idle'),patch.object(screen,'journal',return_value='clean'), \
             patch.object(screen.signal,'signal'),patch.object(screen.subprocess,'Popen',side_effect=popen) as launches, \
             patch.object(screen.subprocess,'run',side_effect=run), \
             patch.object(screen.urllib.request,'urlopen',side_effect=http), \
             patch.object(screen.time,'monotonic',side_effect=lambda:clock[0]), \
             patch.object(screen.time,'sleep',side_effect=sleep), \
             patch.object(screen,'write_calibration',return_value={'verdict':{'passed':True}}) as receipt:
            screen.supervise_locked(args,Path(d))
            self.assertEqual(launches.call_count,1)
            self.assertEqual(events,['watchdog','launch'])
            self.assertEqual(clock[0],22 if defer else 20)
            self.assertTrue(receipt.call_args.args[2])
            self.assertTrue(receipt.call_args.args[3])
        self.assertEqual([u.rsplit('/',1)[1] for u in urls],['health','models'])
        self.assertEqual(sum(cmd[:2]==['docker','kill'] for cmd in commands),1)
        self.assertFalse(any('SIGKILL' in str(cmd) for cmd in commands))

    def test_privileged_passthrough_worker(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'fresh'
            args=['screen.py','run','--mode','calibrate-load','--run-dir',str(path),'--execute']
            env={'SCREEN_PRIVILEGED_FD_SCAN':'1','SCREEN_SUDO_PASSWORD_FILE':'/not-read'}
            with patch.object(screen.sys,'argv',args),patch.dict(screen.os.environ,env), \
                 patch.object(screen,'preflight'),patch.object(screen,'overlay_check'), \
                 patch.object(screen,'call') as call,contextlib.redirect_stdout(io.StringIO()):
                screen.main()
                command=call.call_args.args[0]
                self.assertIn('--setenv=SCREEN_PRIVILEGED_FD_SCAN=1',command)
                self.assertIn('--setenv=SCREEN_SUDO_PASSWORD_FILE=/not-read',command)


if __name__ == '__main__': unittest.main()
