#!/usr/bin/env python3
"""Private additive derivation of packet196 from the completed cache23 chain. CPU only.
The shared generator stays unchanged. Parent artifacts/gates remain historical evidence;
new model bytes are bound to the device-qualified diet screen and its exact source snapshot.
No READY-FOR-DEVICE marker is emitted here: finalize.py writes it after successor gates.
"""
import ast, hashlib, importlib.util, json, os, re, shutil, sys
from pathlib import Path
ROOT=Path('/home/steve/llm-optimizations'); X=ROOT/'experiments/own-xpu-runtime'; OPS=X/'ops'
P0=X/'stage2/packet58-onecard-cache23-chain'; O0=OPS/'packet58c23chain-orchestration'
P=X/'stage2/packet196-onecard-diet-chain'; O=OPS/'packet196-orchestration'
D=X/'stage2/packet58-onecard-diet-engine'
SCREEN=D/'screen/evidence/card0-58de-v5-a/resident/WSCREEN'
FLAGS={'--wait-policy':'spin','--foreground-io':'kernel','--expert-gateup':'diet'}
DEVICE='537c080767f241653a8ac13c77289cd59e8f7444cbee2a4fcb35586eb1e743d4'
HOST='9338012d57a5ab870e7710c270480568d2a37a0dde96efaaf10a640d9677cd92'
K1='ba49aa8156437e0a1f95e52efe5b6b61141f96af62614a8f903c0c627f9e9c35'
PARENT_DEVICE='083e3853427041be36faeaf804781e4204b79ed19296648e0aaa7f6c5f1b151a'
HOST_FLOOR=100487123456; WRITES=397492208
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def rewrite_generated(text, head, value):
    pattern=re.compile(r'^'+re.escape(head)+r'(.*)$',re.M)
    matches=list(pattern.finditer(text));assert len(matches)==1,head
    old=ast.literal_eval(matches[0][1]);return pattern.sub(lambda m:head+repr(value),text),old

def additive_sources(suite, composition, views, parent, flags):
    assert flags==FLAGS and parent['chain_flags']=={'--wait-policy':'spin','--foreground-io':'kernel'}
    assert parent['cache_cap']=='max23' and parent['cache_bytes']==parent['cache_allocation_bytes']==23049601024
    assert suite.index('# >>> onecard_chain_derive generated chain flags')<suite.index("if __name__=='__main__':")
    suite,old=rewrite_generated(suite,'GENERATED_CHAIN_FLAGS = ',list(flags.items()));assert dict(old)==parent['chain_flags']
    old_line='FLAGS.update('+repr(list(parent['chain_flags'].items()))+')';assert composition.count(old_line)==1
    composition=composition.replace(old_line,'FLAGS.update('+repr(list(flags.items()))+')')
    extra={'chain_flags':dict(flags),**{k[2:].replace('-','_'):v for k,v in flags.items()}}
    views,old=rewrite_generated(views,'GENERATED_RUNTIME_SELECTION = ',extra)
    assert old=={'chain_flags':parent['chain_flags'],'wait_policy':'spin','foreground_io':'kernel'}
    return suite,composition,views,dict(parent,**extra)

def load_generator():
    shared=OPS/'onecard_chain_derive.py';source=shared.read_text()
    replacements={
      'host_required_available_bytes=98990252032':'host_required_available_bytes=100487123456',
      "planned_write_bytes=R0.get('planned_write_bytes', 1)":"planned_write_bytes=397492208",
      "for f in (P / 'READY-FOR-DEVICE.json', O / 'READY-FOR-DEVICE.json'):":"for f in (P / 'DERIVATION-READY.json', O / 'DERIVATION-READY.json'):",
      '                shutil.rmtree(d)':'                print("preserved incomplete derivation: " + str(d), file=sys.stderr)',
    }
    for old,new in replacements.items():
      assert source.count(old)==1,(old,source.count(old));source=source.replace(old,new)
    private=Path(__file__).with_name('onecard_chain_derive.py');private.write_text(source)
    spec=importlib.util.spec_from_file_location('p196_private_generator',private);G=importlib.util.module_from_spec(spec);spec.loader.exec_module(G)
    G.OPS=OPS
    return G,dict(shared_path=str(shared.relative_to(ROOT)),shared_sha256=SHA(shared),private_sha256=SHA(private),edits=replacements)

