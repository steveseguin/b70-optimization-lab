#!/usr/bin/env python3
"""Packet 98 CPU tests. No server, checkpoint, real XPU API or accelerator tensor.
Run with the baseline Python -B. Temporary fixtures live under /tmp only.
"""
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ltx_output_size_98 as geometry
R = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
P97 = R / 'prepared-encoder-place-97'
P98 = R / 'prepared-encoder-size-98'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def function(path, name, namespace):
    tree = ast.parse(path.read_text())
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]


class Packet98(unittest.TestCase):
    def test_allowlist_and_read_once(self):
        self.assertEqual(geometry.OUTPUT_SIZE, '256x256')
        for size, tokens in [('256x256',[64,256]),('512x320',[160,640]),('640x384',[240,960])]:
            with unittest.mock.patch.dict(os.environ, LTX_OUTPUT_SIZE=size):
                m=load('size_'+size,HERE/'ltx_output_size_98.py')
            self.assertEqual(list(m.TOKENS),tokens)
            self.assertEqual(m.OUTPUT_SIZE,size)
            m.admit_arm(size,True)
            if size!='256x256':
                with self.assertRaises(RuntimeError):m.admit_arm(size,False)
                with self.assertRaises(RuntimeError):m.admit_arm()
        for bad in ('','640x360','256X256','512x512','640x384 '):
            with unittest.mock.patch.dict(os.environ,LTX_OUTPUT_SIZE=bad):
                with self.assertRaises(ValueError):load('bad',HERE/'ltx_output_size_98.py')

    def test_default_graph_bytes(self):
        for path in (P97/'graphs').glob('*.json'):
            self.assertEqual(path.read_bytes(),(P98/'graphs'/path.name).read_bytes(),path.name)

    def test_manifest_semantics_and_inventory(self):
        a=json.loads((P97/'manifest.json').read_text());b=json.loads((P98/'manifest.json').read_text())
        def normalize(v):
            if isinstance(v,dict):return {k:normalize(x) for k,x in v.items()}
            if isinstance(v,list):return [normalize(x) for x in v]
            if isinstance(v,str) and len(v)==64 and all(c in '0123456789abcdef' for c in v):return '<sha>'
            return v
        for k in a:
            if k not in ('files','extension_sha256s','startup_tools','preparer_sha256'):
                self.assertEqual(normalize(a[k]),normalize(b[k]),k)
        for p,d in b['files'].items():self.assertEqual(hashlib.sha256((P98/p).read_bytes()).hexdigest(),d,p)
        self.assertEqual(set(b['extension_sha256s'])-set(a['extension_sha256s']),{'ltx_output_size_98.py'})

    def test_every_sized_graph(self):
        builder=load('builder',HERE/'prepare-output-size-98.py')
        m=json.loads((P98/'manifest.json').read_text())
        arms=m['output_size']['speed_arms'];self.assertEqual(len(arms),45)
        for arm,row in arms.items():
            base=json.loads((P97/f"graphs/graph-capture-all48-{row['base']}.json").read_text())
            g=json.loads((P98/f'graphs/graph-capture-all48-{arm}.json').read_text())
            self.assertEqual(g,builder.speed_graph(base,row['size']))
            w,h=geometry.dimensions(row['size']);self.assertEqual(g['356']['inputs']['width'],w//2)
            self.assertEqual(g['356']['inputs']['height'],h//2)
            for key in ('364','428','426'):self.assertTrue(g[key]['inputs']['speed_only'])

    def test_shapes_and_tokens(self):
        for size in geometry.SIZES:
            w,h=geometry.dimensions(size)
            for batch in (1,2,4):
                a=geometry.latent_shape(1,batch,size);b=geometry.latent_shape(2,batch,size)
                self.assertEqual(a,(batch,128,4,h//64,w//64))
                self.assertEqual(b,(batch,128,4,2*a[-2],2*a[-1]))
            self.assertEqual(geometry.image_shape(size),(25,h,w,3))
        # Upsampler, sentry and batch helper are the unchanged shape-derived implementations.
        for name in ('ltx_graph_upsampler.py','ltx_lean_conditioning.py','ltx_sampler_batch.py'):
            self.assertEqual((P97/'source/scripts'/name).read_bytes(),(P98/'source/scripts'/name).read_bytes())

    def test_slot_real_constructor(self):
        with unittest.mock.patch.dict(os.environ,LTX_OUTPUT_SIZE='640x384'):
            size=load('slot_size',HERE/'ltx_output_size_98.py')
        ns={'size98':size}
        ctor=function(P98/'source/scripts/ltx_graph_capture.py','__init__',ns)
        for tokens in (240,960):
            slot=types.SimpleNamespace();ctor(slot,[types.SimpleNamespace(shape=(2,tokens,4096))],{},[])
            self.assertEqual(slot.img[0].shape[1],tokens)
        with self.assertRaises(RuntimeError):ctor(types.SimpleNamespace(),[types.SimpleNamespace(shape=(1,256,4096))],{},[])
        text=(P98/'source/scripts/ltx_graph_capture.py').read_text()
        self.assertIn('MAX_SIGNATURES_PER_BLOCK = size98.MAX_SIGNATURES_PER_BLOCK',text)
        self.assertEqual(size.MAX_SIGNATURES_PER_BLOCK,8)

    def test_node_admission_before_work(self):
        with unittest.mock.patch.dict(os.environ,LTX_OUTPUT_SIZE='512x320'):
            size=load('admit_size',HERE/'ltx_output_size_98.py')
        ns={'size98':size,'_failed':False}
        path=P98/'source/scripts/pipeline_node.py'
        fn=function(path,'apply',ns)
        called=[];self_obj=types.SimpleNamespace(_apply=lambda *args:called.append(args))
        with self.assertRaises(RuntimeError):fn(self_obj,None,'x','pipeline-window',0,2,'name')
        self.assertEqual(called,[])
        fn(self_obj,None,'x','pipeline-window',0,2,'name','512x320',True)
        self.assertEqual(len(called),1)

    def test_receipts_and_chain_budget(self):
        for filename,schemas in [('pipeline_sampler_node.py',('ltx.pipeline-sampler-request.v1','ltx.sampler-capture-coverage.v2','ltx.sampler-capture-freeze.v2')),('pipeline_decode_node.py',('ltx.pipeline-decode-request.v1','ltx.decode-replica-probe.v1'))]:
            tree=ast.parse((P98/'source/scripts'/filename).read_text())
            found=[]
            for node in ast.walk(tree):
                if isinstance(node,ast.Dict):
                    vals={k.value:v for k,v in zip(node.keys,node.values) if isinstance(k,ast.Constant)}
                    if isinstance(vals.get('schema'),ast.Constant) and vals['schema'].value in schemas:
                        self.assertIn('output_size',vals);found.append(vals['schema'].value)
            self.assertTrue(set(schemas)<=set(found))
        self.assertIn('SAMPLER_BATCH * size98.TOKEN_SCALE', (P98/'source/scripts/pipeline_sampler_node.py').read_text())

    def test_probe_native_parity_and_corruption(self):
        import torch
        torch.set_num_threads(1)
        placement=load('probe_hash',HERE/'ltx_decode_replica.py')
        fixtures=[{'fixture':str(i)} for i in range(10)]
        with unittest.mock.patch.dict(sys.modules,ltx_decode_replica=placement):
            for output_size in ('512x320','640x384'):
                with unittest.mock.patch.dict(os.environ,LTX_OUTPUT_SIZE=output_size):
                    size=load('probe_size',HERE/'ltx_output_size_98.py')
                calls=[]
                def native(v,a):
                    self.assertEqual(tuple(v['samples'].shape),size.latent_shape())
                    calls.append(v['samples'][0,0,0,0,0].item())
                    return torch.zeros(size.image_shape()),{'waveform':torch.zeros(1,2,48480)}
                ok,rows=size.probe_rows(fixtures,None,native,{'replica':native,'replica2':native})
                self.assertTrue(ok);self.assertEqual(len(rows),10);self.assertEqual(len(set(calls)),10)
                self.assertTrue(all(r['replica2_matches_native'] and 'native_matches_reference' not in r for r in rows))
                def corrupt(v,a):
                    im,au=native(v,a);im[0,0,0,0]=1;return im,au
                self.assertFalse(size.probe_rows(fixtures,None,native,{'replica':native,'replica2':corrupt})[0])

    def test_decode_probe_receipt_binding(self):
        size='640x384'
        rows=[{'fixture':str(i),'passed':True,'output_size':size,'references':'none (speed only)',
               'cards_bytewise_equal':True,'replica':{},'replica_matches_native':True} for i in range(10)]
        report={'output_size':size,'rows':rows,'decode_replica':{'replica_devices':['xpu:2'],
                'replica_slots':['replica'],'decode_replicas':1},'replica_device':'xpu:2',
                'outcome':'replica-exact','replicas':{'video':{'device':'xpu:2'},'audio':{'device':'xpu:2'}},
                'xpu:2_free_after_probe':[123,'test']}
        ns={'a':types.SimpleNamespace(size=size),'rows':rows}
        check=function(HERE/'run-decode-probe-98.py','placement_problems',ns)
        self.assertEqual(check(report,'xpu:2'),[])
        for bad in ('512x320',None):
            changed=copy.deepcopy(report);changed['output_size']=bad
            self.assertTrue(check(changed,'xpu:2'))
        changed=copy.deepcopy(report);changed['rows']=[]
        self.assertTrue(check(changed,'xpu:2'))
        rows[-1]['replica_matches_native']=False
        self.assertTrue(check(report,'xpu:2'))

    def test_memory_exit18(self):
        proc=subprocess.run([sys.executable,'-B',str(HERE/'worker-headroom-98.py'),
                             'plan','two-way','2','4','1','--size','640x384','--replicas','xpu:2'],
                            capture_output=True,text=True)
        self.assertEqual(proc.returncode,18)
        self.assertFalse(json.loads(proc.stdout)['room_for_first_worker'])

    def test_memory_admission_and_refusal(self):
        m=load('memory98',HERE/'worker-headroom-98.py')
        for size in ('512x320','640x384'):
            m.SIZE=size;w,h=geometry.dimensions(size);m.SCALE=w*h/65536
            for workers,batch in ((1,1),(2,2)):
                ok,rec=m.plan('two-way',workers,batch,1,spec='xpu:2')
                self.assertTrue(ok);self.assertTrue(all(x>=2 for x in rec['predicted_free_gib_all_workers'].values()))
            self.assertFalse(m.plan('two-way',4,4,1,spec='xpu:2')[0])
            self.assertFalse(m.live({c:float('nan') for c in m.CARDS},'two-way',1,pool=1)[0])
            self.assertFalse(m.live({c:1*2**30 for c in m.CARDS},'two-way',1,pool=1)[0])
        m.SIZE='256x256';m.SCALE=1
        old=load('memory97',HERE/'worker-headroom-97.py')
        for layout in m.LAYOUTS:
            for batch in (1,2,4):
                self.assertEqual(m.worker_cost(layout,batch),old.worker_cost(layout,batch))
                self.assertEqual(m.zero_worker_free(layout,'xpu:2'),old.zero_worker_free(layout,'xpu:2'))

    def test_memory_calibration_rejects_other_size(self):
        m=load('memorycal98',HERE/'worker-headroom-98.py');m.SIZE='640x384';m.SCALE=3.75
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)/'two-way-w2-b1-p1-dxpu2-s256x256';d.mkdir()
            r={'schema':m.CALIBRATION_SCHEMA,'packet_manifest_sha256':'abc','layout':'two-way','batch':1,'shared_pool':1,'per_card_gib':{c:0 for c in m.CARDS},'source_identity_sha256':'id','source_identity_match':True,'output_size':'256x256'}
            (d/'pool-calibration.json').write_text(json.dumps(r))
            self.assertIsNone(m.find_calibration(tmp,'abc','two-way',1)[0])

    def test_speed_client_rejects_oracle_before_io(self):
        client=load('client98',HERE/'run-throughput-fixtures-98.py')
        graph=P98/'graphs/graph-capture-all48-pipe-samp2-tsh-rep-wlean-speed-s640x384.json'
        with self.assertRaisesRegex(AssertionError,'no-oracle'):
            client.main(['test','--graph',str(graph),'--arm','x','--server-run','/no-server','--out','/no-write','--index-base','46000000','--size','640x384'])

    def test_summary_labels(self):
        m=load('summary98',HERE/'summarize-campaign-98.py')
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);rows=[{'index':i,'prompt':f'p-{i}','fill':False,'emitted_index':i,'t_done':float(i),'reference':None,'exact':None} for i in range(20)]
            tp={'rows':rows,'index_base':0,'output_size':'640x384','comparison':'none (speed only)','speed_only':True,'all_exact':None,'batch':2,'intervals_s':[1]*19}
            (d/'x-throughput.json').write_text(json.dumps(tp))
            row=m.arm_summary(d,d,'x','timed',2,[])
            self.assertEqual(row['references'],'none (speed only)');self.assertEqual(row['clips_verified'],0)
            self.assertIsNone(row['all_exact'])

    def run_fake_client(self, directory, wrong=None, sequence_failure=False):
        """Real client control flow; fake HTTP and sparse candidate archives, no server."""
        client = load('review_client98', HERE/'run-throughput-fixtures-98.py')
        root = Path(directory); run = root/'run'; run.mkdir()
        out = root/'out'; fixtures = root/'fixtures.json'
        fixtures.write_text(json.dumps({'fixtures': [{'id': str(i), 'seed': i, 'prompt': 'test'} for i in range(10)]}))
        graph = {'364': {'class_type':'LTXPipelineTextEncode','inputs':{}},
                 '339': {'class_type':'RandomNoise','inputs':{}}, '338': {'class_type':'RandomNoise','inputs':{}},
                 '356': {'inputs':{'width':320,'height':192}},
                 '428': {'inputs':{'speed_only':True,'output_size':'640x384','depth':0}},
                 '426': {'inputs':{'depth':0}}}
        gp=root/'graph.json';gp.write_text(json.dumps(graph))
        (run/'server-identity.json').write_text(json.dumps({'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'pid':os.getpid()}))
        (run/'server-args.json').write_text('{}')
        (root/'model-verification.json').write_text('{"status":"passed"}')
        count = 2 if sequence_failure else 1
        shapes={'images':[25,384,640,3],'video_latent':[1,128,4,12,20],
                'audio_latent':[1,8,26,16],'waveform':[1,2,48480]}
        if wrong: shapes[wrong][-1] += 1
        for i in range(count):
            path=root/'output/validation'/('test-%02d'%i);path.mkdir(parents=True)
            # Safetensors header plus sparse zero data: tests read shapes, never checkpoints.
            header={};offset=0
            for key,shape in shapes.items():
                size=math.prod(shape);header[key]={'dtype':'U8','shape':shape,'data_offsets':[offset,offset+size]};offset+=size
            encoded=json.dumps(header).encode();encoded+=b' ' * (-len(encoded)%8)
            with (path/'tensors.safetensors').open('wb') as stream:
                stream.write(len(encoded).to_bytes(8,'little'));stream.write(encoded);stream.truncate(8+len(encoded)+offset)
            if sequence_failure:
                (run/('pipeline-sampler-test-%02d.json'%i)).write_text(json.dumps({'detail':{'emitted_index':46000000,'emitted_batch_job':{}}}))
        submitted=[]
        def http(request, **kwargs):
            path=request.full_url.split(client.API)[-1]
            if path=='/queue':value={'queue_running':[],'queue_pending':[]}
            elif path=='/prompt':
                submitted.append(1);value={'prompt_id':str(len(submitted)-1)}
            else:
                i=int(path.rsplit('/',1)[1]);value={str(i):{'status':{'completed':True,'messages':[
                    ['execution_start',{'timestamp':1000+i*1000}],['execution_success',{'timestamp':2000+i*1000}]]}}}
            return io.BytesIO(json.dumps(value).encode())
        with unittest.mock.patch.object(client,'ROOT',root), unittest.mock.patch.object(client.urllib.request,'urlopen',http), unittest.mock.patch.object(client.time,'sleep'), contextlib.redirect_stdout(io.StringIO()):
            rc=client.main(['test','--graph',str(gp),'--arm','speed','--server-run',str(run),'--out',str(out),
                            '--fixtures',str(fixtures),'--count',str(count),'--index-base','46000000','--size','640x384','--no-oracle'])
        return rc,json.loads((out/'test-throughput.json').read_text())

    def test_speed_clip_shapes_fail_arm(self):
        for wrong in (None,'images','video_latent','audio_latent','waveform'):
            with self.subTest(wrong=wrong), tempfile.TemporaryDirectory() as tmp:
                rc,receipt=self.run_fake_client(tmp,wrong)
                self.assertEqual(rc,0 if wrong is None else 13)
                self.assertEqual(receipt['output_size'],'640x384')
                self.assertEqual(receipt['comparison'],'none (speed only)')
                self.assertIsNone(receipt['all_exact'])
                if wrong:self.assertIn(wrong,receipt['shape_problems'][0])

    def test_sequence_failure_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc,receipt=self.run_fake_client(tmp,sequence_failure=True)
            self.assertEqual(rc,12)
            self.assertEqual(receipt['output_size'],'640x384')
            self.assertEqual(receipt['comparison'],'none (speed only)')
            self.assertTrue(receipt['speed_only']);self.assertIsNone(receipt['all_exact'])

    def test_default_no_oracle_graph_labels(self):
        client=load('label_client98',HERE/'run-throughput-fixtures-98.py')
        graph=json.loads((P98/'graphs/graph-capture-all48-pipe-samp2-tsh-rep-wlean-b2-w2.json').read_text())
        for speed in (True,False):
            client.label_graph(graph,'256x256',speed)
            for key in ('364','428','426'):
                self.assertEqual(graph[key]['inputs']['output_size'],'256x256')
                self.assertEqual(graph[key]['inputs']['speed_only'],speed)

    def test_runtime_failure_receipts_metadata(self):
        for size in geometry.SIZES:
            for batch in (1,2,4):
                with unittest.mock.patch.dict(os.environ,LTX_OUTPUT_SIZE=size,LTX_SAMPLER_BATCH=str(batch)):
                    module=load('receipt_size',HERE/'ltx_output_size_98.py')
                    for name in ('pipeline_node.py','pipeline_sampler_node.py','pipeline_decode_node.py'):
                        writer=function(P98/'source/scripts'/name,'write_json',{'size98':module,'json':json})
                        with tempfile.TemporaryDirectory() as tmp:
                            path=Path(tmp)/'failure.json';writer(path,{'passed':False,'outcome':'error'})
                            receipt=json.loads(path.read_text())
                            self.assertEqual(receipt['output_size'],size)
                            self.assertEqual(receipt['comparison'],'none (speed only)' if size!='256x256' else 'references:'+{1:'w93c',2:'b2',4:'b4'}[batch])
                            @module.receipt_scope
                            def fail(speed_only=False):
                                writer(Path(tmp)/'speed-failure.json',{'passed':False})
                                raise RuntimeError('intentional failure')
                            with self.assertRaises(RuntimeError):fail(speed_only=True)
                            self.assertEqual(json.loads((Path(tmp)/'speed-failure.json').read_text())['comparison'],'none (speed only)')
                            self.assertEqual(module._SPEED_ONLY.get(),False)

    def test_summary_refuses_missing_metadata(self):
        for missing in ('output_size','comparison','both','runtime'):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as tmp:
                d=Path(tmp);tp={'rows':[],'index_base':0,'output_size':'640x384','comparison':'none (speed only)'}
                if missing=='both':tp.pop('output_size');tp.pop('comparison')
                elif missing!='runtime':tp.pop(missing)
                else:(d/'pipeline-x-00.json').write_text('{"passed":false}')
                (d/'x-throughput.json').write_text(json.dumps(tp))
                p=subprocess.run([sys.executable,'-B',str(HERE/'summarize-campaign-98.py'),'--run',str(d),'--out',str(d),'--batch','1','--arm','x'],capture_output=True,text=True)
                self.assertNotEqual(p.returncode,0);self.assertIn('missing output_size/comparison',p.stderr)
                self.assertFalse((d/'summary.json').exists())

    def test_child_probe_refused_before_work(self):
        with unittest.mock.patch.dict(os.environ,LTX_OUTPUT_SIZE='640x384',LTX_DECODE_CHILD='1'):
            module=load('child_size',HERE/'ltx_output_size_98.py')
        tree=ast.parse((P98/'source/scripts/pipeline_decode_node.py').read_text())
        node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='LTXDecodeChildProbe')
        ns={'size98':module,'_child_node_context':unittest.mock.Mock(side_effect=AssertionError('work began'))}
        method=next(n for n in node.body if isinstance(n,ast.FunctionDef) and n.name=='apply')
        exec(compile(ast.Module(body=[method],type_ignores=[]),'child_probe','exec'),ns)
        with self.assertRaisesRegex(RuntimeError,'stored reference path refused'):ns['apply'](None,'test')
        ns['_child_node_context'].assert_not_called()
        loader=function(P98/'source/scripts/pipeline_decode_node.py','_load_fixture_tensors',{'size98':module})
        with self.assertRaisesRegex(RuntimeError,'stored reference path refused'):loader({})

    def test_runner_memory_receipt_exit_mapping(self):
        text=(HERE/'run-campaign-98.sh').read_text()
        for var,stem,fallback in [('DPROBE_RC','decode-probe-f98-test-dprobe',9),('FREEZE_RC','sampler-capture-freeze-f98-test-freeze',16)]:
            line=next(line for line in text.splitlines() if line.startswith('[ $'+var+' -eq 0 ]'))
            for outcome in ('insufficient-memory','memory-floor','chain-check-no-room','error','replica-not-exact','chain-check-failed','pipeline-busy',None):
                with self.subTest(step=var,outcome=outcome),tempfile.TemporaryDirectory() as tmp:
                    if outcome:(Path(tmp)/(stem+'.json')).write_text(json.dumps({'outcome':outcome}))
                    env=dict(os.environ,PY=sys.executable,LANE=str(HERE.parent),RUN=tmp,TAG='test',**{var:'10'})
                    # Execute only the failure dispatch, with a stop spy. No campaign action runs.
                    script='step() { :; }; finish() { echo "graceful-stop:$1"; exit "$1"; };\n'+line
                    p=subprocess.run(['bash','-c',script],env=env,capture_output=True,text=True)
                    code=18 if outcome in ('insufficient-memory','memory-floor','chain-check-no-room') else fallback
                    self.assertEqual(p.returncode,code);self.assertEqual(p.stdout.strip(),'graceful-stop:'+str(code))

    def test_runner_all_index_blocks_and_names(self):
        text=(HERE/'run-campaign-98.sh').read_text()
        parse=text[text.index('set -u'):text.index('R=/mnt/fast-ai')]
        script='''for l in two-way shard4-a shard3-c; do for w in 1 2 3 4; do for b in 1 2 4; do for p in 0 1; do for d in xpu:1 xpu:2 xpu:1,xpu:2 xpu:2,xpu:1; do for s in 256x256 512x320 640x384; do for r in 1 2 3 4 5; do
set -- "$l" "$w" "$b" "$p" "$d" "$s" "$r" 9000
'''+parse+'''\necho "$MODE $BASE $TIMED_BASE $TIMED_ARM $CAP_ARM"
done; done; done; done; done; done; done'''
        out=subprocess.run(['bash','-c',script],check=True,capture_output=True,text=True).stdout.splitlines()
        self.assertEqual(len(out),4320)
        short=[];timed=[];names=[]
        for line in out:
            mode,base,tbase,arm,cap=line.split();short.append(int(base));timed.append(int(tbase));names.append(mode)
            self.assertTrue((P98/f'graphs/graph-capture-all48-{arm}.json').is_file())
            self.assertTrue((P98/f'graphs/graph-capture-all48-{cap}.json').is_file())
        self.assertEqual(len(set(names)),4320)
        self.assertEqual(len(set(short)),4320);self.assertEqual(len(set(timed)),4320)
        self.assertGreater(min(short),45920000);self.assertLess(max(short)+500,min(timed))
        self.assertLess(max(timed)+9000,100000000)
        self.assertEqual(min(b-a for a,b in zip(sorted(timed),sorted(timed)[1:])),10000)

    def test_runner_safety_sequence(self):
        text=(HERE/'run-campaign-98.sh').read_text()
        for token in ('SIGINT_IGN','stop_when_proven','pipeline_idle_stable','failed_jobs','finish 20','finish 22','NEOReadDebugKeys','EnableDeferBacking','health_admission','--size "$SIZE"','--no-oracle','-- "${OUT#$REPO/}"'):
            self.assertIn(token,text)
        self.assertNotIn('$PY -c',text)
        self.assertIn('SIZE=${6:-}',text)
        self.assertIn('run-capture-freeze-94.py',text)
        self.assertIn('selfcheck-94f.py',text)
        subprocess.run(['bash','-n',str(HERE/'run-campaign-98.sh')],check=True)


if __name__=='__main__':
    import unittest.mock
    unittest.main(verbosity=2)
