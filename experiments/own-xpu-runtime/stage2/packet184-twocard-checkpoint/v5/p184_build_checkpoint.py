"""Packet184 build: entry TU recompiled with the two-card checkpoint delta; every parent object relinked.

CPU-only. Same procedure as the copied v5 build (p184_v5_build_engine.py, packet153's): compile
v5/native-src/entry-main.cpp (main.cpp + rank.hpp + mtp.hpp + v5/native/checkpoint_tp2.hpp) and
the unchanged p49d_submit.cpp for gnu-host and device, relink the 78 packet136-lineage parent
objects pinned in immutable-binaries.json (sha256 asserted before linking), refuse any compiler or
linker warning. Before building it proves the native delta: every copied native file other than the
four named delta files still has its copy-time digest (lineage/packet184-copy.json), and it writes
the unified delta against packet153's sources (lineage/checkpoint-delta.patch).

Limits (this host's CPU scripts only, never device): nice 19, cores 8-15,24-31, 4 GiB address space,
CPU disk stop 27 GB free (packet181 build_engine.limits precedent; the owner floor is 25 GB).
The parent reproduction (build/parent, built by the copied p184_v5_build_engine.py before any delta)
reproduced packet153's recorded binaries byte-for-byte; that receipt is checked here, not rebuilt.
"""
import difflib,hashlib,importlib.util,json,os,resource,shutil,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;LOCAL=P.parent;ROOT=P.parents[4];STAGE=P.parents[1];B=P/'build'
CHECKED=LOCAL/'build/checked'/LOCAL.relative_to(ROOT)
NB=LOCAL/'native-base'/LOCAL.relative_to(ROOT)
DELTA={'v5/native-src/main.cpp','v5/native-src/rank.hpp','v5/native-src/mtp.hpp',
       'native-base/'+str(LOCAL.relative_to(ROOT))+'/native_controller.hpp'}
NEW={'v5/native/checkpoint_tp2.hpp','v5/native/checkpoint_format.hpp','v5/native/checkpoint_tool.cpp',
     'v5/native/checkpoint_shape_entry.cpp'}   # the last is the CPU production-shape fixture entry, never in the engine
P153=STAGE/'packet153-snapshot-host'
P153_BINARIES={'gnu-host':'a36f14054013ce42609663c5dc5deaebe0320a4d0a0198a5be56a15e97003bb0',
               'device':'106fa3adcb2df0cacdf3048de894614b55a7cfda74b951443ed864e0d9495189'}

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def save(p,row):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(row,indent=2)+'\n')
def limits():
    assert os.getpriority(os.PRIO_PROCESS,0)==19,'nice 19 required'
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32)),'cores 8-15,24-31 required'
    assert shutil.disk_usage('/').free>=27_000_000_000,'CPU disk stop: 27 GB free'
