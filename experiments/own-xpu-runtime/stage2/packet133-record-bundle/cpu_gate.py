"""Rerun copied GNU/Intel CPU binaries; compare actual outputs to frozen packet118."""
import gzip, hashlib, json, shutil, subprocess, resource
from pathlib import Path
from build_engine import P, ROOT, B, sha, save, limits
from bundle_selection import views, choices
from reuse_build import SNAP, native_sources

def run(cmd):
    return subprocess.run(list(map(str,cmd)),stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=300)

def main():
    limits();sources=native_sources();runs=[]
    old=json.loads((SNAP/'evidence/cpu-byte-identity.json').read_text())
    label,v=next(iter(views().items()));expected=old['views']['--'.join(v[:-1])]
    for compiler in ('GNU','Intel'):
        for repeat in (1,2):
            prior=next(r for r in expected['runs'] if r['compiler']==compiler and r['repeat']==repeat)
            binaries=[B/'cpu'/('head-'+compiler),B/'cpu'/compiler,B/'cpu'/('prefix-'+compiler),B/('reset-'+compiler)]
            for binary in binaries:
                assert sha(binary)==sha(P.with_name('packet118-record-bundle')/binary.relative_to(P))
                sources[str(binary.relative_to(ROOT))]=sha(binary)
            scratch=B/'cpu/replay124';scratch.mkdir()
            try:
                run([binaries[0],scratch]);head=(scratch/'candidate.bin').read_bytes()
                assert head==(scratch/'expected.bin').read_bytes()
                assert hashlib.sha256(head).hexdigest()==prior['head']['candidate_sha256']
                assert head==gzip.decompress((SNAP/'evidence'/Path(prior['head']['fixture']).name).read_bytes())
                run([binaries[1],scratch]);fusion=(scratch/'actual.bin').read_bytes()
                assert fusion==(scratch/'expected.bin').read_bytes()
                assert hashlib.sha256(fusion).hexdigest()==prior['fusion']['actual_sha256']
                prefix=json.loads(run([binaries[2],v[14]]).stdout)
                prefix_old=json.loads((SNAP/'evidence'/f'prefix-{compiler}-{v[14]}-{repeat-1}.json').read_text())
                assert prefix==prefix_old and prefix['passed']
                reset=json.loads(run([binaries[3]]).stdout)
                reset_old=json.loads((SNAP/'evidence/reset-regression.json').read_text())
                assert reset==next(r['result'] for r in reset_old['runs'] if r['compiler']==compiler and r['repeat']==repeat)
                raw=json.dumps(prefix,sort_keys=True).encode()+head+fusion
                assert hashlib.sha256(raw).hexdigest()==prior['candidate_sha256']
                out=P/'evidence'/f'joint-{v[14]}-{compiler}-{repeat}.bin.gz'
                out.write_bytes(gzip.compress(raw,mtime=0));digest=hashlib.sha256(raw).hexdigest()
                runs.append(dict(compiler=compiler,repeat=repeat,fixture=str(out.relative_to(ROOT)),
                    fixture_sha256=sha(out),expected_sha256=digest,candidate_sha256=digest,
                    packet118_output_sha256=prior['candidate_sha256'],prefix=prefix,reset=reset))
            finally:shutil.rmtree(scratch)
        print(compiler,'two fresh runs byte-identical to packet118 bundle7 PASS',flush=True)
    for f in [P/'cpu_gate.py',*(SNAP/'evidence').glob('*.json'),*(SNAP/'evidence').glob('*.bin.gz')]:
        sources[str(f.relative_to(ROOT))]=sha(f)
    save(P/'evidence/cpu-byte-identity.json',dict(passed=True,device_executed=False,
        views={label:dict(choices=choices(*v),runs=runs) for label,v in views().items()},sources=sources,
        max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        scope='Two identical-native schedule selections; suffix-specific CPU proof bound from packet130. Actual GNU/Intel head, fusion, prefix and reset CPU outputs match copied packet118 evidence; full model device quality remains separately gated.'))
if __name__=='__main__':main()
