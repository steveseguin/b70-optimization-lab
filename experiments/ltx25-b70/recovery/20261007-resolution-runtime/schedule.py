"""Pure CPU construction of the nine reviewed resolution setup graphs; never submit."""
import copy
import hashlib
import json
from pathlib import Path
import stat

PARENT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99b')
PARENT_SHA = 'f819270165a7e8c59206b0dd641ebb1b7763e586b458a1e32a75344f96220d0a'
PLAN_SHA = '84bdccba3e2fe39b9bf5bcd1cd074c6ee74bbd8ade2a9be7aa63e945f5b07e1d'
QUALIFICATION_ID = 'e017bccd97b4713eab3ca9216e25c540201f117b330bd2cbab35254d19d7e4ac'
PLAN = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261007-resolution-full-103/candidate-plan.json')
PREFIX = 'resolution-full-20261007'
CAPTURE_INDICES = {'capture0': 99903030, 'capture1': 99903041}
GRAPHS = {
 'window-probe': ('text-window-probe.json','ce6085a42aab926e8159c9bc966cc1b67a8da03dd6ecaef6b5efa52669ccd7a0'),
 'pin0': ('sampler-pin.json','fdd237a084723741d41689e7450482f77bc03624abfabcf3300c18f3761f3005'),
 'capture0': ('graph-capture-all48-pipe-samp2-tsh-win.json','181b2fe7e9daed17f516a38f0dd93d5b4e7d9f26b7c8673a419b0dd1fc0385bd'),
 'pin1': ('sampler-pin.json','fdd237a084723741d41689e7450482f77bc03624abfabcf3300c18f3761f3005'),
 'capture1': ('graph-capture-all48-pipe-samp2-tsh-win.json','181b2fe7e9daed17f516a38f0dd93d5b4e7d9f26b7c8673a419b0dd1fc0385bd'),
 'coverage': ('sampler-capture-coverage.json','268ca20b91158e6d8487a4b7ceb6d43ed67c0264550b60eff631dc0d94af0579'),
 'decode-probe': ('decode-replica-probe.json','c14a72eb97855140b728e62f189fddcb1c8cf2d281e42e276d825c6bc6d484ef'),
 'freeze': ('sampler-capture-freeze.json','a7740efa3829edc15bf99d6c4e03d974a2c909f3041d358c517345c007c7a161'),
}


def require(ok, message):
    if not ok: raise ValueError(message)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def sha(raw):return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,'Duplicate JSON key');result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:require(False,'Nonfinite JSON'))


def read(path):
    path=Path(path)
    require(path.is_absolute() and '..' not in path.parts and not any(p.is_symlink() for p in (path,*path.parents)),'Unsafe source path')
    before=path.stat();require(stat.S_ISREG(before.st_mode) and before.st_size<=8*1024**2,'Invalid source file')
    raw=path.read_bytes();after=path.stat()
    attrs=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    require(attrs(before)==attrs(after) and len(raw)==before.st_size,'Source changed')
    return raw


def graph_edges(graph):
    visiting=set();done=set()
    def visit(key):
        require(key not in visiting,'Graph cycle')
        if key in done:return
        visiting.add(key)
        node=graph[key];require(set(node)=={'class_type','inputs'},'Unknown graph fields')
        for value in node['inputs'].values():
            if isinstance(value,list):
                require(len(value)==2 and value[0] in graph and type(value[1]) is int and value[1]>=0,'Bad graph edge')
                visit(value[0])
        visiting.remove(key);done.add(key)
    for key in graph:
        require(isinstance(key,str) and key.isdecimal(),'Invalid node ID');visit(key)


