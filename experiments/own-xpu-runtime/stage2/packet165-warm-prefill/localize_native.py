"""Relocate native constant/include paths; reuse every packet163 kernel object.

The lanequeue pin guard requires private embedded paths even for frozen parents.
Only this entry-path relocation is compiled; no kernel implementation changes.
"""
import hashlib,json,resource,shutil,subprocess,sys,time
from pathlib import Path
from build_engine import P,ROOT,limits,turn,sha,save
OLD=P.parent/'packet163-full-gate'
def main(name):
    limits();p=P/name;old=OLD/name
    inputs=json.loads((old/'lineage/build-inputs.json').read_text())
    for f in (p/'native-source').rglob('*'):
        if f.is_file() and f.suffix in ('.cpp','.hpp','.h'):
            original=(old/f.relative_to(p)).read_text()
            f.write_text(original.replace(str(OLD),str(P)))
            assert f.read_text().replace(str(P),str(OLD))==original
    for f in (p/'inputs').rglob('input.json'):
        f.write_text((old/f.relative_to(p)).read_text().replace(str(OLD),str(P)))
    compile=[s.replace(str(OLD),str(P)) for s in inputs['compile']]
    link=[s.replace(str(OLD),str(P)) for s in inputs['link']]
    for source in inputs['link']:
        if source.endswith('.o') and not source.endswith('/entry-main.o'):
            src=Path(source);dest=Path(source.replace(str(OLD),str(P)))
            assert dest.is_relative_to(p/'build') and src.is_relative_to(old/'build')
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
            assert sha(src)==sha(dest)
    commands=[]
    for label,command in [('compile',compile),('link',link)]:
        with turn(),(p/'build'/('relocate-'+label+'.log')).open('w') as log:
            limits();start=time.monotonic()
            subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
        commands.append(dict(command=command,seconds=time.monotonic()-start))
        print(name,label,'PASS',flush=True)
    receipt=dict(passed=True,device_executed=False,kernel_objects_unchanged=True,
        only_native_delta='absolute include and constant paths packet163-full-gate -> packet165-warm-prefill',
        binary_sha256=sha(p/'build/device/own-rt-iq3'),parent_binary_sha256=sha(old/'build/device/own-rt-iq3'),
        commands=commands,peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024)
    assert receipt['peak_child_rss_bytes']<4*1024**3
    save(p/'evidence/build.json',receipt)
    identity=json.loads((p/'identity.json').read_text());identity.update(binary_sha256=receipt['binary_sha256'],native_binary_unchanged_from_packet163=False,
        native_arithmetic_unchanged_from_packet163=True,native_delta=receipt['only_native_delta'])
    save(p/'identity.json',identity)
    inherited=json.loads((p/'inherited-native.json').read_text())
    inherited.update(binary_sha256=receipt['binary_sha256'],parent_binary_sha256=receipt['parent_binary_sha256'],native_recompiled=True,
        embedded_readonly_dependencies={k.replace('packet163-full-gate','packet165-warm-prefill'):v for k,v in inherited['embedded_readonly_dependencies'].items()})
    save(p/'inherited-native.json',inherited)
    save(p/'lineage/packet165-build.json',dict(compile=compile,link=link,parent_build_inputs_sha256=sha(old/'lineage/build-inputs.json')))
    copied=json.loads((p/'evidence/copy-baseline.json').read_text())['files']
    for leaf in copied:
        if leaf.startswith('native-source/'):
            a=(old/leaf).read_bytes();b=(p/leaf).read_bytes()
            assert b.replace(str(P).encode(),str(OLD).encode())==a,leaf
    save(p/'evidence/identity-check.json',dict(passed=True,device_executed=False,native_source_reversal_exact=True,
        kernel_objects_unchanged=True,selection_unchanged=sha(p/'selection.json')==sha(old/'selection.json'),
        dispatch_unchanged=sha(p/'dispatch.json')==sha(old/'dispatch.json'),arithmetic='iq3-p49-split32-v1',
        build_receipt_sha256=sha(p/'evidence/build.json')))
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2)
    main(sys.argv[1])
