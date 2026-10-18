"""Packet58xd: rebuild only the device entry, retaining all kernel/host objects."""
import json, resource, shlex, subprocess, time
from pathlib import Path
from unittest.mock import patch
from build_engine import P, ROOT, B, sha, save, limits
from frozen_inputs import restore, relocate, FROZEN
from native_source import generate

def retire_restored_receipts():
    # The original receipts remain byte-preserved in the owned archive. They
    # describe historical sibling pins, not this packet's live source closure.
    manifest=json.loads((P/'lineage/58xb-source-snapshot.json').read_text())
    assert sha(P/'lineage/58xb-source-snapshot.tar.gz')==manifest['archive_sha256']
    live_sources=json.loads((P/'evidence/build.json').read_text())['sources']
    for path in FROZEN.rglob('*.json'):
        assert str(path.relative_to(ROOT)) not in live_sources
        assert sha(path)==manifest['members'][str(path.relative_to(FROZEN))]
        path.unlink()  # Generated archive extraction only; restore() recreates it.

def main():
    limits(); restore()
    previous=json.loads((P/'evidence/build.json').read_text())
    history=P/'lineage/58xc-build.json'
    if not history.exists(): history.write_text(json.dumps(previous,indent=2)+'\n')
    # Restore then relocate only this packet's generated native source paths.
    # Owner/backend objects are retained, so their source regeneration is outside
    # this entry-only repair. Generate the actual model entry and its headers.
    with patch('async_source.support'):
        generate()
    for path in (B/'native').glob('*'):
        if path.is_file(): path.write_bytes(relocate(path.read_bytes()))
    commands=[]
    for name in ('device-entry-main','device-own-rt-iq3'):
        old=next(r for r in previous['commands'] if r['name']==name)
        cmd=[relocate(arg.encode()).decode() for arg in old['command']]
        start=time.monotonic()
        # This urgent, bounded entry-only repair runs under the brief's CPU/AS
        # caps. Do not touch another builder's lock or stale lane markers.
        import importlib.util
        spec=importlib.util.spec_from_file_location('compile_observer',P.parents[1]/'ops/compile_turn.py')
        observer=importlib.util.module_from_spec(spec);spec.loader.exec_module(observer)
        rows=observer.process_table()
        assert not [(pid,r['comm']) for pid,r in rows.items() if r['comm'] in observer.COMPILERS], 'active compiler'
        for marker in observer.COORD.glob('active-lane-*.json'):
            owner=json.loads(marker.read_text())
            assert owner.get('scope')!='whole-host' or not observer.device_descendants(owner,rows), 'active whole-host device work'
        with (B/('58xd-'+name+'.log')).open('w') as log:
            subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
        commands.append(dict(name=name,command=cmd,seconds=time.monotonic()-start))
        print(name,'PASS',flush=True)
    sources=dict(previous['sources'])
    for name in shlex.split((B/'device/entry-main.d').read_text().replace('\\\n',' '))[1:]:
        path=Path(name).resolve()
        if path.is_relative_to(ROOT): sources[str(path.relative_to(ROOT))]=sha(path)
    for path in (P/'capacity_source.py',P/'native_source.py',Path(__file__),P/'native/drm_size.hpp'):
        sources[str(path.relative_to(ROOT))]=sha(path)
    previous['sources']=sources
    previous['artifacts']['build/device/own-rt-iq3']=sha(B/'device/own-rt-iq3')
    previous['amendment']=dict(packet='58xd',commands=commands,host_binaries_unchanged=True,
        original_build_sha256=sha(history), scope='device entry DRM size parser only; no model/kernel execution')
    previous['max_rss_kib']=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    assert previous['max_rss_kib']*1024<2*1024**3
    save(P/'evidence/build.json',previous)
    retire_restored_receipts()
    limits()

if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3));main()
