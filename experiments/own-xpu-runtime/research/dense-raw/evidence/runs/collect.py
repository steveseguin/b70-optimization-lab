import json,statistics,hashlib,os,re,shutil
from pathlib import Path
L=Path('/dev/shm/ownrt-lab-raw');R=L/'runs';OUT=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/dense-raw')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
bins={'ref (live service b13b, canonical 5e44953236cc)':'/dev/shm/engine-build-svc-b13b-merged-20261026/sc117-engine',
 'c1 (raw v1 layout)':'/dev/shm/engine-build-lab-raw-c1/sc117-engine','c2 (c1 + lab profile deferral)':'/dev/shm/engine-build-lab-raw-c2/sc117-engine',
 'c3 (v2 pair layout + deferral)':'/dev/shm/engine-build-lab-raw-c3/sc117-engine','c4 (v2, restructured kernels, RUG configs, deferral, plan-only)':'/dev/shm/engine-build-lab-raw-c4/sc117-engine',
 'c5 FINAL (canonical + dense-raw.patch)':'/dev/shm/engine-build-lab-raw-c5/sc117-engine'}
builds={k:dict(binary=v,sha256=sha(v)) for k,v in bins.items()}
def env_of(name):
    p=R/f'launch-{name}.json'
    return p
runs=[]
for d in sorted(R.iterdir()):
    if not d.is_dir():continue
    n=d.name;s=d/'summary.json';log=d/'rank1.log'
    row=dict(run=n)
    lf=(R/f'launch-{n}.json')
    launch=None
    for cand in [R/f'launch-{n}.json']:
        if cand.exists():launch=json.loads(cand.read_text())
    if launch is None:
        # run.sh used the base launch file when no overrides were given
        pass
    if log.exists():
        m=re.search(r'owned_bytes (\d+) weights (\d+)',log.read_text());
        if m:row['plan_owned_bytes']=int(m.group(1));row['plan_weight_bytes']=int(m.group(2))
    if s.exists():
        j=json.loads(s.read_text());h=sorted(j['half_ms'])
        row.update(prompt_rows=j['prompt'],chunk_rows=j['rows'],prompt_ms=round(j['prompt_ms'],1),half_ms_median=round(h[len(h)//2],3),load_s=round(j['load_s'],2),rc=j['rc'],
                   tokens_sha256=hashlib.sha256(json.dumps(j['tokens']).encode()).hexdigest()[:16])
    c=d/'rank1'/'census.json'
    if c.exists():row['runtime_device_bytes']=json.loads(c.read_text())['totals']['device']
    dr=d/'rank1'/'dense-raw.json'
    if dr.exists():j=json.loads(dr.read_text());row['dense_raw']={k:v for k,v in j.items() if k!='tensors'};row['dense_raw']['tensors']=len(j['tensors'])
    dri=R/f'{n}.dri'
    if dri.exists():row['dri']=dri.read_text().split()
    if (d/'rank1'/'plan-only.json').exists():row['plan_only']=True
    runs.append(row)
json.dump(dict(builds=builds,runs=runs),open(L/'collected.json','w'),indent=1)
print(len(runs),'runs')
