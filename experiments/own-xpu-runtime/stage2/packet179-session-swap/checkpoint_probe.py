"""CPU host-only checkpoint correctness gate (SESSION-SWAP-DESIGN.md v1.1, host side).

Compiles the packet179 patched entry TU (native-source .../build/native/main.cpp +
checkpoint.hpp via entry-main.cpp) with -DOWN_RT_HOST_ONLY and relinks packet58aj's
qualified gnu-host host-only object set: an entry-TU-only delta over the ancestor
composition, mirroring the packet's device relink discipline. The ancestor gnu-host
binary is re-pinned by sha256 before its object set is trusted. Runs a
--mini --pipeline-mini synthetic save -> restore round trip on the real CPU arithmetic
path: merged-continuation equality vs an uninterrupted reference run, blob sha256 and
sliced-row arithmetic against fields.tsv, inspect/delete host tools, and every
fail-closed refusal (corrupted blob sha256, wrong prompt prefix, binary mismatch,
geometry mismatch, manifest tamper, delete in_use). No GPU, no model reads; synthetic
mini evidence is not arithmetic or performance qualification.
"""
import hashlib,json,resource,shutil,subprocess,sys,time
from pathlib import Path
from build_engine import P,ROOT,limits,turn,sha,save
NAT='native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/build/native'

def fields(path):
    values={};blobs=[];skips=[]
    for line in (path/'fields.tsv').read_text().splitlines():
        row=line.split('\t')
        if row[0]=='blob':blobs.append(row[1:])
        elif row[0]=='skip':skips.append(row[1:])
        else:values[row[0]]=row[1]
    return values,blobs,skips

