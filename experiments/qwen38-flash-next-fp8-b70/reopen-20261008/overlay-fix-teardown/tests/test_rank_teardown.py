"""No torch import: fake allocator/XPU, real signals, extracted production flow."""
import ast
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import tempfile
import threading
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
VLLM = ROOT/'copies/overlay/vllm'


def load(name):
    spec = importlib.util.spec_from_file_location('fixture_' + name, VLLM/(name+'.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def method(path, cls, name, namespace):
    tree = ast.parse((VLLM/path).read_text())
    node = next(n for c in tree.body if isinstance(c, ast.ClassDef) and c.name == cls
                for n in c.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]


class Module:
    def __init__(self, params=(), children=()):
        self.params, self.children = list(params), list(children)
    def modules(self):
        yield self
        for child in self.children:
            yield from child.modules()
    def parameters(self, recurse=False):
        return iter(self.params)


class TeardownTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, B70_SCREEN1B='1', B70_SCREEN1B_STATE_DIR=self.tmp.name)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.life = load('screen1b_teardown')
        self.guard = load('screen1b_guard')
        self.events = []
        self.torch = NS(xpu=NS(
            synchronize=lambda: self.events.append('sync'),
            empty_cache=lambda: self.events.append('device_cache'),
            is_initialized=lambda: True),
            accelerator=NS(empty_host_cache=lambda: self.events.append('host_cache')),
            empty=lambda *a, **k: 'empty_cpu')
        self.runner = NS()
        self.worker = NS(shutdown=self.shutdown_worker)
        self.proc = NS(rank=0, worker=NS(worker=self.worker, shutdown=self.shutdown_worker),
                       rpc_broadcast_mq=NS(shutdown=lambda: self.events.append('rpc_close')),
                       worker_response_mq=NS(shutdown=lambda: self.events.append('response_close')),
                       use_async_scheduling=False)

    def shutdown_worker(self):
        self.events.append('services')
        self.life.release_runner(self.runner, self.guard, self.torch,
                                 lambda: self.events.append('runtime_globals'))
        self.events.append('pools')

    def run_shutdown(self, on_failure=None):
        kw = {} if on_failure is None else dict(on_failure=on_failure)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.life.shutdown_rank(self.proc, self.guard, self.torch,
                                    lambda: self.events.append('model_parallel'),
                                    lambda: self.events.append('distributed'), **kw)
        return out.getvalue()

    def rows(self):
        return [json.loads(line) for p in Path(self.tmp.name).glob('loader-*.jsonl')
                for line in p.read_text().splitlines()]

    def test_full_order_and_timestamp_receipt(self):
        self.run_shutdown()
        self.assertEqual(self.events, ['rpc_close','response_close','services','sync',
                                      'runtime_globals','sync','sync','pools',
                                      'model_parallel','distributed','sync','device_cache',
                                      'host_cache','sync'])
        row = self.rows()[-1]
        self.assertEqual(row['event'], 'rank_teardown_complete')
        phases = ['submissions_stopped','async_output_drained','queues_closed','drained',
                  'graphs_released','expert_tables_released','uva_released','ple_closed',
                  'pinned_released','registries_cleared','worker_released',
                  'distributed_released','final_sync','device_cache_empty',
                  'host_cache_empty','post_cache_sync','complete']
        self.assertEqual(set(row['timestamps']), set(phases))
        self.assertEqual(sorted(phases,key=lambda p: row['timestamps'][p]['monotonic_ns']), phases)
        self.assertFalse(row['native_queue_destruction_verified'])
        self.assertIsNone(self.proc.worker)

    def test_expert_alias_and_owner_destruction_order(self):
        events = self.events
        class Allocation:
            def __init__(self, name): self.name = name
            def __del__(self): events.append('free:' + self.name)
        host, uva, table = Allocation('host'), Allocation('uva'), Allocation('table')
        old = NS(_q38_host_cpu=host, _q38_host_storage=uva, _q38_base_table=table)
        current = NS(_q38_host_cpu=host, _q38_host_storage=uva, _q38_base_table=table)
        layer = Module([current])
        layer._q38_placed_w13_weight = old
        self.guard.retain_module(layer)
        del host, uva, table
        self.run_shutdown()
        self.assertLess(events.index('free:table'), events.index('free:uva'))
        self.assertLess(events.index('free:uva'), events.index('free:host'))
        self.assertFalse(hasattr(layer, '_q38_placed_w13_weight'))
        for param in (old,current):
            self.assertFalse(hasattr(param, '_q38_host_cpu'))
            self.assertFalse(hasattr(param, '_q38_host_storage'))

    def test_generic_uva_data_detached_before_host(self):
        class Param:
            dtype = 'fake'
            def __init__(self):
                self._screen1b_host_storage = object()
                self._data = 'uva'
            @property
            def data(self): return self._data
            @data.setter
            def data(self, value):
                self.assert_owner = hasattr(self, '_screen1b_host_storage')
                self._data = value
        param = Param()
        self.runner.model = Module([param])
        self.run_shutdown()
        self.assertTrue(param.assert_owner)
        self.assertEqual(param.data, 'empty_cpu')
        self.assertFalse(hasattr(param, '_screen1b_host_storage'))

    def test_ple_close_before_slab_and_partial_module(self):
        embedding = Module()
        def close():
            self.assertTrue(hasattr(embedding, '_screen1b_cache_slab'))
            self.assertTrue(hasattr(embedding, '_screen1b_step_host'))
            self.events.append('ple_close')
        embedding._screen1b_cache = NS(close=close)
        embedding._screen1b_cache_slab = object()
        embedding._screen1b_step_host = object()
        embedding._screen1b_step_device = object()
        self.guard._tables[0] = Module(children=[embedding])
        self.guard._models.append(self.guard._tables[0])
        self.run_shutdown()
        self.assertIn('ple_close', self.events)
        self.assertEqual(self.guard._tables, {})
        self.assertEqual(self.guard._models, [])
        self.assertFalse(hasattr(embedding, '_screen1b_cache_slab'))

    def test_partial_no_worker_still_records_release(self):
        self.proc.worker = None
        self.run_shutdown()
        self.assertIn('registries_cleared', self.rows()[-1]['timestamps'])

    def test_idempotent_release(self):
        self.run_shutdown()
        first = list(self.events)
        self.run_shutdown()
        self.assertEqual(first,self.events)
        self.assertEqual(sum(r['event']=='rank_teardown_complete' for r in self.rows()),1)

    def test_pre_device_init_cannot_claim_native_completion(self):
        self.torch.xpu.is_initialized = lambda: False
        self.run_shutdown()
        self.assertEqual(self.events, [])
        self.assertEqual(self.rows()[-1]['event'],'rank_teardown_uninitialized')

    def test_each_release_failure_never_reaches_later_phases(self):
        for failing in ('sync','device_cache','host_cache','distributed','pools'):
            with self.subTest(failing=failing):
                self.life._complete = self.life._releasing = False
                self.life._timestamps.clear()
                self.events.clear()
                self.proc.worker = NS(worker=object(),shutdown=lambda: None)
                self.proc.rpc_broadcast_mq = self.proc.worker_response_mq = None
                errors=[]
                def fail(): raise RuntimeError(failing)
                with patch.object(self.torch.xpu,'synchronize',fail if failing=='sync' else lambda: None), \
                     patch.object(self.torch.xpu,'empty_cache',fail if failing=='device_cache' else lambda: None), \
                     patch.object(self.torch.accelerator,'empty_host_cache',fail if failing=='host_cache' else lambda: None):
                    if failing == 'pools': self.proc.worker.shutdown = fail
                    self.life.shutdown_rank(self.proc,self.guard,self.torch,lambda:None,
                        fail if failing=='distributed' else lambda:None,
                        on_failure=lambda g,r,e:errors.append(str(e)))
                self.assertEqual(errors,[failing])
                self.assertFalse(self.life._complete)
                self.assertNotIn('complete',self.life._timestamps)

    def test_close_failure_preserves_pinned_owners(self):
        embedding=Module()
        def fail(): raise BufferError('exported view')
        embedding._screen1b_cache = NS(close=fail)
        embedding._screen1b_cache_slab = object()
        self.guard._owned_modules.append(embedding)
        failures=[]
        self.run_shutdown(lambda *a:failures.append(a))
        self.assertTrue(failures)
        self.assertTrue(hasattr(embedding,'_screen1b_cache_slab'))
        self.assertNotIn('host_cache',self.events)

    def test_async_mode_refuses_instead_of_destroying_live_output(self):
        self.proc.use_async_scheduling=True
        failures=[]
        self.run_shutdown(lambda *a:failures.append(a))
        self.assertTrue(failures)
        self.assertEqual(self.events,[])

    def test_actual_signals_only_latch_even_during_release(self):
        old={sig:signal.signal(sig,self.guard.signal_stop) for sig in (signal.SIGINT,signal.SIGTERM)}
        try:
            for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGINT):
                signal.raise_signal(sig)
            self.assertTrue(self.guard.stop_requested())
            self.assertEqual(self.events,[])
            self.assertFalse((Path(self.tmp.name)/'STOP').exists())
            self.torch.xpu.empty_cache=lambda:signal.raise_signal(signal.SIGTERM)
            self.run_shutdown()
            self.assertTrue(self.life._complete)
        finally:
            for sig,handler in old.items():signal.signal(sig,handler)

    def test_failed_diagnostics_still_park(self):
        parked=[]
        def fail(*args, **kw): raise OSError('receipt filesystem failed')
        for target in ('request_stop', 'receipt'):
            with patch.object(self.guard,target,fail), \
                 patch.object(self.life.threading,'Event',return_value=NS(wait=lambda:parked.append(target))):
                with self.assertRaises(OSError):
                    self.life.preserve_failure(self.guard,0,RuntimeError('release failed'))
        self.assertEqual(parked,['request_stop','receipt'])

    def test_clock_cache_close_is_repeatable_and_releases_view(self):
        ple=load('screen1b_ple')
        closed=[]
        store=NS(width=2,end=2,start=0,close=lambda:closed.append('mmap'))
        slab=bytearray(8)
        cache=ple.ClockCache(store,slab)
        cache.close(); cache.close()
        slab.extend(b'x')  # BufferError if a memoryview still exports slab
        self.assertIsNone(cache.buffer)
        self.assertIsNone(cache.row2slot)
        self.assertEqual(closed,['mmap','mmap'])

    def test_cooperative_rpc_finishes_before_shutdown(self):
        busy=method(Path('v1/executor/multiproc_executor.py'),'WorkerProc','worker_busy_loop',{'_s1b':self.guard})
        def rpc(request):
            self.events.append('rpc_enter')
            self.guard.signal_stop(signal.SIGINT,None)
            self.events.append('rpc_return')
        proc=NS(rpc_broadcast_mq=NS(dequeue=lambda **kw:('work',)),_execute_worker_rpc=rpc)
        busy(proc)
        self.run_shutdown()
        self.assertLess(self.events.index('rpc_return'),self.events.index('services'))

    def test_parent_waits_after_warning_without_terminate(self):
        class Process:
            pid=999999
            joins=0
            def is_alive(self):return self.joins<3
            def join(self,timeout):self.joins+=1
            def kill(self):raise AssertionError('kill forbidden')
            def terminate(self):raise AssertionError('terminate forbidden')
        proc=Process()
        with patch.object(self.guard,'WAIT_SECONDS',-1):
            self.guard.wait_processes([proc])
        self.assertEqual(proc.joins,3)
        self.assertTrue(any(r['event']=='drain_needs_owner' for r in self.rows()))
        self.assertEqual(self.rows()[-1]['event'],'children_drained')

    def test_failure_parks_without_retry(self):
        wait=[]
        with patch.object(self.life.threading,'Event',return_value=NS(wait=lambda:wait.append('park'))):
            self.life.preserve_failure(self.guard,0,RuntimeError('drain failed'))
        self.assertEqual(wait,['park'])
        self.assertEqual(self.rows()[-1]['event'],'rank_teardown_failed')



