"""Two fresh processes under each host compiler; resource caps only in CLI."""
import json, subprocess, resource
from build_engine import P, B, ROOT, limits, sha, save
def main():
    limits();records=[]
    for mode in ('gnu','intel'):
        build=P/'evidence'/('build-'+mode+'.json')
        for n,h in json.loads(build.read_text())['sources'].items():assert sha(ROOT/n)==h,n
        for repeat in (1,2):
            output=P/'evidence'/f'cpu-{mode}-final-{repeat}.jsonl'
            with output.open('x') as log:
                subprocess.run([str(B/('micro-'+mode)),'--cpu-test',str(P/'evidence/capture/harness-logits.bin')],stdin=subprocess.DEVNULL,stdout=log,check=True,timeout=120)
            rows=[json.loads(s) for s in output.read_text().splitlines()]
            assert rows[-1]['passed'] and rows[-1]['cases']==2048
            cases=[r for r in rows if r['kind']=='correctness']
            assert [r['case'] for r in cases]==list(range(2048)) and all(r['exact'] for r in cases)
            records.append(dict(compiler=mode,repeat=repeat,pid=rows[0]['pid'],output_sha256=rows[-1]['output_sha256'],log=str(output.relative_to(P)),log_sha256=sha(output),build_sha256=sha(build)))
    assert len({r['pid'] for r in records})==4
    assert len({r['output_sha256'] for r in records})==1
    save(P/'evidence/cpu.json',dict(passed=True,device_executed=False,cases_per_process=2048,records=records,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
    print('GNU and Intel: 2048 exact cases each, twice; all output hashes equal')
if __name__=='__main__':main()
