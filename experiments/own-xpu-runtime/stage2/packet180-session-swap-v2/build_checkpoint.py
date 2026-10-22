"""Relink the packet180 binary: recompile the patched entry TU, reuse packet165 objects.

Same procedure as packet179's build_checkpoint.py (packet165's localize_native.py with three
changes): (1) the native delta (main.cpp + checkpoint.hpp v2) was applied by adapt_native.py
and is verified against evidence/native-delta.json pins here; (2) kernel objects are copied
from packet165's build/objects, sha-asserted against packet165's lineage/build-inputs.json
objects block (byte-identical reuse); (3) the identity receipts record the arithmetic parent
packet165 (1364bb3d...) and the previous checkpoint engine packet179 (8d185384...).
CPU-only: nice 19, cores 8-15,24-31, 4 GiB address-space cap, 27 GB CPU disk stop (build_engine).
"""
import hashlib,json,resource,shutil,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
sys.path.insert(0,str(P))  # compile_turn.py does 'from build_engine import limits'
from build_engine import sha,save,limits,turn
OLD=P.parent/'packet165-warm-prefill'
P179=P.parent/'packet179-session-swap'
NAT='native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/build/native'

def main(name):
    limits();p=P/name;old=OLD/name
    delta=json.loads((p/'evidence/native-delta.json').read_text())
    assert delta['passed'] and delta['entry_tu_only']
    inputs=json.loads((old/'lineage/build-inputs.json').read_text())
    # Path-relocate every native source from packet165's original bytes to this packet; the
    # entry TU is the adapt-time patched text (packet165-path-normalized) relocated the same way.
    for f in (p/'native-source').rglob('*'):
        if f.is_file() and f.suffix in ('.cpp','.hpp','.h'):
            rel=str(f.relative_to(p))
            if rel==NAT+'/checkpoint.hpp':continue  # new in packet179, rewritten by packet180; no embedded paths
            if rel==NAT+'/main.cpp':
                current=f.read_text()
                assert hashlib.sha256(current.replace(str(P),str(OLD)).encode()).hexdigest()==delta['patched_main_sha256'],'patched main.cpp drifted'
                f.write_text(current.replace(str(OLD),str(P)))
                continue
            original=(old/f.relative_to(p)).read_text()
            f.write_text(original.replace(str(OLD),str(P)))
            assert f.read_text().replace(str(P),str(OLD))==original
    assert sha(p/NAT/'checkpoint.hpp')==delta['checkpoint_hpp_sha256']==sha(P/'checkpoint.hpp'),'checkpoint.hpp drifted'
    assert 'packet179-session-swap' not in (p/NAT/'main.cpp').read_text()
    for f in (p/'inputs').rglob('input.json'):
        f.write_text((old/f.relative_to(p)).read_text().replace(str(OLD),str(P)))
    # Compile/link commands pinned by packet165's lineage, relocated to this packet.
    compile=[s.replace(str(OLD.parent/'packet163-full-gate'),str(P)) for s in inputs['compile']]
    compile=[s.replace(str(OLD),str(P)) for s in compile]
    link=[s.replace(str(OLD.parent/'packet163-full-gate'),str(P)) for s in inputs['link']]
    link=[s.replace(str(OLD),str(P)) for s in link]
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
    assert copied==41,copied
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
    previous=json.loads((P179/name/'evidence/build.json').read_text())['binary_sha256']
    receipt=dict(passed=True,device_executed=False,kernel_objects_unchanged=True,reused_object_files=True,
        reused_object_count=copied,reused_objects_sha256_asserted_against='packet165 lineage/build-inputs.json objects block',
        only_native_delta='entry TU only: checkpoint v2 (append, restore-then-save, tokenizer identity, manifest.json single source of truth, shared sibling lock, inspect/inspect-metadata/validated delete) over the packet179 checkpoint delta; every kernel object byte-identical to packet165',
        arithmetic_qualified=False,
        binary_sha256=sha(binary),parent_binary_sha256=sha(old/'build/device/own-rt-iq3'),previous_checkpoint_binary_sha256=previous,
        first_execution='host-side --help in capture_flags/rehearsal only; arithmetic and performance unqualified until the device run',
        commands=commands,peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024)
    assert receipt['parent_binary_sha256']=='1364bb3de0e0742ea3c5419a3f6850cea3646466c19732ad5cf3fe9be2b1b7cf'
    assert previous=='8d18538475e00200032846d51dce11e0d38392dc9962778ffd01b03dd75394a7'
    assert receipt['binary_sha256'] not in (receipt['parent_binary_sha256'],previous),'entry TU changed; binary must differ'
    assert receipt['peak_child_rss_bytes']<4*1024**3
    save(p/'evidence/build.json',receipt)
    identity=json.loads((p/'identity.json').read_text());identity.update(binary_sha256=receipt['binary_sha256'],
        parent_binary_sha256=receipt['parent_binary_sha256'],native_binary_unchanged_from_packet163=False,
        native_arithmetic_unchanged_from_packet163=True,native_delta=receipt['only_native_delta'])
    save(p/'identity.json',identity)
    inherited=json.loads((p/'inherited-native.json').read_text())
    inherited.update(binary_sha256=receipt['binary_sha256'],parent_binary_sha256=receipt['parent_binary_sha256'],native_recompiled=True,
        embedded_readonly_dependencies={k.replace('packet179-session-swap',P.name):v for k,v in inherited['embedded_readonly_dependencies'].items()})
    save(p/'inherited-native.json',inherited)
    save(p/'lineage/packet180-build.json',dict(compile=compile,link=link,
        parent_build_inputs_sha256=sha(old/'lineage/build-inputs.json'),native_delta_patch_sha256=delta['patch_sha256']))
    copied_baseline=json.loads((p/'evidence/copy-baseline.json').read_text())['files']
    for leaf in copied_baseline:
        if leaf.startswith('native-source/') and leaf not in (NAT+'/main.cpp',NAT+'/checkpoint.hpp'):
            a=(old/leaf).read_bytes();b=(p/leaf).read_bytes()
            assert b.replace(str(P).encode(),str(OLD).encode())==a,leaf
    save(p/'evidence/identity-check.json',dict(passed=True,device_executed=False,native_source_reversal_exact=True,
        kernel_objects_unchanged=True,reused_object_count=copied,
        selection_unchanged=sha(p/'selection.json')==sha(old/'selection.json'),
        dispatch_unchanged=sha(p/'dispatch.json')==sha(old/'dispatch.json'),arithmetic='iq3-p49-split32-v1',
        parent_binary_sha256=receipt['parent_binary_sha256'],previous_checkpoint_binary_sha256=previous,
        build_receipt_sha256=sha(p/'evidence/build.json')))
    print('Built',binary,'sha256',receipt['binary_sha256'])
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main(sys.argv[1])