class WorkerMainRehearsal(TeardownTests):
    # Only new methods: inherited unit checks live on TeardownTests once.
    def rehearsal(self, rank=0, failure=None, broken_pipe=False):
        outer=self
        callbacks=[]
        self.guard._cancelled = False
        (Path(self.tmp.name)/'STOP').unlink(missing_ok=True)
        class FixtureWorker:
            READY_STR='READY'
            def __init__(self,*args,**kwargs):
                self.rank=rank
                self.use_async_scheduling=False
                self.worker=NS(worker=outer.worker,shutdown=outer.shutdown_worker)
                self.rpc_broadcast_mq=None
                self.worker_response_mq=NS(export_handle=lambda:None,wait_until_ready=lambda:None,
                    shutdown=lambda:outer.events.append('response_close'))
                self.peer_response_handles=[]
                if failure=='partial':
                    outer.events.append('injected:partial')
                    raise RuntimeError('partial load')
            def worker_busy_loop(self):
                if failure:
                    outer.events.append('injected:' + failure)
                if failure=='keyboard':raise KeyboardInterrupt()
                if failure=='systemexit':raise SystemExit(0)
                if failure=='rpc':raise ValueError('RPC failure')
                signal.raise_signal(signal.SIGINT)
                signal.raise_signal(signal.SIGTERM)
                outer.events.append('rpc_unwound')
            def shutdown(self):
                outer.proc=self
                outer.run_shutdown()
        config=NS(parallel_config=NS(assigned_physical_gpu_ids=None,numa_bind=False))
        def close():
            if broken_pipe:raise OSError('pipe already closed')
        pipe=NS(send=lambda v:None,close=close)
        logger=NS(exception=lambda *a:None,debug_once=lambda *a:None,warning=lambda *a:None)
        ns=dict(_s1b=self.guard,threading=threading,signal=signal,os=os,time=time,
                set_worker_net_device=lambda *a:None,maybe_init_worker_tracer=lambda **kw:None,
                WorkerProc=FixtureWorker,logger=logger,
                Thread=lambda **kw:NS(start=lambda:callbacks.append(kw['target'])))
        main=method(Path('v1/executor/multiproc_executor.py'),'WorkerProc','worker_main',ns)
        old={sig:signal.getsignal(sig) for sig in (signal.SIGINT,signal.SIGTERM)}
        try:
            main(vllm_config=config,rank=rank,ready_pipe=pipe,death_pipe=None)
        finally:
            for sig,handler in old.items():signal.signal(sig,handler)
        self.assertEqual(self.rows()[-1]['event'],'rank_teardown_complete')
        self.assertEqual(self.rows()[-1]['rank'],rank)
        if failure:
            self.assertIn('injected:' + failure, self.events)
        return callbacks

    def test_four_rank_fixture_worker_main(self):
        for rank in range(4):
            self.life._timestamps.clear()
            self.life._complete=self.life._releasing=False
            self.runner=NS()
            self.rehearsal(rank)
        complete=[r for r in self.rows() if r['event']=='rank_teardown_complete']
        self.assertEqual([r['rank'] for r in complete],[0,1,2,3])

    def test_partial_load_and_exception_scope_unwind(self):
        for failure in ('partial','keyboard','systemexit','rpc'):
            with self.subTest(failure=failure):
                self.life._timestamps.clear()
                self.life._complete=self.life._releasing=False
                self.runner=NS()
                self.rehearsal(failure=failure)

    def test_broken_ready_pipe_does_not_skip_cleanup(self):
        self.rehearsal(broken_pipe=True)

    def test_idle_signal_observer_closes_queues(self):
        callbacks=self.rehearsal()
        queue=[]
        self.proc.rpc_broadcast_mq=NS(shutdown=lambda:queue.append('wake_dequeue'))
        callbacks[0]()
        self.assertEqual(queue,['wake_dequeue'])

