"""Build the one-card engine from the sealed portable source archive.

Vendors repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70 manifests into
one-card/lineage/portable/ (private copies; cross-packet pins are refused),
verifies the archive and every member hash, extracts with original_root
rewritten to the packet-private one-card/native-portable tree, then runs the
manifest's 42 one-card translation units plus link_command under the shared
compiler turn. No inherited object files; arithmetic/flags unchanged. The
resulting binary is never device-executed here.
"""
import hashlib,json,os,re,resource,shutil,subprocess,sys,tarfile,time
from pathlib import Path
from build_engine import P,ROOT,limits,turn,sha,save
REPRO=ROOT/'repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70'
CODEX_SHM=Path('/dev/shm/ownrt-portable-build-one-20261020/own-rt-iq3')
VENDORED=('native-build.json','build-validation.json','native-sources.tar.gz')

def digest(data):return hashlib.sha256(data).hexdigest()

def unpack(manifest,archive,source):
    if digest(archive.read_bytes())!=manifest['archive']['sha256']:
        raise ValueError('source archive hash mismatch')
    expected=manifest['source_files'];seen=set()
    with tarfile.open(archive,'r:gz') as tf:
        for member in tf:
            name=member.name;rel=Path(name)
            if not member.isfile() or rel.is_absolute() or '..' in rel.parts or name in seen or name not in expected:
                raise ValueError(f'unexpected or unsafe archive member: {name}')
            data=tf.extractfile(member).read()
            if digest(data)!=expected[name]['sha256'] or len(data)!=expected[name]['bytes']:
                raise ValueError(f'source hash mismatch: {name}')
            target=source/rel;target.parent.mkdir(parents=True,exist_ok=True)
            # Only originating checkout paths change. Arithmetic, flags and parser guards do not.
            if target.suffix in ('.cpp','.hpp','.h','.inc','.c','.tsv'):
                data=data.replace(manifest['original_root'].encode(),str(source).encode())
            target.write_bytes(data);seen.add(name)
    if seen!=set(expected):raise ValueError('archive does not contain every pinned source')
    return {name:digest((source/name).read_bytes()) for name in sorted(seen)}

def command(template,source,build):
    result=[part.replace('@SOURCE@',str(source)).replace('@BUILD@',str(build)) for part in template]
    if any('@SOURCE@' in part or '@BUILD@' in part for part in result):
        raise ValueError('unexpanded build command')
    return result