def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    assert shutil.disk_usage('/').free>=27_000_000_000
    assert SHA(D/'build/device/own-rt-iq3')==DEVICE and SHA(D/'build/gnu-host/own-rt-iq3')==HOST
    assert SHA(P0/'build/device/own-rt-iq3')==PARENT_DEVICE and SHA(P0/'build/device/p58-cache-fixtures')==K1
    G,delta=load_generator()
    original_bracket=G.bracket_gate;original_derive=G.derive_packet
    def bracket(path):
      row=original_bracket(path);s=G.read(path);d=s['s58de_decision']
      G.refuse(d['screen_winner'] is True and d['chain_rule'] is True and d['kill_rules_fired']==[], 'diet chain admission failed')
      G.refuse(d['record_tok_s']==36.602512 and d['chain_bar_tok_s']==37.33456224,'diet bars changed')
      return row
    def inject(p,flags):
      parent=G.read(P0/'runtime-selection.json')
      suite,composition,views,selection=additive_sources((p/'suite_driver.py').read_text(),(p/'composition.py').read_text(),(p/'views.py').read_text(),parent,flags)
      for n,t in [('suite_driver.py',suite),('composition.py',composition),('views.py',views)]:G.put(p/n,t)
      G.save(p/'runtime-selection.json',selection)
    def bind(p,p0,flags):
      assert G.read(p/'runtime-selection.json')==dict(G.read(p0/'runtime-selection.json'),**G.selection_extra(flags))
    def derive(a,p0,p,flags,root,pairs):
      copied,gates,note=original_derive(a,p0,p,flags,root,pairs)
      # Candidate source bytes are copied without relabeling: these are the exact compiled inputs,
      # alongside parent-native history, never claimed as a rebuilt or independently qualified binary.
      for directory in ('native','frozen-inputs'):
        shutil.copytree(D/directory,p/'lineage/engine-source'/directory,ignore=shutil.ignore_patterns('__pycache__'))
      for leaf in ('build_dietengine.py','restore_build.py','restore-inputs.json','replaced-objects.json','native-dietengine-delta.patch','native-cache23-delta.patch','memory-plan.json','runtime-selection.json'):
        shutil.copy2(D/leaf,p/'lineage/engine-source'/leaf)
      for leaf in ('build.json','kernel-identity.json','diet-fixture.json','preparation.json'):
        target=p/'lineage/engine-source/proofs'/leaf;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(D/'evidence'/leaf,target)
      files={str(f.relative_to(p/'lineage/engine-source')):SHA(f) for f in (p/'lineage/engine-source').rglob('*') if f.is_file()}
      G.save(p/'engine-binding.json',dict(schema='packet196.engine-binding.v1',compiled_here=False,device_executed=False,
        engine=dict(path='build/device/own-rt-iq3',sha256=DEVICE,source=G.record(D/'build/device/own-rt-iq3',ROOT)),
        host_parser=dict(path='build/gnu-host/own-rt-iq3',sha256=HOST,source=G.record(D/'build/gnu-host/own-rt-iq3',ROOT)),
        k1_fixture=dict(path='build/device/p58-cache-fixtures',sha256=K1,source=G.record(P0/'build/device/p58-cache-fixtures',ROOT)),
        parent_engine_sha256=PARENT_DEVICE,source_snapshot=dict(directory='lineage/engine-source',source_files=[dict(relative_path=n,digest=h) for n,h in sorted(files.items())]),
        proof_scope='47 parent device images unchanged plus one diet image; 47/48 gate-up sites switch; layer2 retains its other-layout kernel; BF16 KV unchanged'))
      # Existing source literals in test fixtures and notes describe capacity. Preserve their fair
      # suite and submission safeguards while making the sole new kernel dimension explicit.
      f=p/'test_submission.py';t=f.read_text();t=t.replace("'--foreground-io','kernel'","'--foreground-io','kernel','--expert-gateup','diet'");t=t.replace('21.55 GB record line','exact expert gate/up diet').replace('30.5 GB DRM guard unchanged','unchanged capacity and 30.5 GB DRM guard');G.put(f,t)
      f=p/'rehearse_submission.py';t=f.read_text();t=t.replace("('--foreground-io','kernel')","('--foreground-io','kernel'),('--expert-gateup','diet')")
      t=t.replace("'35.892 / 36.546 / 35.929 / 36.569 / 35.925'","'36.579 / 37.573 / 36.599 / 37.583 / 36.601'")
      t=t.replace("'cmvjejvoi03qcrf0138emu5a6'","'cmvkcqznb002lng01fsrhjn7t'");G.put(f,t)
      f=p/'packet58_submission.py';t=f.read_text();t=t.replace("'+1.5 GB over the 21.55 GB record line; 30.5 GB DRM guard unchanged); zero-copy misses; '","'unchanged capacity and 30.5 GB DRM guard); exact expert gate/up diet; zero-copy misses; '")
      G.put(f,t)
      # All source transformations are retained as a patch against the committed parent later.
      return copied,{n:h for n,h in gates.items() if n not in ('evidence/chain-flags.json','evidence/pin-relocation.json')},note
    G.bracket_gate=bracket;G.inject=inject;G.bind_views=bind;G.derive_packet=derive
    argv=['--parent-orch',str(O0),'--packet',str(P),'--out',str(O),'--unit','packet58-onecard-diet-a','--output','evidence/card0-diet-a',
          '--binary',str(D/'build/device/own-rt-iq3'),'--host-binary',str(D/'build/gnu-host/own-rt-iq3'),'--bracket-summary',str(SCREEN/'summary.json'),
          '--threshold-file',str(ROOT/'scripts/packet58_onecard_record_threshold.json')]
    for k,v in FLAGS.items():argv+=['--flag',k[2:]+'='+v]
    rc=G.main(argv)
    if not O.exists():O.mkdir()
    shutil.copy2(__file__,O/'derive_diet_chain.py');shutil.copy2(Path(__file__).with_name('onecard_chain_derive.py'),O/'onecard_chain_derive.py')
    G.save(O/'derivation.json',dict(schema='packet196.derivation.v1',passed=rc==0,device_executed=False,argv=argv,generator_delta=delta,compiled_here=False,preparation_complete=False))
    return rc
if __name__=='__main__':raise SystemExit(main())