def build_schedule(packet=PARENT, plan_path=PLAN):
    packet=Path(packet);raw=read(packet/'manifest.json')
    require(sha(raw)==PARENT_SHA,'Qualified parent changed');manifest=strict_json(raw)
    plan_raw=read(plan_path);envelope=strict_json(plan_raw)
    require(set(envelope)=={'plan','plan_sha256'} and envelope['plan_sha256']==PLAN_SHA==sha(canonical(envelope['plan'])),'Unreviewed plan')
    plan=envelope['plan'];require(plan['qualification_id']==QUALIFICATION_ID,'Qualification identity differs')
    graphs={};sources={}
    for kind,(filename,expected) in GRAPHS.items():
        path='graphs/'+filename;raw=read(packet/path)
        require(sha(raw)==expected==manifest['files'][path],'Pinned setup graph changed: '+kind)
        graphs[kind]=strict_json(raw);sources[path]=expected
    rows=[];previous=None
    for kind in ('window-probe','prepare-native','pin0','capture0','pin1','capture1','coverage','decode-probe','freeze'):
        name=PREFIX+'-'+kind
        graph=({'490':{'class_type':'LTXResolutionPrepareNative','inputs':{'run_name':name}}}
               if kind=='prepare-native' else copy.deepcopy(graphs[kind]))
        for node in graph.values():
            if 'run_name' in node['inputs']:node['inputs']['run_name']=name
        if kind in ('pin0','pin1'):
            for node in graph.values():
                if node['class_type']=='LTXSamplerPin':node['inputs']['worker']=int(kind[-1])
        if kind in CAPTURE_INDICES:
            # Fixture metadata derives from the already pinned native boat graph.
            native=plan['requests'][0]['graph']
            require(plan['requests'][0]['fixture']=='boat','Native fixture ordering differs')
            for node in ('338','339'):graph[node]['inputs']['noise_seed']=native[node]['inputs']['noise_seed']
            graph['364']['inputs']['text']=native['364']['inputs']['text']
            graph['356']['inputs'].update(width=320,height=192,length=25,batch_size=1)
            for node in ('364','428'):
                graph[node]['inputs']['clip_index']=CAPTURE_INDICES[kind]
            graph['428']['inputs']['depth']=1
            for node in ('364','428','426'):
                graph[node]['inputs'].update(output_size='640x384',speed_only=False,
                    comparison_mode='same-size-native-v1',qualification_id=QUALIFICATION_ID)
            require(graph['428']['inputs']['mode']=='pipeline' and
                    graph['426']['inputs']['mode']=='pipeline-save' and graph['426']['inputs']['depth']==1,
                    'Capture needs unchanged nonlean sampler/native decoder fill route')
        graph_edges(graph)
        depends=[] if previous is None else [previous]
        if kind=='pin0':depends=['barrier:optimized_preparation']
        row={'name':name,'phase':'native-setup' if kind in ('window-probe','prepare-native') else 'optimized-setup',
             'kind':kind,'graph':graph,'graph_sha256':sha(canonical(graph)),'depends_on':depends}
        if kind in CAPTURE_INDICES:
            row.update(clip_index=CAPTURE_INDICES[kind],expected_emitted_index=None,
                       worker=int(kind[-1]),
                       admission_action='admit-'+kind, retirement_action='retire-'+kind+'-tails',
                       postcondition='sample%d finished finite on pinned worker; no failed jobs; pipeline idle; preserve then retire completed un-emitted tail' % CAPTURE_INDICES[kind],
                       output_role='unscored fill placeholder; no native-reference or candidate parity')
        rows.append(row);previous=name
    indices={r['clip_index'] for r in plan['requests']}
    require(len(set(CAPTURE_INDICES.values()))==2 and all(i not in indices and
        max(r['clip_index'] for r in plan['requests'][:20])<i<min(r['clip_index'] for r in plan['requests'][20:])
        for i in CAPTURE_INDICES.values()),'Capture index collision')
    captures=sum(any(n['class_type'] in ('LTXBaselineCapture','LTXPipelineSave') for n in r['graph'].values()) for r in [*plan['requests'],*rows])
    require(captures==80 and captures<=80,'Capture budget differs')
    result={'schema':'ltx.resolution-setup-schedule.v1','status':'CPU-plan-only-not-runtime-qualified',
            'parent_manifest_sha256':PARENT_SHA,'plan_sha256':PLAN_SHA,'qualification_id':QUALIFICATION_ID,
            'source_graph_sha256':sources,'rows':rows,
            'boundary_dependencies':{
                plan['requests'][0]['name']:[PREFIX+'-prepare-native'],
                'barrier:reference_verified':[r['name'] for r in plan['requests'][:20]],
                'barrier:optimized_preparation':['barrier:reference_verified'],
                plan['requests'][20]['name']:[PREFIX+'-freeze'],
                'barrier:candidate_verified':[r['name'] for r in plan['requests'][20:34]],
                'barrier:timing':['barrier:candidate_verified']},
            'submitted_requests':len(plan['requests'])+len(rows),'raw_capture_requests':captures,'capture_cap':80,
            'retry_or_extra_fill_requests':0,'native_reference_captures':20,'candidate_compared_clips':10,'timed_compared_clips':40,
            'timed_full_suite_clips':10,'timed_bounded_continuity_clips':30,
            'obligations':['Exact registered setup order and per-kind verdict checks in trusted executor adapter',
                           'Quiescence plus durable completed-tail retirement at explicit barriers; no clear/recompute',
                           'Native proof verified before any sampler route/sentry/replica installation',
                           'Actual memory/storage admission and pending-tail observation; no automatic extra captures']}
    return {'schedule':result,'schedule_sha256':sha(canonical(result))}


def validate_schedule(value, packet=PARENT, plan_path=PLAN):
    require(value==build_schedule(packet,plan_path),'Schedule differs from pinned reconstruction')
    return value


if __name__=='__main__':print(json.dumps(build_schedule(),indent=2,sort_keys=True))
