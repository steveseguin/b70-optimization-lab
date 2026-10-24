"""Generate immutable exact-model authority; no model access or compilation."""
from pathlib import Path
import hashlib,json
P=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
PINS={'placement.tsv':'a9ab0302d85f208717748c70be9d09d0a494e07f494a0e67b39dac6cc9468253','shard-auth.tsv':'dfec2707adc2459d625f1dfe0add5607e8b2d7e36453f7aed32de5b292348fde','inputs.json':'2fbe659efac3d8a895d57984305452e145f894662e9aedb95bef68f04e0c3f1a','../metadata/new-census.json':'b47eae82a10854f47f23acc96e44d920a8b04ea1511f100aa1395418c41ca8a1'}

def generate():
    for name,digest in PINS.items():
        if sha(P/name)!=digest:raise ValueError('bound source changed '+name)
    census=json.loads((P/'../metadata/new-census.json').read_text());inputs=json.loads((P/'inputs.json').read_text())
    lines=[]
    for line in (P/'placement.tsv').read_text().splitlines():
        fields=line.split();shard,name,component=fields[:3];kind,offset,size,layer,mask,rank=map(int,fields[3:9]);dims=list(map(int,fields[9:]))
        assert len(dims)==rank
        lines.append('{'+','.join(map(json.dumps,[shard,name,component]))+',iq3::Type('+str(kind)+'),{'+','.join(str(n)+'ULL' for n in dims)+'},'+','.join([str(offset)+'ULL',str(size)+'ULL',str(layer),str(mask)])+'}')
    roots={str(Path(s['path']).parent) for s in census['shards']};assert len(roots)==1
    identities=[];headers=[]
    for s,t in zip(inputs['shards'],census['shards']):
        assert s['basename']==Path(t['path']).name
        identities.append('{'+json.dumps(s['basename'])+','+','.join(str(s[k])+'ULL' for k in ('bytes','dev','ino','mtime_ns','ctime_ns'))+'}')
        headers.append('{'+str(t['header_bytes_read'])+'ULL,'+json.dumps(t['header_sha256'])+'}')
    text=(P/'bound_template.hpp.txt').read_text()
    replacements={'@PLACEMENT@':json.dumps(str(P/'placement.tsv')),'@AUTH@':json.dumps(str(P/'shard-auth.tsv')),'@ROOT@':json.dumps(roots.pop()),'@PLAN_SHA@':json.dumps(PINS['placement.tsv']),'@AUTH_SHA@':json.dumps(PINS['shard-auth.tsv']),'@SHARDS@':',\n'.join(identities),'@HEADERS@':',\n'.join(headers),'@PLAN@':',\n'.join(lines)}
    for marker,value in replacements.items():
        if text.count(marker)!=1:raise ValueError('nonunique bound template marker')
        text=text.replace(marker,value)
    (P/'bound.hpp').write_text(text)
    record={'schema':'ownrt.gsq.compiled-loader-authority.v1','native_admitted':False,'source_sha256':{name:sha(P/name) for name in [*PINS,'generate_bound.py','bound_template.hpp.txt']},'bound_header_sha256':sha(P/'bound.hpp'),'expected_descriptors':len(lines),'exact_header_prefix_bytes':sum(s['header_bytes_read'] for s in census['shards']),'model_reads_performed':0,'scope':'Immutable descriptors/stat identities plus exact raw header SHA authority; actual preflight hash callback must be the admitted SHA256 implementation.'}
    (P/'bound-authority.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record))

if __name__=='__main__':generate()
