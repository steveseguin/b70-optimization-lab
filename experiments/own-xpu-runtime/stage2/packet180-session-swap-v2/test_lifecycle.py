"""Synthetic worker lifecycle arm at production shape; real Python gates; mocked native.

Runs the real worker.lifecycle() (argv for five fresh processes, NEW input file, leg
ordering, reset/stream/completion checks, manifest reads, host-tool wrapper, comparators,
receipt, drain proof) with subprocess.Popen and the device-free host tools mocked. Shapes are
production: P is the 87-token suite prompt, K=256, T is the recorded 126-token turn, NEW is
469 tokens, manifests carry packet179's real 128-blob/1937-skip layout. Token values are real
(packet179 row-a incident-retrospective output) so the save == packet179 [0:K] and oracle-128
gates run as on device; the reference continuation is a stand-in, never a measurement.
Deliberate mismatches must FAIL with the first divergent index and both streams in
run/lifecycle-receipt.json. Also: screen.report_completed on the passing receipt, and the
worker's host-tool wrapper against the host-only probe binary on a real CPU-probe checkpoint.
"""
import copy,hashlib,json,os,shutil,struct,sys,tempfile
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent;p=P/sys.argv[1];sys.path.insert(0,str(p))
import worker,measurement as MEAS,screen
read=lambda f:json.loads(Path(f).read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
L=worker.LIFECYCLE;K,M1,M2=L['K'],L['M1'],L['M2'];ids=L['checkpoint_ids']
prompt=list(map(int,(p/'inputs'/L['prompt_id']/'tokens.txt').read_text().split()))
p179=read(p/'reference-p179-row-a.json')['prompts'][L['prompt_id']]['tokens']
turn=MEAS.lifecycle_turn(L,p)
template=read(p/'lineage/packet179-receipts/row-b/run/checkpoints/gate/manifest.json')
REF=list(p179[256:256+M1+M2])
assert len(REF)==M1+M2 and not any(t in MEAS.EOS for t in REF) and len(prompt)==87 and len(turn)==126
TID=p/'tokenizer-identity.tsv'
drain=dict(passed=True,device_executed=True,teardown=[dict(safe_to_exit=True,idle_marker_complete=True,live_bytes=0,in_flight=0,exit_code=0)])

def fake_checkpoint(root,cid,processed,pending,prompt_length,parent=None,perturb=False):
    d=root/cid;assert not d.exists(),'never overwrite';d.mkdir(parents=True)
    N=len(processed);m=copy.deepcopy(template)
    m.update(contract='v1.2+p180',operations=['same-generation-resume','append','restore-then-save'],checkpoint_id=cid,
             lineage=dict(operation='restore-then-save' if parent else 'save',parent=parent))
    m['tokenizer_identity']=dict(file_sha256=sha(TID.read_bytes()),format='ownrt.tokenizer-identity.v1',gguf_header_sha256='0'*64,
                                 tokenizer_source_sha256='0'*64,vocab_bin_sha256='0'*64)
    token_bytes=struct.pack('<%di'%N,*processed)
    m['token_state']=dict(prompt_length=prompt_length,length=N,position=N,next_token=pending,tokens_sha256=sha(token_bytes),
                          token_history=[processed[-2],processed[-1]])
    total=0
    for b in m['blobs']:
        if b['slice']:
            rows=N//4 if b['name'].endswith('.qsa.pooled') else N
            b['bytes']=b['bytes']//b['slice'][1]*rows;b['slice']=[0,rows]
        b['sha256']=sha((b['name']+repr(processed)+repr(pending)+('perturbed' if perturb and b['name']=='blk.3.qsa.keys' else '')).encode())
        total+=b['bytes']
    m['measurements']=dict(save_seconds=1.25,save_bytes=total)
    (d/'manifest.json').write_text(json.dumps(m,separators=(',',':'))+'\n')
    (d/'fields.tsv').write_text('synthetic rendering\n');(d/'tokens.bin').write_bytes(token_bytes)
    for name,value in (('position',N),('next_token',pending),('token',processed[-1]),('error',0)):(d/(name+'.bin')).write_bytes(struct.pack('<i',value))
    (d/'token_history.bin').write_bytes(struct.pack('<2q',processed[-2],processed[-1]))
    (root/(cid+'.lock')).write_text('')
    return m

def fake_tool(flag,target,folder):
    target=Path(target);m=read(target/'manifest.json');digest=sha((target/'manifest.json').read_bytes())
    row=dict(argv=['own-rt-iq3',flag,str(target)],returncode=0,stdout_lines=1,stderr_json_lines=True)
    if flag=='--checkpoint-delete':
        shutil.rmtree(target);(target.parent/(target.name+'.lock')).unlink()
        row['stdout_object']=dict(schema='ownrt.checkpoint-delete.v1',ok=True,deleted=True,reason=None,error=None)
    else:
        metadata=flag=='--checkpoint-inspect-metadata'
        verified=dict(blobs_verified=None,blob_bytes_verified=None) if metadata else dict(blobs_verified=len(m['blobs']),
            blob_bytes_verified=m['measurements']['save_bytes']+4*m['token_state']['position'])
        row['stdout_object']=dict(schema='ownrt.checkpoint-inspect.v1',ok=True,mode='metadata' if metadata else 'full',manifest=m,
            manifest_sha256=digest,verified=verified,error=None)
    return row

def run_arm(mutate=None,perturb_s2b=False,fail_leg=None,reference_stop=None):
    mutate=mutate or {}
    with tempfile.TemporaryDirectory(prefix='p180-lifecycle-') as td:
        root=Path(td);out=root/'run'
        worker.save(root/'window.json',dict(synthetic=True));worker.save(root/'identity.json',dict(lane='A'))
        launches=[];state={}
        class Child:
            def __init__(self,argv,**kw):
                argv=list(argv);launches.append(argv)
                assert argv[:2]==['/usr/bin/ionice','-c3'] and argv[2]==str(p/'build/device/own-rt-iq3')
                assert '--suite-inputs' not in argv and argv[argv.index('--retain-steps')+1]=='none' and argv[argv.index('--context')+1]=='4096'
                leg=Path(argv[argv.index('--output')+1]).parent.name
                outpath=Path(argv[argv.index('--output')+1]);assert not outpath.exists();outpath.mkdir(parents=True)
                max_new=int(argv[argv.index('--max-new')+1])
                tokens_in=list(map(int,Path(argv[argv.index('--input')+1]).read_text().split()))
                ckpt='--checkpoint-save' in argv or '--checkpoint-restore' in argv
                assert ('--tokenizer-identity' in argv)==ckpt
                if ckpt:assert argv[argv.index('--tokenizer-identity')+1]==str(TID)
                self.returncode=1 if leg==fail_leg else 0
                if leg=='save-s1':
                    assert tokens_in==prompt and max_new==K
                    gen=list(p179[:K])
                else:
                    assert tokens_in==prompt+state['save']+turn and len(tokens_in)==469,'NEW = P + gen[0:K] + T'
                    R=list(REF) if reference_stop is None else list(REF[:reference_stop-1])+[248046]
                    gen={'append-s2':R[:M1],'append-s2b':R[:M1],'resume-s2':R[M1:M1+M2],'reference':R}[leg]
                    if leg=='resume-s2' and len(R)<=M1:gen=list(REF[:M2])  # the engine steps a pending EOS and keeps generating
                    assert max_new==dict(**{'append-s2':M1,'append-s2b':M1,'resume-s2':M2,'reference':M1+M2})[leg]
                if leg in mutate:gen=mutate[leg](list(gen))
                if leg=='save-s1':state['save']=gen
                start={'save-s1':1000.,'append-s2':2000.,'resume-s2':3000.,'reference':4000.,'append-s2b':5000.}[leg]
                restore=save=None
                if '--checkpoint-restore' in argv:
                    rid=argv[argv.index('--checkpoint-id')+1];rroot=Path(argv[argv.index('--checkpoint-restore')+1])
                    m=read(rroot/rid/'manifest.json');N=m['token_state']['position']
                    append=len(tokens_in)>=N+1
                    restore=dict(checkpoint_id=rid,manifest_sha256=sha((rroot/rid/'manifest.json').read_bytes()),
                        operation='append' if append else 'same-generation-resume',saved_prefix_length=N,saved_history_length=N+1,
                        saved_prompt_length=m['token_state']['prompt_length'],input_length=len(tokens_in),
                        appended_length=len(tokens_in)-N-1 if append else 0,pending_token=m['token_state']['next_token'],
                        pending_token_handling='synthetic',restore_ms=480.5,append_prefill_ms=9000.25 if append else None,restored_bytes=70000000)
                if '--checkpoint-save' in argv:
                    sroot=Path(argv[argv.index('--checkpoint-save')+1])
                    sid=argv[argv.index('--checkpoint-save-id')+1] if restore else argv[argv.index('--checkpoint-id')+1]
                    if restore and restore['operation']=='append':processed=tokens_in+gen[:-1]
                    elif restore:processed=None
                    else:processed=tokens_in+gen[:-1]
                    parent=dict(checkpoint_id=restore['checkpoint_id'],manifest_sha256=restore['manifest_sha256']) if restore else None
                    m=fake_checkpoint(sroot,sid,processed,gen[-1],len(tokens_in),parent,perturb=perturb_s2b and sid==ids['S2b'])
                    save=dict(checkpoint_id=sid,manifest_sha256=sha((sroot/sid/'manifest.json').read_bytes()),position=len(processed),
                        pending_token=gen[-1],bytes=m['measurements']['save_bytes'],seconds=1.25,parent_checkpoint_id=parent and parent['checkpoint_id'])
                ops=([restore['operation']] if restore else [])+(['save'] if save else [])
                result=dict(passed=True,arithmetic=MEAS.ARITHMETIC,cached_tokens=0,requested_max_new=max_new,prompt_tokens=len(tokens_in),
                    tokens=gen,timing_rows=[dict(completed_monotonic=start+1+i*.03) for i in range(len(gen))],
                    request_start_monotonic=start,request_end_monotonic=start+60.,
                    prefill_ms=(restore or {}).get('append_prefill_ms') or (0 if restore else 30000.),
                    checkpoint_restore_ms=restore['restore_ms'] if restore else None,
                    checkpoint=dict(contract='v1.2+p180',label='experimental',operations=ops,restore=restore,save=save))
                worker.save(outpath/'reset.json',dict(passed=True,cached_tokens=0,allocation_ids_preserved=True))
                (outpath/'timings.jsonl').write_text(json.dumps(dict(request=leg,sensor='synthetic'))+'\n')
                (outpath/'prefill-timings.jsonl').write_text('' if leg=='resume-s2' else json.dumps(dict(request=leg,sensor='synthetic'))+'\n')
                worker.save(outpath/'result.json',result);worker.save(outpath/'lookup-request-complete.json',{})
                worker.save(outpath/'receipt.json',drain)
            def poll(self):return self.returncode
        from contextlib import ExitStack
        error=None
        with ExitStack() as stack:
            stack.enter_context(patch.object(worker.subprocess,'Popen',Child))
            stack.enter_context(patch.object(worker.exec_limits,'check'))
            stack.enter_context(patch.object(worker,'host_tool',side_effect=fake_tool))
            stack.enter_context(patch.object(sys,'argv',['worker','--output',str(out),'--lane','A','--kind','lifecycle']))
            try:rc=worker.main()
            except (ValueError,KeyError,AssertionError) as e:rc,error=None,e
        receipt=read(out/'lifecycle-receipt.json') if (out/'lifecycle-receipt.json').exists() else None
        summary=None
        if rc==0:
            summary=screen.report_completed(root,dict(device_executed=False),dict(lane='A',bracket=dict(kind='lifecycle')),dict(scope='synthetic-CPU'))
        return rc,error,receipt,launches,summary

rc,error,receipt,launches,summary=run_arm()
assert rc==0 and error is None and len(launches)==5,(rc,error)
assert receipt['passed'] and not receipt['problems'] and receipt['device_executed'] is False
assert all(g['passed'] for g in receipt['gates'].values()) and len(receipt['gates'])>=30
assert receipt['comparisons']['append_vs_reference']['compared']==M1 and receipt['comparisons']['chain_vs_reference']['compared']==M2
assert receipt['new_input_tokens']==469 and receipt['timing']['cold_vs_restore']['input_tokens']==469 and receipt['timing']['cold_vs_restore']['saved_prefix_tokens']==342
assert summary['kind']=='lifecycle' and summary['passed'] and summary['experimental_checkpoint'] and not summary['submission_eligible']
cases=['pass: 5 launches, all gates, report written']
def fails(name,gate,index=None,**kw):
    rc,error,receipt,launches,_=run_arm(**kw)
    assert rc is None and error is not None,name
    assert receipt is not None and receipt['passed'] is False,name
    if gate:
        assert gate in receipt['problems'],(name,receipt['problems'])
        detail=receipt['gates'][gate]['detail']
        if index is not None:assert detail['index']==index,(name,detail)
    cases.append(name+': '+(gate or receipt.get('stage','')))
    return receipt
flip=lambda i:(lambda t:t[:i]+[t[i]^1]+t[i+1:])
r=fails('append divergence at 37','append == reference [0:M1]',37,mutate={'append-s2':flip(37),'append-s2b':flip(37)})
cmp=r['comparisons']['append_vs_reference'];assert len(cmp['actual_tokens'])==M1 and len(cmp['expected_tokens'])==M1,'both streams saved'
fails('chain divergence at 5','restore-then-save chain == reference [M1:M1+M2]',5,mutate={'resume-s2':flip(5)})
fails('repeat divergence at 100','append repeat identical',100,mutate={'append-s2b':flip(100)})
fails('S2b state differs','S2 == S2b saved state (every blob sha256, token state)',perturb_s2b=True)
fails('save differs from packet179 at 200','save == packet179 row a [0:K]',200,mutate={'save-s1':flip(200)})
fails('save inside oracle-128 at 7','save oracle-128 prefix',mutate={'save-s1':flip(7)})
r=fails('reference natural stop at 100 (<=M1)','restore-then-save chain == reference [M1:M1+M2]',reference_stop=100)
assert 'not evaluable' in r['gates']['restore-then-save chain == reference [M1:M1+M2]']['detail']
rc,error,receipt,launches,_=run_arm(reference_stop=150)
assert rc==0 and receipt['passed'] and receipt['reference_natural_stop'] and receipt['comparisons']['chain_vs_reference']['compared']==150-M1
cases.append('reference natural stop at 150 (>M1): chain evaluable and passes')
r=fails('EOS inside the save leg',None,mutate={'save-s1':lambda t:t[:100]+[248044]+t[101:]})
assert r['stage']=='native legs' and r['completed_legs']==['save-s1']
r=fails('native failure in append-s2',None,fail_leg='append-s2')
assert r['stage']=='native legs' and 'native failed' in r['error']

# Host-tool wrapper against the host-only probe binary on a real CPU-probe checkpoint.
probe=p/'build/checkpoint-probe/checkpoint-probe';source=p/'build/checkpoint-probe/run/ck/s2'
assert probe.is_file() and (source/'manifest.json').is_file(),'run checkpoint_probe.py first'
with tempfile.TemporaryDirectory(prefix='p180-hosttool-') as td:
    td=Path(td);(td/'build/device').mkdir(parents=True);os.symlink(probe,td/'build/device/own-rt-iq3')
    shutil.copytree(source,td/'ck/s2')
    with patch.object(worker,'HERE',td):
        meta=worker.host_tool('--checkpoint-inspect-metadata',td/'ck/s2',td/'tools')
        full=worker.host_tool('--checkpoint-inspect',td/'ck/s2',td/'tools')
        gone=worker.host_tool('--checkpoint-delete',td/'ck/s2',td/'tools')
    manifest=read(source/'manifest.json')
    assert meta['returncode']==0 and meta['stdout_lines']==1 and meta['stderr_json_lines'] and meta['stdout_object']['manifest']==manifest
    assert full['stdout_object']['verified']['blobs_verified']==len(manifest['blobs']) and full['stderr_json_lines']
    assert gone['stdout_object']['deleted'] is True and not (td/'ck/s2').exists() and not (td/'ck/s2.lock').exists()
cases.append('host_tool wrapper parses the real C++ inspect/inspect-metadata/delete output (host-only probe binary)')
worker.save(p/'evidence/lifecycle-test.json',dict(passed=True,device_executed=False,synthetic=True,launches=5,
    production_shape=dict(prompt_tokens=87,K=K,turn_tokens=126,new_input_tokens=469,M1=M1,M2=M2,manifest_blobs=len(template['blobs']),
        manifest_skipped_buffers=len(template['skipped_buffers'])),
    cases=cases,native_transport_mocked=True,host_tools_mocked_in_arm=True,
    scope='real Python lifecycle orchestration and gates with synthetic streams (real token values) and mocked native/host tools; no arithmetic/performance claim; native CPU sessions in checkpoint_probe.py'))
print(p.name,'lifecycle worker arm PASS',len(cases),'cases')
