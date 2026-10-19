"""GNU/Intel exact bytes per port and their real-shape composition, CPU only."""
import json,resource,subprocess,tempfile,shlex
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits,compiler_turn
from hc_source import prepare

def run(cmd,log):
    with log.open('w') as f:
        subprocess.run(list(map(str,cmd)),stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=600)

def main():
    limits();prepare();records=[];sources={}
    for tag,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
        flags=['-O3','-march=native'] if tag=='GNU' else ['-O2','-fdenormal-fp-math=ieee']
        common=[cxx,'-std=c++20',*flags,'-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-ffunction-sections','-fdata-sections','-I'+str(B/'native')]
        ref=B/(tag+'-port-reference.o')
        with compiler_turn():run([*common,'-c',B/'native/production_cpu.cpp','-o',ref],B/(tag+'-port-reference.log'))
        for kind in ('fusion_cpu','ports_bytes'):
            binary=B/(tag+'-'+kind);dep=B/(tag+'-'+kind+'.d')
            cmd=[*common,'-MMD','-MF',dep,B/'native'/(kind+'.cpp'),ref,'-Wl,--gc-sections','-lcrypto','-o',binary]
            with compiler_turn():run(cmd,B/(tag+'-'+kind+'-compile.log'))
            for name in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):
                path=Path(name).resolve();sources[str(path.relative_to(ROOT))]=sha(path)
            hashes=[]
            for repeat in range(2):
                with tempfile.TemporaryDirectory(prefix='ports-',dir=B) as directory:
                    out=Path(directory);log=P/'evidence'/f'{tag}-{kind}-{repeat}.log'
                    # This guard also waits out an active one-card timing window.
                    with compiler_turn():run([binary,out],log)
                    expected,actual=out/'expected.bin',out/'actual.bin'
                    assert expected.read_bytes()==actual.read_bytes(),log
                    row=json.loads(log.read_text().splitlines()[-1]);assert row['passed'] and not row['device_executed']
                    hashes.append(sha(actual));records.append(dict(compiler=tag,kind=kind,repeat=repeat,expected_sha256=sha(expected),actual_sha256=sha(actual),bytes_compared=actual.stat().st_size,binary_sha256=sha(binary),native=row,passed=True))
                    print(tag,kind,repeat,'exact PASS',flush=True)
            assert hashes[0]==hashes[1]
    for f in [P/'ports_gate.py',*P.glob('native/*')]:
        if f.is_file():sources[str(f.relative_to(ROOT))]=sha(f)
    save(P/'evidence/ports-gates.json',dict(passed=True,device_executed=False,synthetic_only=True,records=records,sources=sources,
        independent_dimensions=['hc-wide','wide64','wide64+halfcache','other-fusion'],full_composition=True,
        comparison='Every output/status/intermediate byte against unchanged one-card arithmetic under each compiler; no NaN normalization.',
        peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024))

if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