def main():
    limits();p=P/'one-card'
    lineage=p/'lineage/portable';lineage.mkdir(parents=True,exist_ok=True)
    for name in VENDORED:shutil.copy2(REPRO/'manifests'/name,lineage/name)
    manifest=json.loads((lineage/'native-build.json').read_text())
    validation=json.loads((lineage/'build-validation.json').read_text())
    save(p/'evidence/portable-inputs.json',dict(passed=True,device_executed=False,
        origin=str((REPRO/'manifests').relative_to(ROOT)),
        files={name:sha(lineage/name) for name in VENDORED},
        archive_sha256=manifest['archive']['sha256'],
        source_file_count=len(manifest['source_files']),
        build_validation_passed=validation.get('passed'),
        arithmetic_qualified=validation.get('arithmetic_qualified',False)))
    plan=manifest['plans']['one-card']
    source=p/'native-portable';build=p/'build/portable'
    progress=build/'progress.json'
    if source.exists():
        assert progress.is_file(),'existing tree without progress receipt; refusing to guess'
        receipt=json.loads(progress.read_text());relocated=receipt['relocated_source_sha256']
    else:
        source.mkdir();(build/'objects').mkdir(parents=True);(build/'logs').mkdir();(build/'tmp').mkdir()
        relocated=unpack(manifest,lineage/'native-sources.tar.gz',source)
    commands=[(row['id'],command(row['command'],source,build)) for row in plan['translation_units']]
    commands.append(('link',command(plan['link_command'],source,build)))
    save(build/'build-plan.json',{'commands':commands,'device_execution':'never'})
    env=dict(os.environ,TMPDIR=str(build/'tmp'),OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
    if not progress.is_file():
        receipt=dict(passed=False,device_executed=False,reused_object_files=False,arithmetic_qualified=False,
            schema='neural.download.ownrt.source-build-result.v1',cards=1,
            manifest_sha256=sha(lineage/'native-build.json'),archive_sha256=manifest['archive']['sha256'],
            build_validation_sha256=sha(lineage/'build-validation.json'),
            historical_binary_sha256=plan['historical_binary_sha256'],
            relocated_source_sha256=relocated,commands=[],compiler_versions={})
    for exe in sorted({cmd[0] for _,cmd in commands}):
        if exe not in ('/opt/intel/oneapi/compiler/2026.0/bin/icpx','/usr/bin/g++','g++'):
            raise SystemExit(f'unexpected compiler: {exe}')
        receipt['compiler_versions'][exe]=subprocess.check_output([exe,'--version'],env=env,text=True)
    done={r['name'] for r in receipt['commands']}
    try:
        for name,cmd in commands:
            if name in done:
                assert (build/'objects'/(name+'.o')).is_file() or name=='link'
                print(f'one-card: {name} already compiled; retained',flush=True);continue
            if shutil.disk_usage(build).free<1024**3:
                raise RuntimeError('output filesystem below 1 GiB free')
            if name!='link':cmd=[*cmd,'-MMD','-MF',str(build/'objects'/(name+'.d'))]
            with turn(),(build/'logs'/(name+'.log')).open('w') as log:
                limits();started=time.monotonic()
                result=subprocess.run(cmd,cwd=source,env=env,stdin=subprocess.DEVNULL,stdout=log,
                                      stderr=subprocess.STDOUT,timeout=900)
            row={'name':name,'argv':cmd,'returncode':result.returncode,'seconds':time.monotonic()-started}
            receipt['commands'].append(row)
            save(progress,receipt)
            if result.returncode:
                raise RuntimeError(f'{name}: compiler failed; inspect logs/{name}.log')
            if name!='link':
                # The compiler, not just an include-text scan, checks the closed source tree.
                deps=(build/'objects'/(name+'.d')).read_text().replace('\\\n',' ')
                paths=set(re.findall(r'/[^\s\\]+',deps))
                outside=[q for q in paths if q.startswith(manifest['original_root']+'/') and not q.startswith(str(P)+'/')]
                if outside:raise RuntimeError(f'{name}: compiler escaped to originating checkout: {outside}')
                project=[q for q in paths if str(source)+'/' in q]
                external=[q for q in paths if Path(q).suffix in ('.cpp','.hpp','.h','.inc') and not q.startswith((str(source)+'/','/usr/','/opt/intel/'))]
                if external:raise RuntimeError(f'{name}: unbundled non-system dependency: {external}')
                if not project:raise RuntimeError(f'{name}: no source dependencies reported')
                missing=[q for q in project if str(Path(q).resolve().relative_to(source)) not in relocated]
                if missing:raise RuntimeError(f'{name}: dependency absent from source manifest: {missing}')
                row['dependency_sha256']={q:digest(Path(q).read_bytes()) for q in sorted(project)}
                save(progress,receipt)
            print(f'one-card: {name} compiled ({row["seconds"]:.1f}s)',flush=True)
        binary=build/'own-rt-iq3'
        device=p/'build/device';device.mkdir(parents=True,exist_ok=True)
        if not (device/'own-rt-iq3').exists():shutil.move(str(binary),device/'own-rt-iq3')
        assert not binary.exists()
        binary=device/'own-rt-iq3'
        new_sha=sha(binary)
        codex_sha=sha(CODEX_SHM) if CODEX_SHM.is_file() else None
        receipt.update(passed=True,status='compiled-not-device-qualified',binary_sha256=new_sha,
            binary_bytes=binary.stat().st_size,
            historical_binary_hash_matches=new_sha==plan['historical_binary_sha256'],
            codex_shm_binary_sha256=codex_sha,codex_shm_binary_path=str(CODEX_SHM),
            codex_shm_hash_matches=(codex_sha==new_sha) if codex_sha else None,
            first_execution='host-side --help in capture_flags/rehearsal only; arithmetic and performance unqualified until the device run')
    except Exception as exc:
        receipt['status']='build-failed';receipt['error']=str(exc)
        save(p/'evidence/build.json',receipt)
        raise
    finally:
        receipt['peak_child_rss_bytes']=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024
        save(progress,receipt)
    assert receipt['peak_child_rss_bytes']<4*1024**3
    save(p/'evidence/build.json',receipt)
    old=P.parent/'packet165-warm-prefill'/'one-card'
    identity=json.loads((p/'identity.json').read_text())
    identity.update(binary_sha256=receipt['binary_sha256'],parent_binary_sha256=receipt['historical_binary_sha256'],
        native_binary_unchanged_from_packet163=False,native_arithmetic_unchanged_from_packet163=True,
        native_delta='portable rebuild from hash-pinned archive native-sources.tar.gz '+manifest['archive']['sha256'][:16]+' with @SOURCE@ relocated to packet178 one-card/native-portable; no arithmetic, flag or parser edits')
    save(p/'identity.json',identity)
    rope=next((source).rglob('rope.bf16'))
    assert digest(rope.read_bytes())=='92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390'
    embedded={str(rope.relative_to(ROOT)):'92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390'}
    save(p/'inherited-native.json',dict(parent=str(old.relative_to(ROOT)),
        binary_sha256=receipt['binary_sha256'],parent_binary_sha256=receipt['historical_binary_sha256'],
        embedded_readonly_dependencies=embedded,native_recompiled=True))
    save(p/'runtime-constants.json',[dict(
        source='native-sources.tar.gz member '+next(n for n in relocated if n.endswith('/rope.bf16')),
        local=str(rope.relative_to(p)),sha256=embedded[str(rope.relative_to(ROOT))],bytes=rope.stat().st_size)])
    save(p/'lineage/packet178-build.json',dict(manifest_sha256=receipt['manifest_sha256'],
        archive_sha256=receipt['archive_sha256'],build_validation_sha256=receipt['build_validation_sha256'],
        commands=receipt['commands'],relocated_source_count=len(relocated),
        codex_shm_binary_sha256=codex_sha,codex_shm_hash_matches=receipt['codex_shm_hash_matches']))
    save(p/'evidence/identity-check.json',dict(passed=True,device_executed=False,
        archive_member_hashes_verified=len(relocated),reused_object_files=False,
        selection_unchanged=sha(p/'selection.json')==sha(old/'selection.json'),
        dispatch_unchanged=sha(p/'dispatch.json')==sha(old/'dispatch.json'),
        arithmetic='iq3-p49-split32-v1',
        historical_binary_sha256=receipt['historical_binary_sha256'],
        historical_binary_hash_matches=receipt['historical_binary_hash_matches'],
        codex_shm_hash_matches=receipt['codex_shm_hash_matches'],
        build_receipt_sha256=sha(p/'evidence/build.json')))
    print('Built',binary,'sha256',receipt['binary_sha256'],'; device execution and arithmetic qualification remain pending.')

if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
