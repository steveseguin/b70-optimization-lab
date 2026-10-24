"""Strict census admission and accounting around the real packet3 C++ planner."""
from pathlib import Path
import collections, copy, hashlib, importlib.util, json, math
import prepare_overlay as O
P=O.P;ROOT=O.ROOT
META=P.parent/'metadata'
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('gsq_metadata_census',META/'census.py')
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)


def read(path):return json.loads(Path(path).read_text())


def pinned_inputs():
    pins=read(P/'parent-pins.json')
    for path,want in pins.items():
        if sha(ROOT/path)!=want:raise ValueError('input source changed: '+path)
    old,new=read(META/'old-census.json'),read(META/'new-census.json')
    authoritative=read(ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json')['tensors']
    baseline={t['name']:t for t in authoritative}
    if len(baseline)!=len(authoritative) or set(baseline)!=set(old['tensors']) or set(baseline)!=set(new['tensors']):
        raise ValueError('authoritative role coverage')
    for name,t in old['tensors'].items():
        for key in ('type','type_id','dimensions','shape','bytes'):
            if baseline[name][key]!=t[key]:raise ValueError('old role-source identity differs')
    return old,new,baseline


def admit(candidate, reference, roles):
    if candidate['metadata']!=reference['metadata']:raise ValueError('metadata identity differs')
    if candidate['shards']!=reference['shards'] or candidate['shard_count']!=reference['shard_count']:
        raise ValueError('shard/header identity differs')
    if set(candidate['tensors'])!=set(reference['tensors']):raise ValueError('name coverage differs')
    rows=[]
    for name,t in sorted(candidate['tensors'].items()):
        e=reference['tensors'][name]
        if type(t.get('type_id')) is not int or t['type_id'] not in C.TYPES:
            raise ValueError('unknown tensor type')
        kind,block,size=C.TYPES[t['type_id']]
        dims=t['dimensions']
        if not isinstance(dims,list) or not dims or any(type(d) is not int or d<=0 for d in dims):
            raise ValueError('invalid dimensions')
        if dims[0]%block or t['bytes']!=math.prod(dims)//block*size or t['type']!=kind:
            raise ValueError('typed extent differs')
        for field in ('type','type_id','dimensions','shape','bytes','file_offset','data_offset','shard','reserved_span_bytes','payload_extent_validated'):
            if t.get(field)!=e[field]:raise ValueError('tensor identity differs: '+name+' '+field)
        if dims!=roles[name]['dimensions']:raise ValueError('family shape differs')
        rows.append(dict(name=name,type=kind,dimensions=dims,bytes=t['bytes'],component=roles[name]['component'],layer=roles[name]['layer']))
    return rows


def export(rows,path):
    Path(path).write_text(''.join(f"{t['name']} {t['type']} {','.join(map(str,t['dimensions']))} {t['bytes']} {t['component']}\n" for t in rows))


def validate_graph(plan, rows):
    tensors={r['name']:r for r in rows};buffers={b['name']:b for b in plan['buffers']}
    if len(buffers)!=len(plan['buffers']):raise ValueError('duplicate buffer')
    usage=collections.defaultdict(set);dispatch=collections.defaultdict(list)
    for b in buffers.values():
        if b['card'] not in (-1,0,1) or not b['shape'] or any(type(x)is not int or x<1 for x in b['shape']):raise ValueError('buffer geometry')
        if b['element_bytes'] not in (2,4,8):raise ValueError('buffer scalar')
    labels=set()
    for i,l in enumerate(plan['launches']):
        if l['label'] in labels:raise ValueError('duplicate launch label')
        labels.add(l['label'])
        if l['card'] not in (0,1):raise ValueError('launch card')
        if any(type(x)is not int or x<1 for x in l['shape']):raise ValueError('launch geometry')
        for direction in ('inputs','outputs'):
            for name in l[direction]:
                b=buffers[name]
                if b['card'] not in (-1,l['card']):raise ValueError('foreign buffer binding')
            expected=sum(math.prod(buffers[n]['shape'])*buffers[n]['element_bytes'] for n in l[direction])
            if l['read_bytes' if direction=='inputs' else 'write_bytes']!=expected:raise ValueError('buffer extent accounting')
        for name in l['weights']:
            t=tensors[name];usage[name].add(l['card'])
            dispatch[(l['op'],t['type'])].append({'launch_index':i,'label':l['label'],'tensor':name,'dimensions':t['dimensions'],'card':l['card'],'component':t['component']})
        if l['op'] in ('gemv','routed_gemv'):
            batch,n,k=l['shape']
            for name in l['weights']:
                expected=[k,n] if l['op']=='gemv' else [k,n,512]
                actual=tensors[name]['dimensions']
                if actual!=expected and not(n==1 and actual==[k]):raise ValueError('actual launch weight shape')
    if set(usage)!=set(tensors):raise ValueError('unreferenced tensor')
    if len(plan['launches'])!=plan['launch_count']:raise ValueError('launch count')
    if sum(l['weight_bytes'] for l in plan['launches'])!=plan['weight_bytes']:raise ValueError('weight accounting')
    placement=[];cards=[dict(card=i,raw_resident_weight_bytes=0,logical_buffer_bytes=0) for i in (0,1)];host=0
    for name,t in tensors.items():
        mask=sum(1<<i for i in usage[name])
        if t['component'] in ('embedding','ple_lookup'):location='host-file-backed';host+=t['bytes']
        else:
            if len(usage[name])!=1:raise ValueError('unexpected weight replication')
            card=next(iter(usage[name]));location=f'card{card}';cards[card]['raw_resident_weight_bytes']+=t['bytes']
            expected=1 if t['layer'] is None else t['layer']//24
            if card!=expected:raise ValueError('weight split differs')
        placement.append(dict(t,location=location,consumer_card_mask=mask))
    for b in buffers.values():
        for card in (0,1):
            if b['card'] in (-1,card):cards[card]['logical_buffer_bytes']+=math.prod(b['shape'])*b['element_bytes']
    for c in cards:c['raw_weights_plus_logical_buffers']=c['raw_resident_weight_bytes']+c['logical_buffer_bytes']
    return dict(native_admitted=False,numeric_execution=False,tensor_placement=placement,per_card=cards,
                host_file_backed_bytes=host,dispatch_requirements=[dict(op=k[0],type=k[1],count=len(v),bindings=v,native_qualified=False) for k,v in sorted(dispatch.items())],
                buffer_masks={n:(3 if b['card']==-1 else 1<<b['card']) for n,b in buffers.items()},
                scope='Original unfused packet3 graph. Packed resident bytes and logical plan buffers only; not selected Engine lowering, actual expanded cache/residency, peak allocation or hardware fit. MTP unavailable in target shards.')


def same_topology(a,b):
    def strip(p):
        return {'buffers':p['buffers'],'launches':[{k:v for k,v in l.items() if k!='weight_bytes'} for l in p['launches']]}
    if strip(a)!=strip(b):raise ValueError('actual graph topology differs')
    return True