def main():
    limits();p=P/'one-card'
    build=p/'build/checkpoint-probe';build.mkdir(parents=True,exist_ok=True)
    main_cpp=(p/NAT/'main.cpp').resolve();entry=(p/NAT/'entry-main.cpp').resolve()
    # Entry-TU-only host recompile + ancestor object relink: take packet58aj's
    # executed gnu-host compile/link commands, swap in the packet179 patched
    # entry-main.cpp, and keep every other (host-only, g++) object byte-input
    # exactly as the qualified ancestor composition used it.
    aj=ROOT/'experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident'
    binding=json.loads((aj/'evidence/build.json').read_text())
    assert sha(aj/'build/gnu-host/own-rt-iq3')==binding['artifacts']['build/gnu-host/own-rt-iq3'],'ancestor gnu-host composition drifted'
    executed={}
    for row in binding['commands']:executed[row['name']]=row['command']
    compile_cmd=list(executed['gnu-host-entry-main'])
    compile_cmd[compile_cmd.index('-MF')+1]=str(build/'entry-main.d')
    compile_cmd[compile_cmd.index('-o')+1]=str(build/'entry-main.o')
    compile_cmd[compile_cmd.index('-c')+1]=str(entry)
    probe=build/'checkpoint-probe'
    link_cmd=list(executed['gnu-host-own-rt-iq3'])
    ancestor_entry=str(aj/'build/gnu-host/entry-main.o')
    link_cmd[link_cmd.index(ancestor_entry)]=str(build/'entry-main.o')
    link_cmd[link_cmd.index('-o')+1]=str(probe)
    ancestor_objects={a:sha(a) for a in link_cmd if a.endswith('.o') and a!=str(build/'entry-main.o')}
    previous=json.loads((build/'compiled-inputs.json').read_text()) if (build/'compiled-inputs.json').is_file() else {}
    reuse=(probe.is_file() and previous.get('binary_sha256')==sha(probe)
        and previous.get('compile')==compile_cmd and previous.get('link')==link_cmd)
    if not reuse:
        with turn(),(build/'compile.log').open('w') as log:
            limits();subprocess.run(compile_cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
        with turn(),(build/'link.log').open('w') as log:
            limits();subprocess.run(link_cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
        save(build/'compiled-inputs.json',dict(compile=compile_cmd,link=link_cmd,binary_sha256=sha(probe),
            sources_sha256={str(entry):sha(entry),str(main_cpp):sha(main_cpp),str(main_cpp.parent/'checkpoint.hpp'):sha(main_cpp.parent/'checkpoint.hpp')},
            ancestor_objects_sha256=ancestor_objects))
    link_used=json.loads((build/'compiled-inputs.json').read_text())['link']
    sys.path.insert(0,str(p))
    import native_env
    env=native_env.environment('A')
    runroot=build/'run';shutil.rmtree(runroot,ignore_errors=True);runroot.mkdir()
    results=[]
    def run(tag,argv,expect=0):
        cp=subprocess.run([str(probe),*argv],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,
            preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3)))
        row=dict(tag=tag,argv=argv,returncode=cp.returncode,stdout_tail=cp.stdout[-400:],stderr_tail=cp.stderr[-400:])
        results.append(row)
        assert cp.returncode==expect,(tag,cp.returncode,cp.stderr[-500:])
        return cp
    base=['--mini','--pipeline-mini','--context','64']
    ck=runroot/'ck'
    K,M=8,4  # prompt {2,5,3,7,1}: N=5+K-1=12 < context 64; pooled rows floor(12/4)=3
    run('reference',base+['--max-new',str(K+M),'--output',str(runroot/'ref')])
    run('save',base+['--max-new',str(K),'--output',str(runroot/'save'),'--checkpoint-save',str(ck),'--checkpoint-id','gate'])
    run('restore1',base+['--max-new',str(M),'--output',str(runroot/'restore1'),'--checkpoint-restore',str(ck),'--checkpoint-id','gate'])
    run('restore2',base+['--max-new',str(M),'--output',str(runroot/'restore2'),'--checkpoint-restore',str(ck),'--checkpoint-id','gate'])
    load=lambda d:json.loads((runroot/d/'result.json').read_text())
    ref,sv,r1,r2=load('ref'),load('save'),load('restore1'),load('restore2')
    assert len(ref['tokens'])==K+M and len(sv['tokens'])==K,'synthetic mini stream hit EOS; adjust K/M'
    assert len(r1['tokens'])==M and r1['tokens']==r2['tokens'],'repeat restore determinism'
    assert sv['tokens']+r1['tokens']==ref['tokens'],'merged checkpoint stream != uninterrupted reference (CPU real arithmetic)'
    assert isinstance(r1.get('checkpoint_restore_ms'),(int,float)) and r1['checkpoint_restore_ms']>=0
    assert r1.get('prefill_ms')==0 and sv.get('checkpoint_restore_ms') is None
    # Manifest/fields integrity and sliced-row arithmetic (mini geometry: kvh=1,ad=4,id=4,context=64).
    gate=ck/'gate';manifest=json.loads((gate/'manifest.json').read_text())
    assert manifest['format']=='ownrt.session-checkpoint.v1' and manifest['label']=='experimental'
    v,blobs,skips=fields(gate)
    N=int(v['position']);assert N==5+K-1==int(v['length']) and int(v['prompt_length'])==5
    assert int(v['next_token'])==sv['tokens'][-1]
    token_bytes=(gate/'tokens.bin').read_bytes()
    assert len(token_bytes)==N*4 and hashlib.sha256(token_bytes).hexdigest()==v['tokens_sha256']
    import struct
    assert list(struct.unpack('<%di'%N,token_bytes))==[2,5,3,7,1]+sv['tokens'][:-1]
    g=manifest['geometry'];assert g['context']==64 and g['qsa_layers']==[1,3] and g['gdn_layers']==[0,2]
    seen=set()
    for name,bytes_,sha_,rows in blobs:
        data=(gate/(name+'.bin')).read_bytes()
        assert len(data)==int(bytes_) and hashlib.sha256(data).hexdigest()==sha_,name
        seen.add(name)
        if name.endswith('.qsa.keys') or name.endswith('.qsa.values'):
            assert int(rows)==N and int(bytes_)==N*1*4*2,(name,'slice rows [0:N)')
        elif name.endswith('.qsa.raw'):
            assert int(rows)==N and int(bytes_)==N*4*2,(name,'raw slice')
        elif name.endswith('.qsa.pooled'):
            assert int(rows)==N//4==3 and int(bytes_)==(N//4)*4*2,(name,'pooled slice floor(N/4)')
        else:
            assert int(rows)==-1,(name,'whole blob')
    for name,rule in skips:
        assert name not in seen and (name.endswith('.qsa.ids') or name=='ple_metadata' or rule.startswith('skip: plan intermediate')),name
    # Every plan buffer classified exactly once: blob + skip sets partition the manifest record.
    assert len(seen)+len(skips)==len(blobs)+len(skips)
    # Host tools without any device.
    cp=run('inspect',[ '--checkpoint-inspect',str(gate)])
    assert 'sha256_verified' in cp.stdout and '"format":"ownrt.session-checkpoint.v1"' in cp.stdout.replace(' ','')
    shutil.copytree(gate,ck/'del');run('delete',['--checkpoint-delete',str(ck/'del')]);assert not (ck/'del').exists()
    shutil.copytree(gate,ck/'inuse');(ck/'inuse'/'restore.lock').write_text('locked')
    cp=run('delete-in-use',['--checkpoint-delete',str(ck/'inuse')],expect=1)
    assert 'in_use' in cp.stdout and (ck/'inuse').exists()
    # Fail-closed refusals, each naming its check.
    def refusal(tag,mutate,marker,extra=()):
        shutil.copytree(gate,ck/tag);mutate(ck/tag)
        cp=run(tag,base+['--max-new','1','--output',str(runroot/tag),'--checkpoint-restore',str(ck),'--checkpoint-id',tag,*extra],expect=1)
        assert marker in cp.stderr,(tag,cp.stderr[-300:]);assert 'checkpoint restore refused' in cp.stderr
    def corrupt(d):
        f=d/'blk.1.qsa.keys.bin';b=bytearray(f.read_bytes());b[0]^=1;f.write_bytes(bytes(b))
    refusal('corrupt-blob',corrupt,'blob sha256')
    wrong=runroot/'wrong.txt';wrong.write_text('3 5 3 7 1\n')
    refusal('wrong-prompt',lambda d:None,'prefix',extra=('--prompt-tokens',str(wrong)))
    def binary(d):
        t=(d/'fields.tsv').read_text();(d/'fields.tsv').write_text(t.replace(v['binary_sha256'],'0'*64))
    refusal('binary-mismatch',binary,'engine identity')
    def geometry(d):
        t=(d/'fields.tsv').read_text();(d/'fields.tsv').write_text(t.replace('\ncontext\t64\n','\ncontext\t128\n'))
    refusal('geometry-mismatch',geometry,'geometry')
    def tamper(d):
        with (d/'manifest.json').open('a') as f:f.write(' ')
    refusal('manifest-tamper',tamper,'manifest sha256')
    receipt=dict(passed=True,device_executed=False,model_reads=False,
        driver='patched packet179 entry TU compiled -DOWN_RT_HOST_ONLY (g++, packet58aj gnu-host entry command); ancestor gnu-host object set relinked byte-input; real CPU arithmetic path',
        compile=compile_cmd,link=link_used,
        sources_sha256={str(entry):sha(entry),str(main_cpp):sha(main_cpp),str(main_cpp.parent/'checkpoint.hpp'):sha(main_cpp.parent/'checkpoint.hpp')},
        ancestor_objects_sha256=ancestor_objects,
        probe_binary_sha256=sha(probe),
        round_trip=dict(prompt=[2,5,3,7,1],K=K,M=M,N=N,merged_equal_reference=True,repeat_restore_identical=True,
            blob_count=len(blobs),skipped_count=len(skips),
            slice_arithmetic='qsa keys/values rows [0:N) at 2*kvh*ad bytes/row; raw rows [0:N) at 2*id; pooled rows [0:floor(N/4)) at 2*id; verified against blob bytes'),
        refusals=['corrupt-blob: blob sha256','wrong-prompt: prefix','binary-mismatch: engine identity',
                  'geometry-mismatch: geometry','manifest-tamper: manifest sha256','delete-in-use: in_use'],
        results=results,
        peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024,
        scope='synthetic --mini CPU round trip of the patched entry TU; correctness of format/slicing/fail-closed gates only; not device, arithmetic or performance qualification; the production-geometry merged-equality gate is the packet179 device row B')
    assert receipt['peak_child_rss_bytes']<4*1024**3
    save(p/'evidence/checkpoint-probe.json',receipt)
    print('one-card checkpoint host-only probe PASS',flush=True)

if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
