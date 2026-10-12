#!/usr/bin/env python3
"""CPU receipt-path rehearsal. Device admission/timestamps are never fabricated.

The host fixture validation mode exercises the exact registered entry bindings;
full arithmetic identity is covered by fixture_gate and p38_kernel_gate. K0's
SYCL build-only body has no host backend, so only its refusal/receipt contract
can be checked here, explicitly recorded as a remaining device-window gate.
"""
import argparse,copy,json,os,subprocess,time,unittest,gzip,contextlib
from pathlib import Path
from unittest.mock import patch
import pipeline as pp
import suite,window,k2_summary
P=Path(__file__).resolve().parent

def child(binary,argv,log):
    pp.require('/device/' not in str(binary.resolve()),'never execute a device binary')
    with log.open('w') as output:
        process=subprocess.Popen(['nice','-n','19','ionice','-c','3',str(binary),*map(str,argv)],stdout=output,stderr=subprocess.STDOUT,
                                 env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'})
        code=process.wait(timeout=10800)
    pp.require(code==0,log.read_text()[-3000:]);return process.pid

def receipt(path):
    row=json.loads(path.read_text());pp.require(row.get('passed') is True,'CPU backend failed '+str(path))
    pp.require(row.get('device_executed') is False,'CPU receipt mislabeled as device')
    # Ordinary JSON encoder deliberately rejects Path objects in every final record.
    json.dumps(row);return row

def hashes(root,patterns):
    return {str(f.relative_to(root)):pp.sha(f) for pattern in patterns for f in sorted(root.glob(pattern)) if f.is_file()}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--binary',type=Path,default=P/'build/gnu-host/own-rt-iq3')
    parser.add_argument('--output',type=Path,default=P/'build/window-cpu-gate');parser.add_argument('--phase',choices=['all','fixtures','models'],default='all')
    parser.add_argument('--skip-wrapper-tests',action='store_true',help='fixtures phase only; model phase runs the pair-spawning regressions')
    a=parser.parse_args();pp.require(not a.skip_wrapper_tests or a.phase=='fixtures','only fixture rehearsal may defer wrapper pair');pp.require(os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2','CPU priority/thread contract')
    a.output.mkdir(parents=True,exist_ok=True);rows=[];root=a.output;bindir=a.binary.parent
    def note(name,**extra):
        row=dict(window=name,passed=True,device_executed=False,cpu_receipt_contract=True,**extra);json.dumps(row);rows.append(row)
        pp.save(root/'progress.json',rows)
    if a.phase in ('all','fixtures'):
        # K0 is a build-only device program, intentionally not executed here.
        refusal=subprocess.run(['nice','-n','19','ionice','-c','3',str(a.binary),'--authorized-device-window','--mini','--output',str(root/'K0-refusal')],capture_output=True,text=True,env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'},timeout=30)
        (root/'K0-host-refusal.log').write_text(refusal.stdout+refusal.stderr)
        pp.require(refusal.returncode!=0 and 'host binary cannot authorize device execution' in refusal.stderr,'host authorization refusal must precede owner creation')
        note('K0',scope='source/argument contract only; SYCL bundle build remains coordinator-only',kernel_execution=False,host_authorization_refused=True)
        fresh=[]
        for name in ('K1a','K1b'):
            out=root/name;out.mkdir();run=out/'run0';linked=out/'linked'
            pid=child(bindir/'nongemv-fixtures',['--validate-only','--dispatch',P/'dispatch-p38.json','--fixtures',P/'build/fusion-fixtures','--output',run],out/'fixture.log')
            r=receipt(run/'receipt.json');pp.require(r.get('validation_only') is True and r['fixtures']>=72,'K1 entry coverage')
            lpid=child(bindir/'p33-linked-fixtures',['--output',linked,'--seconds','300'],out/'linked.log')
            l=receipt(linked/'receipt.json');pp.require(l['checks']==216 and l['split_instantiations']==36 and l['reference_exact'],'linked fixture checks')
            pp.require(pp.sha(linked/'output.bin')==l['output_sha256'],'linked output digest')
            owner=dict(pids=[pid,lpid]);fresh.append(owner)
            note(name,fixture_binary_sha256=pp.sha(bindir/'nongemv-fixtures'),linked_binary_sha256=pp.sha(bindir/'p33-linked-fixtures'),pids=owner['pids'],fixture_entry_checks=r['fixtures'],linked_checks=l['checks'],validation_only=True,
                 receipts=hashes(out,['run0/receipt.json','linked/receipt.json']))
        window.fresh_k1_owners(*fresh)
        out=root/'K2';out.mkdir();run=out/'run0'
        child(bindir/'k2-fixtures',['--validate-only','--dispatch',P/'dispatch-p38.json','--fixtures',P/'build/fusion-fixtures','--output',run,'--repetitions','200'],out/'fixture.log')
        r=receipt(run/'receipt.json')
        with (out/'summary.log').open('w') as log,contextlib.redirect_stdout(log):summary=k2_summary.summarize(run)
        pp.require(summary['passed'] is False,'CPU zero timestamps must never pass device K2')
        for name in ('summary.json','dispatch-measured.json','dispatch-rank0.json','dispatch-rank1.json'):
            pp.require((run/name).is_file(),'K2 summary receipt missing '+name);json.loads((run/name).read_text())
        packed=P/'evidence/window-cpu-k2-summary.json.gz';packed.parent.mkdir(exist_ok=True)
        raw=(run/'summary.json').read_bytes();packed.write_bytes(gzip.compress(raw,mtime=0));pp.require(gzip.decompress(packed.read_bytes())==raw,'K2 evidence archive roundtrip')
        note('K2',summary_archive=str(packed.relative_to(P)),summary_archive_sha256=pp.sha(packed),summary_sha256=pp.sha(run/'summary.json'),fixture_binary_sha256=pp.sha(bindir/'k2-fixtures'),entry_checks=r['fixtures'],summary_exercised=True,device_timing_rejected=True,
             summary_failure_count=len(summary['failures']),summary_failure_examples=summary['failures'][:4],validation_only=True)
    if a.phase in ('all','models'):
        base=pp.parser().parse_args(['--binary',str(a.binary),'--output',str(root/'unused'),'--mini','--tokens','8','--context','32','--seconds','300','--wait-seconds','300','--dump-state'])
        base.host_memory='resident';base.argument_audit=True
        # W0p actual two-rank host owner/canary protocol, same byte contract.
        out=root/'W0p';out.mkdir();canary=copy.copy(base);canary.output=out/'run';canary.output.mkdir();canary.canary=True
        t=pp.Transport(canary,canary.output);pids=[c.pid for c in t.children]
        try:
            for index in range(1000):
                for rank in (0,1):
                    t.mapping[rank*pp.SLOT:rank*pp.SLOT+256]=pp.struct.pack('<64I',*([index]*64));t.start(rank,pp.CANARY,position=index)
                t.wait(0);t.wait(1)
                for rank in (0,1):pp.require(t.mapping[rank*pp.SLOT:rank*pp.SLOT+256]==pp.struct.pack('<64I',*([index+1]*64)),'W0p byte handover')
            t.close(True)
        except Exception as error:t.stop(error);t.close(False);raise
        pp.save(out/'receipt.json',dict(passed=True,device_executed=False,pids=pids,handovers=1000))
        note('W0p',handovers=1000,pids=pids)
        # KD two fresh host capture owners; deterministic miniature BF16 inputs.
        out=root/'KD';out.mkdir();stream=out/'streams.bf16';stream.write_bytes(bytes(128))
        table=out/'capture.tsv';table.write_text(''.join(f'{pos} {token} 1 {stream.resolve()}\n' for pos,token in enumerate([2,5,3])))
        signatures=[];pids=[]
        for index in range(2):
            dest=out/f'owner{index}';pids.append(child(a.binary,['--mini','--pipeline-mini','--draft-capture',table,'--rank','1','--context','32','--output',dest,'--seconds','300'],out/f'owner{index}.log'))
            receipt(dest/'receipt.json');signatures.append(hashes(dest,['row-*/*.bf16','row-*/*.bin','draft-final-state/*.bin']))
        pp.require(signatures[0] and signatures[0]==signatures[1] and len(set(pids))==2,'KD fresh owner fixture identity')
        note('KD',fixture_files=len(signatures[0]),pids=pids,miniature=True)
        reference=None;reference_fixtures=None
        for controller in ('python','native'):
            for name,draft,timing in [('W2s','none','token'),('W2n','ngram','token'),('W2m','mtp','token'),('W2d','script','token'),('W2x','script','token'),('W2mc','mtp','class')]:
                args=copy.copy(base);args.output=root/(name+'-'+controller);args.controller=controller;args.draft=draft;args.timing=timing
                if draft=='script':
                    args.script=root/('diagnostic-'+name+'-'+controller+'.txt');args.script.write_text(' '.join(map(str,reference[:-1] if name=='W2d' else [(token+1)%16 for token in reference[:-1]])))
                r=pp.run(args);receipt(args.output/'receipt.json')
                current=hashes(args.output,['rank*/step*/layer-*.bf16'])
                if reference is None:reference=r['tokens'];reference_fixtures=current
                pp.require(r['tokens']==reference and current==reference_fixtures,'controller/draft changed token or retained fixture')
                pp.require(r['decode_tok_s'] is None,'CPU output must not report device speed')
                if name in ('W2d','W2x'):
                    expected_hits=len(reference)-1 if name=='W2d' else 0
                    pp.require(r['stats']['guesses']==len(reference)-1 and r['stats']['hits']==expected_hits,'diagnostic all-hit/all-miss pattern')
                profiles=[args.output/f'rank{rank}/class-times.json' for rank in (0,1)]
                if timing=='class':
                    for profile in profiles:
                        info=json.loads(profile.read_text());pp.require(info['profiling'] is True and info['classes'],'class-only receipt required in class mode')
                else:pp.require(not any(profile.exists() for profile in profiles),'token-only mode must not require class-only receipts')
                note(name,controller=controller,draft=draft,timing=timing,tokens=len(reference),retained_fixtures=len(current),class_receipt_required=timing=='class')
        # WS/WSs persistent rank suite summary, using three distinct mini requests.
        manifest=root/'suite-manifest.json';pp.save(manifest,dict(arithmetic='iq3-p17-detmath-v2',token_cap=64,context=32,complete=False,prompts=[dict(prompt_id=name,mini_tokens=tokens,mini_count=8,input_bundle='unused-mini') for name,tokens in [('alpha',[2,5,3,7,1]),('beta',[1,2,1]),('gamma',[3,5,7,2])]]))
        for name,draft in [('WS','mtp'),('WSs','none')]:
            args=copy.copy(base);args.output=root/name;args.controller='native';args.draft=draft;args.suite_manifest=manifest;args.repeat=1
            result=suite.run(args);receipt(args.output/'receipt.json');pp.require(result['passed'] and len(result['rows'])==3 and result['decode_median_tok_s'] is None,'suite summary contract')
            note(name,controller='native',draft=draft,requests=len(result['rows']),summary_exercised=True)
    # A forked process may refuse malformed arguments before Device creation.
    # Launch itself is not GPU contact and cannot poison the boot fault latch.
    safety=root/'latch-contract';safety.mkdir(exist_ok=True)
    with patch.object(window,'journal',return_value=('Fault response: old reviewed event','own-start')):
        watch=window.Watch(safety,'cpu-contract',600)
    watch.mark_launched(12345)
    with patch.object(window,'save') as saved:
        watch.latch('argument refusal before device contact');saved.assert_not_called()
    with patch.object(window,'journal',return_value=('', 'after-own-start')),patch.object(window,'save') as saved:
        watch.last=0;watch.poll_kernel();saved.assert_not_called()
    with patch.object(window,'journal',return_value=('Fault response: new window event','new-event')),patch.object(window,'save') as saved:
        watch.last=0
        try:watch.poll_kernel()
        except ValueError:pass
        else:raise AssertionError('new kernel fault not rejected')
        saved.assert_called_once();json.dumps(saved.call_args.args[1])
    # Existing regressions exercise prelaunch refusal, only-new journal lines,
    # fresh K1 owners, loader failures, and JSON serializable wrapper metadata.
    wrapper_tests=0
    if not a.skip_wrapper_tests:
        import test_window
        loaded=unittest.defaultTestLoader.loadTestsFromModule(test_window)
        with (root/'wrapper-tests.log').open('w') as output:tests=unittest.TextTestRunner(stream=output,verbosity=2).run(loaded)
        pp.require(tests.wasSuccessful(),'wrapper regressions failed: '+str(root/'wrapper-tests.log'))
        wrapper_tests=tests.testsRun
    report=dict(schema='packet38.window-cpu-rehearsal.v1',passed=True,device_executed=False,no_speed_claim=True,phase=a.phase,rows=rows,wrapper_tests=wrapper_tests,wrapper_tests_deferred_to='window-cpu-models.json' if a.skip_wrapper_tests else None,new_latch_regressions=3,
                binary_sha256=pp.sha(a.binary),limitations=['K0 SYCL bundle build has no host equivalent and remains coordinator-only','K1 registration dryrun uses validation-only mode; full arithmetic gate is separate','CPU K2 emits zero GPU timestamps and is required to fail device timing admission','mini requests exercise receipts/controller/reset; real-model oracle windows remain pending'])
    pp.save(P/('window-cpu-'+a.phase+'.json'),report);print(json.dumps(dict(passed=True,phase=a.phase,windows=len(rows),wrapper_tests=wrapper_tests,binary_sha256=report['binary_sha256'])))
if __name__=='__main__':main()
