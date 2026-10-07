"""Pinned-source and synthetic execution tests; never import Torch or run a device."""
import ast
import copy
import importlib.util
from contextlib import nullcontext
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest.mock import Mock, patch

import overlay as O

_trace_spec = importlib.util.spec_from_file_location('sparse107_trace_under_test', Path(__file__).with_name('trace.py'))
T = importlib.util.module_from_spec(_trace_spec)
_trace_spec.loader.exec_module(T)

PACKET = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-sampler-accounting-106')


def definition(raw, name, cls=None):
    body = ast.parse(raw).body
    if cls:
        body = next(n for n in body if isinstance(n, ast.ClassDef) and n.name == cls).body
    return next(n for n in body if isinstance(n, ast.FunctionDef) and n.name == name)


def execute(node, env):
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<synthetic overlay>', 'exec'), env)
    return env[node.name]


class Tensor:
    def __init__(self, device='xpu:0', count=6, name='input', error=False):
        self.device, self.shape, self.dtype = device, (count,), 'float32'
        self.name, self.error = name, error

    def numel(self):
        return self.shape[0]

    def element_size(self):
        return 4


class OverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {p:(PACKET/p).read_bytes() for p in O.SOURCE_SHAS}
        cls.result = O.transform_sources(cls.sources)

    def test_exact_inputs_only_and_repeatable(self):
        self.assertEqual(O.transform_sources(self.sources),self.result)
        for value in ({}, {**self.sources,'extra':b'bad'}, {**self.sources,O.GRAPH:b'changed'}):
            with self.assertRaises(ValueError):
                O.transform_sources(value)
        with self.assertRaises(ValueError):
            O.transform_sources(self.result)

    def test_anchor_refuses_drift(self):
        with self.assertRaisesRegex(ValueError,'anchor'):
            O.replace_once('xx','x','y')

    def test_original_sample_body_byte_semantics_preserved(self):
        before=definition(self.sources[O.SAMPLER],'sample_clip')
        after=definition(self.result[O.SAMPLER],'_sample_clip107_body')
        after=copy.deepcopy(after);after.name='sample_clip'
        self.assertEqual(ast.dump(before),ast.dump(after))
        self.assertEqual(ast.dump(before.args),ast.dump(definition(self.result[O.SAMPLER],'sample_clip').args))

    def test_capture_static_cache_and_batch_bodies_unchanged(self):
        for name,cls in [('static_like',None),('fill_static',None),('_staged_cached',None),
                         ('_capture','GraphBlockRoute'),('__call__','PassthroughRoute')]:
            self.assertEqual(ast.dump(definition(self.sources[O.GRAPH],name,cls)),
                             ast.dump(definition(self.result[O.GRAPH],name,cls)))
        for name in ('sample_batch','sample_clip_original'):
            self.assertEqual(ast.dump(definition(self.sources[O.SAMPLER],name)),
                             ast.dump(definition(self.result[O.SAMPLER],name)))

    def test_no_numerical_copy_allocation_replay_or_sync_call_delta(self):
        wanted={'host.copy_','out.copy_','torch.empty','event.synchronize','event.record',
                'fill_static','entry.graph.replay','st.synchronize','torch.xpu.synchronize'}
        for path in O.SOURCE_SHAS:
            def calls(raw):
                return [ast.dump(n) for n in ast.walk(ast.parse(raw))
                        if isinstance(n,ast.Call) and ast.unparse(n.func) in wanted]
            self.assertEqual(calls(self.sources[path]),calls(self.result[path]))

    def staged(self, recording=True, copy_error=False, sync_error=False):
        log=[]
        class Buffer(Tensor):
            def copy_(self,value,**kwargs):
                log.append(self.name+'.copy')
                if copy_error:
                    raise RuntimeError('original-copy-error')
        class Event:
            def __init__(self):log.append('original.event.new')
            def record(self,stream):log.append('original.event.record')
            def synchronize(self):
                log.append('original.event.synchronize')
                if sync_error:raise RuntimeError('original-sync-error')
        class Job:
            def __getattr__(self,name):
                def hook(*args):
                    log.append(name)
                    if name=='move_begin':return object()
                return hook
        job=Job();job.recording=recording
        torch=types.SimpleNamespace(Tensor=Tensor,xpu=types.SimpleNamespace(
            device=lambda d:nullcontext(),stream=lambda s:nullcontext(),Event=Event))
        def empty(*args,**kwargs):
            log.append('original.empty');return Buffer('xpu:1',name='out')
        torch.empty=empty
        env={'torch':torch,'thread_stream':lambda d:d,
             '_pinned':lambda *args:Buffer('cpu',name='host'),
             '_transport107':types.SimpleNamespace(current=lambda:job)}
        return execute(definition(self.result[O.GRAPH],'staged_move'),env),log

    def test_transfer_brackets_preserve_existing_operation_order(self):
        fn,log=self.staged();result=fn(Tensor(),'xpu:1',('img',0))
        self.assertEqual(result.device,'xpu:1')
        self.assertEqual(log,['move_begin','host.copy','move_d2h_end','original.event.new',
            'original.event.record','wait_begin','original.event.synchronize','wait_end',
            'move_alloc_begin','original.empty','move_alloc_end','move_h2d_begin','out.copy','move_end'])

    def test_disabled_transfer_has_no_trace_calls(self):
        fn,log=self.staged(recording=False);fn(Tensor(),'xpu:1',('img',0))
        self.assertEqual(log,['host.copy','original.event.new','original.event.record',
                              'original.event.synchronize','original.empty','out.copy'])

    def test_noop_transfer_does_not_observe_or_allocate(self):
        fn,log=self.staged();v=Tensor()
        self.assertIs(fn(v,'xpu:0',('img',0)),v)
        self.assertIs(fn(None,'xpu:1',('img',0)),None)
        self.assertEqual(log,[])

    def test_original_transfer_errors_are_not_retried_or_swallowed(self):
        for kwargs,message in [({'copy_error':True},'original-copy-error'),({'sync_error':True},'original-sync-error')]:
            fn,log=self.staged(**kwargs)
            with self.assertRaisesRegex(RuntimeError,message):fn(Tensor(),'xpu:1',('img',0))
            self.assertNotIn('move_end',log)
            self.assertNotIn('original.empty',log)

    def test_fill_pairs_only_nonempty_and_counts_expanded_owned_core(self):
        fn_node=definition(self.result[O.GRAPH],'fill','DeviceGroup')
        a,b,c=Tensor(name='a'),Tensor(count=100,name='b'),Tensor(name='c')
        b._graph_fill_target=Tensor(count=2)
        va,vb,vc=Tensor(),Tensor(),c
        log=[]
        job=types.SimpleNamespace(recording=True,fill_begin=lambda *x:log.append('begin') or 'token',
            fill_add=lambda token,n:log.append(('bytes',n)),fill_end=lambda *x:log.append('end'))
        def walk(value,out,*args):
            if value is not None:out.extend(value if isinstance(value,list) else [value])
        env={'_transport107':types.SimpleNamespace(current=lambda:job),'walk':walk,'KEYWORDS':(),
             'split_options':lambda x:({},None),'require':O.require,'thread_stream':lambda d:d,
             'fill_static':lambda buf,val:log.append(('copy',buf.name))}
        fn=execute(fn_node,env);slot=types.SimpleNamespace(flat=[a,b,c],sources=[va,None,None])
        self.assertEqual(fn(types.SimpleNamespace(device='xpu:1'),slot,{'img':[va,vb,vc]},{}),1)
        self.assertEqual(log,['begin',('bytes',8),('copy','b'),'end'])
        log.clear();self.assertEqual(fn(types.SimpleNamespace(device='xpu:1'),slot,{'img':[va,vb,vc]},{}),0)
        self.assertEqual(log,[])

    def test_stage_hooks_before_original_sampler_calls_only(self):
        body=definition(self.result[O.SAMPLER],'_sample_chain').body
        for stage in ('a','b'):
            sampler=next(i for i,n in enumerate(body) if isinstance(n,ast.Assign) and
                         isinstance(n.targets[0],ast.Name) and n.targets[0].id=='stage_'+stage)
            self.assertEqual(ast.unparse(body[sampler-1]),"_transport107.current().stage('%s')"%stage)
            self.assertEqual(ast.unparse(body[sampler-2]),"lean.set_stage('%s')"%stage)

    def test_forward_marker_precedes_image_routing(self):
        node=definition(self.result[O.GRAPH],'__call__','GraphBlockRoute')
        src=ast.unparse(node)
        self.assertLess(src.index('.block_enter('),src.index('for k, v in args.items():'))
        self.assertLess(src.index('if not pipelined_enabled():'),src.index('.block_enter('))

    def test_wrapper_preserves_original_failure_and_clears(self):
        log=[]
        job=types.SimpleNamespace(finish_after_existing_drains=lambda success:log.append(('finish',success)) or {'ok':True})
        def body(*args,**kw):log.append('body-drained');return 'unchanged-result'
        env={'_transport107_begin_job':lambda i:job,'_sample_clip107_body':body,
             '_transport107':types.SimpleNamespace(clear=lambda:log.append('clear')),
             'pipeline':types.SimpleNamespace(record_fingerprint=lambda *x:log.append('persist'))}
        fn=execute(definition(self.result[O.SAMPLER],'sample_clip'),env)
        self.assertEqual(fn(*range(13)),'unchanged-result')
        self.assertEqual(log,['body-drained',('finish',True),'persist','clear'])
        log.clear();error=RuntimeError('original failure')
        def fail(*a,**k):raise error
        env['_sample_clip107_body']=fail
        with self.assertRaises(RuntimeError) as caught:fn(*range(13))
        self.assertIs(caught.exception,error);self.assertEqual(log,['clear'])
        log.clear();env['_transport107_begin_job']=fail
        with self.assertRaises(RuntimeError) as caught:fn(*range(13))
        self.assertIs(caught.exception,error);self.assertEqual(log,['clear'])

    def test_worker_binding_uses_registered_object_not_even_clip_parity(self):
        current=types.SimpleNamespace(ident=222,name='ltx-sample-1',is_alive=lambda:True)
        other=types.SimpleNamespace(ident=111,name='ltx-sample-0',is_alive=lambda:True)
        meta={'halted':False,'phase':'optimized_preparation',**{k:'a'*64 for k in
            ('plan_sha256','runtime_manifest_sha256','server_identity_sha256','qualification_id')}}
        session=types.SimpleNamespace(auxiliary_metadata=lambda:meta,
            _authority=types.SimpleNamespace(plan={'requests':[{'clip_index':99907104,'phase':'candidate-check'}]}))
        trace=types.SimpleNamespace(configure=Mock(),begin_job=Mock(return_value='job'))
        env={'_transport107_threading':types.SimpleNamespace(current_thread=lambda:current,get_ident=lambda:222),
             'pipeline':types.SimpleNamespace(_LOCK=threading.Lock(),_STAGES={'sample':{'workers':[other,current]}}),
             '_transport107_setup_lock':threading.Lock(),'_transport107':trace,
             '_transport107_event':object(),'require':O.require}
        fn=execute(definition(self.result[O.SAMPLER],'_transport107_begin_job'),env)
        with patch.dict(sys.modules,{'ltx_resolution_session':session}):
            self.assertEqual(fn(99907104),'job')
            trace.begin_job.assert_called_once_with(99907104,1,'candidate-check')
            meta['phase']='timing'
            with self.assertRaisesRegex(ValueError,'authority phase'):fn(99907104)
            meta['phase']='optimized_preparation'
            current.ident=333
            with self.assertRaisesRegex(ValueError,'registered owning'):fn(99907104)

    def test_real_helper_with_transformed_fill_move_and_replay_routes(self):
        class Buffer(Tensor):
            def copy_(self,value,**kwargs):return self
        class Event:
            def record(self,stream):pass
            def synchronize(self):pass  # Only original staged_move completion event uses this.
            def elapsed_time(self,other):return 0.25
        streams={d:types.SimpleNamespace(device=d) for d in ('xpu:0','xpu:1')}
        torch=types.SimpleNamespace(Tensor=Tensor,empty=lambda shape,dtype,device:Buffer(device,shape[0]),
            xpu=types.SimpleNamespace(device=lambda d:nullcontext(),stream=lambda s:nullcontext(),Event=Event))
        manager=T.TraceManager({0:{'ident':111,'name':'ltx-sample-0'},1:{'ident':222,'name':'ltx-sample-1'}},
            lambda d:Event(),{k:'a'*64 for k in ('plan_sha256','server_identity_sha256','source_sha256')},
            thread_info=lambda:(111,'ltx-sample-0'))
        job=manager.begin_job(99907104,0,'candidate-check')
        env={'torch':torch,'_transport107':types.SimpleNamespace(current=manager.current),
             'threading':threading,'thread_stream':lambda d:streams[str(d)],'pipelined_enabled':lambda:True,
             '_pinned':lambda shape,dtype,tag:Buffer('cpu',shape[0]),'KEYWORDS':(),'CACHE_KEY':'cache',
             'split_options':lambda options:({},None),'require':O.require,
             'fill_static':lambda buf,value:buf.copy_(value),'busy_begin':lambda d:None,'busy_end':lambda *a:None,
             'MAX_SIGNATURES_PER_BLOCK':2,
             'CAPTURE_LOCK':types.SimpleNamespace(acquire_shared=lambda:None,release_shared=lambda:None)}
        def walk(value,out,*args):
            if value is not None:out.extend(value if isinstance(value,(tuple,list)) else [value])
        env['walk']=walk
        execute(definition(self.result[O.GRAPH],'staged_move'),env)
        fill=execute(definition(self.result[O.GRAPH],'fill','DeviceGroup'),env)
        cls=ast.ClassDef(name='GraphRoute',bases=[],keywords=[],body=[
            definition(self.result[O.GRAPH],'_call_native','GraphBlockRoute'),
            definition(self.result[O.GRAPH],'__call__','GraphBlockRoute')],decorator_list=[])
        tree=ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[]))
        exec(compile(tree,'<transformed route>','exec'),env)
        groups={}
        for device in streams:
            flat=[Buffer(device),Buffer(device)]
            slot=types.SimpleNamespace(flat=flat,sources=[None,None])
            group=types.SimpleNamespace(device=device,fresh_forward=False,key_for=lambda *a:'key',
                                        slot_for=lambda *a,slot=slot:slot)
            group.fill=types.MethodType(fill,group);groups[device]=(group,flat)
        routes=[]
        for index in range(48):
            device='xpu:0' if index<23 else 'xpu:1';group,flat=groups[device]
            route=env['GraphRoute']();route.index=index;route.device=device;route.blocks=[None]
            route.original_route=types.SimpleNamespace(device=device,primary='xpu:0',last=index==47)
            entry=types.SimpleNamespace(graph=types.SimpleNamespace(replay=lambda:None),
                                        out_vx=flat[0],out_ax=flat[1],replays=0)
            route.registry=types.SimpleNamespace(for_device=lambda d:groups[d][0])
            route.entries={threading.get_ident():{'key':entry}}
            route.report=types.SimpleNamespace(first_options={},copies=0,replays=0)
            route._validate_fast=lambda:None;route._validate=lambda:None;routes.append(route)
        for stage in ('a','b'):
            job.stage(stage)
            for forward in range(3):
                img=(Buffer(),Buffer())
                for route in routes:
                    img=route({'img':img,'transformer_options':{'cache':{}}},{})['img']
        receipt=job.finish_after_existing_drains(True);manager.clear()
        self.assertTrue(receipt['valid'],receipt['error'])
        self.assertEqual(receipt['coverage'],{stage:{'blocks':48,'replays':48,'moves':4,'partitions':2} for stage in ('a','b')})
        self.assertEqual(sum(op['kind']=='move' for op in receipt['operations']),8)
        self.assertEqual(sum(op['kind']=='partition' for op in receipt['operations']),4)
        self.assertTrue(all(op['forward_ordinal']==2 for op in receipt['operations']))
        self.assertLessEqual(receipt['operation_count'],108)
        self.assertLessEqual(receipt['events_recorded'],232)


if __name__ == '__main__':
    unittest.main()
