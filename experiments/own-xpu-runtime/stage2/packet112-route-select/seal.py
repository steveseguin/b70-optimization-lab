"""Pin immutable micro source, input and CPU receipts; no import-time caps."""
import json
from build_engine import P, ROOT, sha, save
def main():
    sources={};files={}
    for mode in ('gnu','intel','device'):
        path=P/'evidence'/('build-'+mode+'.json');r=json.loads(path.read_text())
        assert r['passed'] and not r['device_executed']
        for n,h in r['sources'].items():assert sha(ROOT/n)==h;sources[n]=h
        for n,h in r['artifacts'].items():assert sha(P/n)==h;files[n]=h
        files[str(path.relative_to(P))]=sha(path)
    for path in P.iterdir():
        if path.suffix in ('.py','.hpp','.cpp','.inc'):files[path.name]=sha(path)
    for name in ('evidence/cpu.json','evidence/input-capture.json','evidence/capture/harness-logits.bin','evidence/capture/harness-logits.jsonl'):
        files[name]=sha(P/name)
    cpu=json.loads((P/'evidence/cpu.json').read_text());assert cpu['passed']
    for r in cpu['records']:assert sha(P/r['log'])==r['log_sha256'];files[r['log']]=r['log_sha256']
    save(P/'seal.json',dict(schema='ownrt.packet112.micro-seal.v1',sources=sources,files=files,device_executed=False))
    print('micro seal PASS')
if __name__=='__main__':main()
