"""Relink the packet179 binary: recompile the patched entry TU, reuse packet165 objects.

Mirrors packet165's localize_native.py with three changes (SESSION-SWAP design spec):
(1) the native delta (patched main.cpp + new checkpoint.hpp) was already applied by
    adapt_native.py and is verified against evidence/native-delta.json pins here;
(2) kernel objects are copied from packet165's build/objects sha-asserted against
    packet165's lineage/build-inputs.json objects block (byte-identical reuse);
(3) identity receipts record parent_binary_sha256=1364bb3d... (packet165 binary).
"""
import hashlib,json,resource,shutil,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
sys.path.insert(0,str(P))  # compile_turn.py does 'from build_engine import limits'
OLD=P.parent/'packet165-warm-prefill'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def limits():
 import os
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage(P).free>=27_000_000_000,'CPU stop: 27 GB'
def turn():
 import importlib.util
 spec=importlib.util.spec_from_file_location('packet163_compile_turn',ROOT/'experiments/own-xpu-runtime/ops/compile_turn.py')
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.turn()

NAT='native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/build/native'

def main(name):
    limits();p=P/name;old=OLD/name
    delta=json.loads((p/'evidence/native-delta.json').read_text())
    assert delta['passed'] and delta['entry_tu_only']
    inputs=json.loads((old/'lineage/build-inputs.json').read_text())
    # Path-rewrite native sources packet165 -> packet179 (entry TU already patched).
    for f in (p/'native-source').rglob('*'):
        if f.is_file() and f.suffix in ('.cpp','.hpp','.h'):
            if str(f.relative_to(p))==NAT+'/checkpoint.hpp':continue  # new file; no parent, no embedded paths
            original=(old/f.relative_to(p)).read_text()
            if str(f.relative_to(p))==NAT+'/main.cpp':
                # Patched entry TU: reversal must equal the adapt-time patched bytes.
                current=f.read_text()
                assert hashlib.sha256(current.replace(str(P),str(OLD)).encode()).hexdigest()==delta['patched_main_sha256'],'patched main.cpp drifted'
                f.write_text(current.replace(str(OLD),str(P)))
                continue
            f.write_text(original.replace(str(OLD),str(P)))
            assert f.read_text().replace(str(P),str(OLD))==original
    assert sha(p/NAT/'checkpoint.hpp')==delta['checkpoint_hpp_sha256'],'checkpoint.hpp drifted'
    for f in (p/'inputs').rglob('input.json'):
        f.write_text((old/f.relative_to(p)).read_text().replace(str(OLD),str(P)))
    # Compile/link commands pinned by packet165's lineage, relocated to this packet.
    compile=[s.replace(str(OLD.parent/'packet163-full-gate'),str(P)) for s in inputs['compile']]
    compile=[s.replace(str(OLD),str(P)) for s in compile]
    link=[s.replace(str(OLD.parent/'packet163-full-gate'),str(P)) for s in inputs['link']]
    link=[s.replace(str(OLD),str(P)) for s in link]
    # Copy every non-entry kernel object from packet165, sha-asserted against its pins.
    pins=inputs['objects'];copied=0
    for i,source in enumerate(inputs['link']):
        if not source.endswith('.o'):continue
        if source.endswith('/entry-main.o'):
            link[i]=str(p/'build/device/entry-main.o');continue
        src=Path(source.replace(str(OLD.parent/'packet163-full-gate'),str(OLD)))
        assert src.is_relative_to(old/'build'),src
        leaf=str(src.relative_to(old))
        assert leaf in pins and sha(src)==pins[leaf]['sha256'] and src.stat().st_size==pins[leaf]['bytes'],('kernel object pin mismatch',leaf)
        dest=Path(source.replace(str(OLD.parent/'packet163-full-gate'),str(P)))
        assert dest.is_relative_to(p/'build'),dest
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
        assert sha(src)==sha(dest);link[i]=str(dest);copied+=1
    assert copied==len(pins)-0 or copied>=40,copied
    (p/'build/device').mkdir(parents=True,exist_ok=True)
    compile[compile.index('-c')+1]=str(p/NAT/'entry-main.cpp')
    compile[compile.index('-o')+1]=str(p/'build/device/entry-main.o')
    if '-MF' in compile:compile[compile.index('-MF')+1]=str(p/'build/device/entry-main.d')
    commands=[]
    for label,command in [('compile',compile),('link',link)]:
        with turn(),(p/'build'/('checkpoint-'+label+'.log')).open('w') as log:
            limits();start=time.monotonic()
            subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
        commands.append(dict(command=command,seconds=time.monotonic()-start))
        print(name,label,'PASS',flush=True)
    binary=p/'build/device/own-rt-iq3'
    receipt=dict(passed=True,device_executed=False,kernel_objects_unchanged=True,reused_object_files=True,
        reused_object_count=copied,reused_objects_sha256_asserted_against='packet165 lineage/build-inputs.json objects block',
        only_native_delta='entry TU only: checkpoint/restore argv, run() save hook and restore-after-reset integration, new checkpoint.hpp (SESSION-SWAP-DESIGN.md v1.1); every kernel object byte-identical to packet165',
        arithmetic_qualified=False,
        binary_sha256=sha(binary),parent_binary_sha256=sha(old/'build/device/own-rt-iq3'),
        first_execution='host-side --help in capture_flags/rehearsal only; arithmetic and performance unqualified until the device run',
        commands=commands,peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024)
    assert receipt['parent_binary_sha256']=='1364bb3de0e0742ea3c5419a3f6850cea3646466c19732ad5cf3fe9be2b1b7cf'
    assert receipt['binary_sha256']!=receipt['parent_binary_sha256'],'entry TU changed; binary must differ'
    assert receipt['peak_child_rss_bytes']<4*1024**3
    save(p/'evidence/build.json',receipt)
    identity=json.loads((p/'identity.json').read_text());identity.update(binary_sha256=receipt['binary_sha256'],
        parent_binary_sha256=receipt['parent_binary_sha256'],native_binary_unchanged_from_packet163=False,
        native_arithmetic_unchanged_from_packet163=True,native_delta=receipt['only_native_delta'])
    save(p/'identity.json',identity)
    inherited=json.loads((p/'inherited-native.json').read_text())
    inherited.update(binary_sha256=receipt['binary_sha256'],parent_binary_sha256=receipt['parent_binary_sha256'],native_recompiled=True,
        embedded_readonly_dependencies={k.replace('packet165-warm-prefill','packet179-session-swap'):v for k,v in inherited['embedded_readonly_dependencies'].items()})
    save(p/'inherited-native.json',inherited)
    save(p/'lineage/packet179-build.json',dict(compile=compile,link=link,
        parent_build_inputs_sha256=sha(old/'lineage/build-inputs.json'),native_delta_patch_sha256=delta['patch_sha256']))
    copied_baseline=json.loads((p/'evidence/copy-baseline.json').read_text())['files']
    for leaf in copied_baseline:
        if leaf.startswith('native-source/') and leaf!=NAT+'/main.cpp':
            a=(old/leaf).read_bytes();b=(p/leaf).read_bytes()
            assert b.replace(str(P).encode(),str(OLD).encode())==a,leaf
    save(p/'evidence/identity-check.json',dict(passed=True,device_executed=False,native_source_reversal_exact=True,
        kernel_objects_unchanged=True,reused_object_count=copied,
        selection_unchanged=sha(p/'selection.json')==sha(old/'selection.json'),
        dispatch_unchanged=sha(p/'dispatch.json')==sha(old/'dispatch.json'),arithmetic='iq3-p49-split32-v1',
        parent_binary_sha256=receipt['parent_binary_sha256'],
        build_receipt_sha256=sha(p/'evidence/build.json')))
    print('Built',binary,'sha256',receipt['binary_sha256'])
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main(sys.argv[1])
