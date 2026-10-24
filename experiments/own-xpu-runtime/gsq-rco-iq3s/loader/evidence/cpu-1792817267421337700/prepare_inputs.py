"""Generate native-format placement/stat inputs from authenticated retained census."""
from pathlib import Path
import hashlib,json,os,stat
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def verify_pins():
    pins=json.loads((P/'parent-pins.json').read_text())
    for path,want in pins.items():
        if sha(ROOT/path)!=want:raise ValueError('parent changed: '+path)
    return pins

def placement(census,roles):
    if set(census['tensors'])!=set(roles):raise ValueError('placement name coverage')
    result=[]
    for name,t in sorted(census['tensors'].items()):
        role=roles[name]
        if t['dimensions']!=role['dimensions']:raise ValueError('family dimensions differ')
        layer=role['layer'] if role['layer'] is not None else -1
        mask=0 if role['component'] in ('embedding','ple_lookup') else 3 if role['hc_projection_replicated'] else 1 if 0<=layer<24 else 2
        result.append(dict(shard=Path(t['shard']).name,name=name,component=role['component'],type_id=t['type_id'],offset=t['data_offset'],bytes=t['bytes'],layer=layer,mask=mask,dimensions=t['dimensions']))
    return result

def plan_text(rows):
    return ''.join(' '.join(map(str,[r['shard'],r['name'],r['component'],r['type_id'],r['offset'],r['bytes'],r['layer'],r['mask'],len(r['dimensions']),*r['dimensions']]))+'\n' for r in rows)

def prepare():
    pins=verify_pins();census=json.loads((P.parent/'metadata/new-census.json').read_text())
    roles=json.loads((ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json').read_text())['tensors'];roles={r['name']:r for r in roles}
    rows=placement(census,roles);identities=[]
    for shard in census['shards']:
        path=Path(shard['path']);s=path.lstat()
        actual=[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
        if not stat.S_ISREG(s.st_mode) or actual!=shard['stat_identity']:raise ValueError('real shard stat changed')
        identities.append(dict(basename=path.name,bytes=s.st_size,dev=s.st_dev,ino=s.st_ino,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,header_sha256=shard['header_sha256']))
    if len(identities)!=2 or len({s['basename'] for s in identities})!=2:raise ValueError('exact two shards')
    (P/'placement.tsv').write_text(plan_text(rows))
    (P/'shard-auth.tsv').write_text(''.join(' '.join(str(s[k]) for k in ('basename','bytes','dev','ino','mtime_ns','ctime_ns'))+'\n' for s in identities))
    counts={str(mask):sum(r['mask']==mask for r in rows) for mask in range(4)}
    totals=[sum(r['bytes'] for r in rows if r['mask']&(1<<card)) for card in range(2)]+[sum(r['bytes'] for r in rows if r['mask']==0)]
    record={'schema':'ownrt.gsq.loader-inputs.v1','native_admitted':False,'tensor_count':len(rows),'placement_sha256':sha(P/'placement.tsv'),'stat_auth_sha256':sha(P/'shard-auth.tsv'),'shards':identities,'mask_counts':counts,'bytes_card0_card1_host':totals,'replica_BF16_count':sum(r['mask']==3 and r['type_id']==30 for r in rows),'source_sha256':pins,'model_reads':'lstat only; existing census reused, zero model header/payload reads','trust':'Admission inputs must be independently hash-admitted by coordinator. Stat identity does not defend against hostile same-user mutation; source/header/download provenance remains external.'}
    (P/'inputs.json').write_text(json.dumps(record,indent=2)+'\n');return record