# Do not duplicate base checks in the subclass's discovery.
for _name in tuple(vars(TeardownTests)):
    if _name.startswith('test_'):
        setattr(WorkerMainRehearsal, _name, None)


class ParentConcurrencyTests(unittest.TestCase):
    def test_main_cannot_return_while_monitor_waits_for_child(self):
        life=load('screen1b_teardown')
        entered,release,second_started,second_done=(threading.Event() for _ in range(4))
        events=[]
        guard=NS(request_stop=lambda r:None,
                 wait_processes=lambda p:(entered.set(),release.wait(),events.append('children_done')))
        executor=NS(_screen1b_shutdown_lock=threading.RLock(),_screen1b_shutdown_complete=False,
                    workers=[NS(proc=object(),death_writer=NS(close=lambda:None),
                                worker_response_mq=NS(shutdown=lambda:events.append('response_close')))])
        def monitor():life.shutdown_executor(executor,guard)
        def main():
            second_started.set()
            life.shutdown_executor(executor,guard)
            events.append('main_return');second_done.set()
        first=threading.Thread(target=monitor);second=threading.Thread(target=main)
        first.start();self.assertTrue(entered.wait(2));second.start()
        try:
            self.assertTrue(second_started.wait(2))
            self.assertFalse(second_done.wait(.05))
        finally:
            release.set();first.join(2);second.join(2)
        self.assertEqual(events,['children_done','response_close','main_return'])

    def test_parent_wait_failure_preserves_instead_of_claiming_done(self):
        life=load('screen1b_teardown');failures=[]
        def fail(*a):raise OSError('lost process observation')
        guard=NS(request_stop=lambda r:None,wait_processes=fail)
        executor=NS(_screen1b_shutdown_lock=threading.RLock(),_screen1b_shutdown_complete=False,workers=[])
        life.shutdown_executor(executor,guard,on_failure=lambda *a:failures.append(a))
        self.assertEqual(len(failures),1)
        self.assertFalse(executor._screen1b_shutdown_complete)


class StartupParentTests(unittest.TestCase):
    def test_failed_startup_pipe_close_cannot_skip_child_wait(self):
        path=VLLM/'v1/executor/multiproc_executor.py'
        tree=ast.parse(path.read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='MultiprocExecutor')
        init=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_init_executor')
        cleanup=next(n.finalbody for n in init.body if isinstance(n,ast.Try) and n.finalbody)
        def broken():raise OSError('broken death pipe')
        procs=[object(),object()];waited=[]
        workers=[NS(proc=p,death_writer=NS(close=broken)) for p in procs]
        ns=dict(success=False,unready_workers=workers,_s1b=NS(enabled=lambda:True),
                self=NS(_ensure_worker_termination=lambda p:waited.extend(p)))
        exec(compile(ast.Module(body=cleanup,type_ignores=[]),str(path),'exec'),ns)
        self.assertEqual(waited,procs)
        self.assertTrue(all(w.death_writer is None for w in workers))

if __name__=="__main__":unittest.main()