def compiler_turn():
    if str(LOCAL) not in sys.path:sys.path.append(str(LOCAL))
    spec=importlib.util.spec_from_file_location('ops_compile_turn',STAGE.parent/'ops/compile_turn.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.turn()
def run(cmd,name):
    limits();t=time.monotonic();log=B/(name+'.log')
    with compiler_turn(),log.open('w') as f:
        subprocess.run(list(map(str,cmd)),stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1200)
    text=log.read_text()
    assert 'warning' not in text.lower(),'compiler/linker warning in '+name+' (see '+str(log)+')'
    print(name,'PASS',flush=True);return dict(name=name,command=list(map(str,cmd)),seconds=round(time.monotonic()-t,3),log_bytes=len(text))

def native_delta():
    copy=json.loads((LOCAL/'lineage/packet184-copy.json').read_text())
    digests={row['name']:row for row in copy['copied']}
    roots=('v5/native-src/','v5/native/','native-base/')
    unchanged,changed=[],[]
    for name,row in sorted(digests.items()):
        if not name.startswith(roots):continue
        now=sha(LOCAL/name)
        if name in DELTA:
            assert now!=row['digest'],'delta file unchanged: '+name;changed.append(name)
        else:
            assert now==row['digest'],'non-delta native file changed after the copy: '+name;unchanged.append(name)
    assert set(changed)==DELTA,set(changed)^DELTA
    present={str(f.relative_to(LOCAL)) for r in roots for f in (LOCAL/r).rglob('*') if f.is_file()}
    extra=present-set(digests)
    assert extra==NEW,('unexpected new native files',extra^NEW)
    patch=[]
    for name in sorted(DELTA|NEW):
        source=digests.get(name,{}).get('source_relpath')
        old=(P153/source).read_text().replace('packet153-snapshot-host',LOCAL.name).replace('p153_v5_','p184_v5_').replace('p153_ops_','p184_ops_') if source else ''
        new=(LOCAL/name).read_text()
        patch+=difflib.unified_diff(old.splitlines(True),new.splitlines(True),'packet153/'+(source or '/dev/null'),'packet184/'+name)
    out=LOCAL/'lineage/checkpoint-delta.patch';out.write_text(''.join(patch))
    receipt=dict(passed=True,device_executed=False,entry_tu_only=True,
        delta_files=sorted(DELTA),new_files=sorted(NEW),unchanged_native_files=len(unchanged),
        patch=str(out.relative_to(ROOT)),patch_sha256=sha(out),patch_lines=sum(1 for _ in out.open()),
        delta_sha256={n:sha(LOCAL/n) for n in sorted(DELTA|NEW)},
        kernel_objects_unchanged=True,
        scope=('main.cpp: device-free host-tool hook; rank.hpp: op 15 stage/verify/apply, op 10 resume start, p149 probe at '
               'production geometry only; mtp.hpp: DraftRuntime checkpoint view/host restore; native_controller.hpp: '
               'run(b,c,start=0) resume preamble; checkpoint_tp2.hpp: the checkpoint itself. No kernel source changed.'))
    save(P/'evidence/native-delta.json',receipt);return receipt

def parent_reproduction():
    row=json.loads((B/'parent/build-receipt.json').read_text())
    got={k.split('/build/')[1].split('/')[0]:v for k,v in row['artifacts'].items()}
    old=json.loads((LOCAL/'lineage-inputs/packet153-own/v5/evidence/build.json').read_text())['artifacts']
    recorded={k.split('/build/')[1].split('/')[0]:v for k,v in old.items()}
    assert got==recorded==P153_BINARIES,(got,recorded)
    for mode,digest in P153_BINARIES.items():assert sha(B/'parent'/mode/'own-rt-iq3')==digest
    return dict(passed=True,parent_binaries=P153_BINARIES,
        evidence='build/parent/build-receipt.json (copied p184_v5_build_engine.py before any delta) == lineage-inputs/packet153-own/v5/evidence/build.json artifacts',
        meaning='the relocated toolchain reproduces packet153\'s device binary (lane-B bracket 2026-10-19, controls 58.638/58.671/58.663 tok/s) byte for byte')

def main():
    limits();delta=native_delta();reproduction=parent_reproduction()
    (LOCAL/'build').mkdir(exist_ok=True)
    if not (LOCAL/'build/checked').exists():(LOCAL/'build/checked').symlink_to('../native-base',target_is_directory=True)
    pinned=json.loads((LOCAL/'immutable-binaries.json').read_text())
    prior=json.loads((LOCAL/'lineage-inputs/packet136-history/engine-commands.json').read_text())
    commands,artifacts,inherited=[],{},{}
    for mode in ('gnu-host','device'):
        dest=B/mode
        if dest.exists():shutil.rmtree(dest)
        dest.mkdir(parents=True)
        args=list(next(r['command'] for r in prior if r['name']==mode+'-entry-main'));args=args[:args.index('-o')]
        args=[v for v in args if not v.startswith(('-I','-O'))]+['-O2','-I'+str(CHECKED),'-I'+str(LOCAL)]
        for stem in ('entry-main','p49d_submit'):
            src=P/'native-src/entry-main.cpp' if stem=='entry-main' else CHECKED/'p49d_submit.cpp'
            commands.append(run([*args,'-c',src,'-o',dest/(stem+'.o')],mode+'-'+stem))
        link=list(next(r['command'] for r in prior if r['name']==mode+'-link'));link[link.index('-o')+1]=str(dest/'own-rt-iq3')
        relinked=0
        for i,arg in enumerate(link):
            if not arg.endswith('.o'):continue
            stem=next((s for s in ('entry-main','p49d_submit') if Path(arg).name.endswith((s+'.o',s+'.cpp.o'))),None)
            if stem:link[i]=str(dest/(stem+'.o'));continue
            src=Path(arg);assert sha(src)==pinned[str(src.resolve())],'frozen parent object changed: '+str(src)
            target=dest/'inherited'/src.name;target.parent.mkdir(exist_ok=True)
            if not target.exists():target.symlink_to(src.resolve())
            assert sha(src)==sha(target);inherited[str(src.resolve().relative_to(ROOT))]=sha(target);link[i]=str(target);relinked+=1
        commands.append(run(link,mode+'-link'))
        artifacts[str((dest/'own-rt-iq3').relative_to(ROOT))]=sha(dest/'own-rt-iq3')
        commands[-1]['relinked_parent_objects']=relinked
    assert len(inherited)==len(pinned)==78,(len(inherited),len(pinned))
    # Device-free checkpoint tool: host-only g++ build, libcrypto only (no SYCL, no engine objects),
    # with the engine gnu-host warning policy (no -Wall; any warning still fails the build).
    tool=B/'tool';shutil.rmtree(tool,ignore_errors=True);tool.mkdir(parents=True)
    commands.append(run(['/usr/bin/g++','-std=gnu++20','-O2','-Werror=return-type','-fno-fast-math','-ffp-contract=off',
                         '-I'+str(P/'native'),P/'native/checkpoint_tool.cpp','-o',tool/'own-rt-ckpt-tool','-lcrypto'],'tool-build'))
    links=subprocess.run(['readelf','-d',str(tool/'own-rt-ckpt-tool')],capture_output=True,text=True,check=True).stdout.lower()
    assert not any(x in links for x in ('libsycl','libze_loader','libur_loader','libopencl')),'tool must not link a device runtime'
    artifacts[str((tool/'own-rt-ckpt-tool').relative_to(ROOT))]=sha(tool/'own-rt-ckpt-tool')
    for mode,digest in P153_BINARIES.items():
        assert artifacts[str((B/mode/'own-rt-iq3').relative_to(ROOT))]!=digest,'entry TU changed; binary must differ from packet153'
    save(P/'engine-commands.json',commands)
    sources={str(f.relative_to(ROOT)):sha(f) for f in [*P.glob('native-src/*'),*P.glob('native/*'),*LOCAL.joinpath('native-base').rglob('*'),
             Path(__file__).resolve(),LOCAL/'lineage/checkpoint-delta.patch',LOCAL/'immutable-binaries.json'] if f.is_file()}
    save(P/'evidence/build.json',dict(passed=True,device_executed=False,warnings=0,
        binary_sha256=artifacts[str((B/'device/own-rt-iq3').relative_to(ROOT))],
        gnu_host_sha256=artifacts[str((B/'gnu-host/own-rt-iq3').relative_to(ROOT))],
        tool_sha256=artifacts[str((B/'tool/own-rt-ckpt-tool').relative_to(ROOT))],
        parent_binary_sha256=P153_BINARIES,parent_reproduction=reproduction,native_delta_sha256=sha(P/'evidence/native-delta.json'),
        relinked_parent_objects=len(inherited),recompiled=['entry-main (checkpoint delta)','p49d_submit (unchanged source; packet153 recompiled it too)'],
        sources=sources,inherited=inherited,artifacts=artifacts,commands=commands,
        max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        arithmetic='iq3-p49-split32-v1',arithmetic_qualified=False,
        first_execution='CPU only (host-only mini sessions, production-shape mock); device arithmetic and checkpoints unqualified until a device window'))
    for k,v in artifacts.items():print(k.rsplit('/build/',1)[1],v)

if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
