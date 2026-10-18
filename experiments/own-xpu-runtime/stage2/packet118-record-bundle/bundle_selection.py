"""Independent CPU-qualified choices; placement is separately memory-qualified."""
import hashlib,itertools,json
from pathlib import Path
P=Path(__file__).resolve().parent
PLACEMENTS={'1':(1,0,24)}
DENSE=('production',); EXPERTS=('wide64+halfcache',)
HC=('hc-wide',); HOST=('ordered',)
ROUTE=('fast',); NORM=('production',)
RECURRENCE=('rec-both-plus',)
DRAFT_HEAD=('production',)
HEAD=('production',); HC_NORM=('production',)
DOWN=('tile16',); DRAFT_ATTENTION=('split32',)
OTHER_FUSION=('fused',); TARGET_HEAD=('split',)
DRAFT_PREFIX=('91392','80128')
KEYS=('dense','hc','experts','host','route','norm','recurrence','draft_head','head','hc_norm','down','draft_attention','other_fusion','target_head','draft_prefix')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def name(dense,hc,experts,host='production',route='production',norm='production',recurrence='production',draft_head='production',head='production',hc_norm='production',down='production',draft_attention='split32',other_fusion='production',target_head='split',draft_prefix='91392'):
    values=(dense,hc,experts,host,route,norm,recurrence,draft_head,head,hc_norm,down,draft_attention,other_fusion,target_head,draft_prefix)
    if any(v not in allowed for v,allowed in zip(values,(DENSE,HC,EXPERTS,HOST,ROUTE,NORM,RECURRENCE,DRAFT_HEAD,HEAD,HC_NORM,DOWN,DRAFT_ATTENTION,OTHER_FUSION,TARGET_HEAD,DRAFT_PREFIX))):
        raise ValueError('unregistered composition; dense must be production, experts wide64')
    return '--'.join(values)
def views():return {name(*v):v for v in itertools.product(DENSE,HC,EXPERTS,HOST,ROUTE,NORM,RECURRENCE,DRAFT_HEAD,HEAD,HC_NORM,DOWN,DRAFT_ATTENTION,OTHER_FUSION,TARGET_HEAD,DRAFT_PREFIX)}
def placements(v):
    # Packet83 preregisters rank1 / 24+24 only. Q4 also exceeds split23's arena.
    return PLACEMENTS if v[7]=='production' else {'1':PLACEMENTS['1']}
def configurations():
    return [(n,v,p) for n,v in views().items() for p in placements(v)]
def draft(v):
    d=json.loads((P/'selection-template.json').read_text())['draft']
    d['qsa_attention']='packet59' if v[11]=='split32' else 'production'
    d.update(head_format='q4-g32' if v[7]=='q4-g32' else 'production',head_prefix={'prefix990':'coverage990','prefix985':'coverage985'}.get(v[7],'production'))
    d['head_prefix']='production' if v[14]=='91392' else 'p114-80128'
    return d
def selection(v):
    s=json.loads((P/'selection-template.json').read_text());s.update(choices=choices(*v),draft=draft(v));return s
def prefix_rows(value):return {'production':91392,'q4-g32':91392,'prefix990':80128,'prefix985':74752}[value]
def choices(dense,hc,experts,host='production',route='production',norm='production',recurrence='production',draft_head='production',head='production',hc_norm='production',down='production',draft_attention='split32',other_fusion='production',target_head='split',draft_prefix='91392'):
    name(dense,hc,experts,host,route,norm,recurrence,draft_head,head,hc_norm,down,draft_attention,other_fusion,target_head,draft_prefix)
    result=dict(route='route-fast' if route=='fast' else 'route-exp32-rank4',
        recurrence='rows4-shared' if recurrence=='production' else recurrence,hc='production',miss='batch',experts={'wide64':'wide64','wide64+grid-prefetch':'exp-grid-prefetch','wide64+halfcache':'exp-halfcache','wide64+grid-prefetch+halfcache':'exp-grid-prefetch+halfcache'}[experts],
        packed_dense=dense,hc_gate='wide' if hc=='hc-wide' else 'production',
        host_retire='reply-first' if host=='ordered+reply-first' else host,hc_norm='consumer' if hc_norm=='normfuse' else 'production',head=head)
    if down=='tile16':result['experts']+='+'+'down-tile16'
    result['other_fusion']=other_fusion
    result['head']='head-split-compute' if target_head=='split' else 'production'
    return result
def view_path(row):return P/'selections'/(row['name']+'--placement-'+row['placement'])
def selected():
    row=json.loads((P/'bundle-selection.json').read_text());values=tuple(row[k] for k in KEYS)
    if row['name']!=name(*values):raise ValueError('view differs')
    if row['placement'] not in placements(values):raise ValueError('placement differs')
    if (row['draft_rank'],row['target_split'],row['layer_boundary'])!=PLACEMENTS[row['placement']]:raise ValueError('topology differs')
    if (row['draft'],row['miss'])!=('draft-hc','batch'):raise ValueError('record preset differs')
    selection=json.loads((P/'selection.json').read_text())
    if selection['choices']!=choices(*values):raise ValueError('selection differs')
    if selection['draft']!=draft(values):raise ValueError('draft selection differs')
    view=view_path(row)
    for leaf in ('selection.json','memory-plan.json','dispatch-speed6.json'):
        if sha(view/leaf)!=sha(P/leaf):raise ValueError('active bytes differ: '+leaf)
    if row['selection_sha256']!=sha(P/'selection.json') or row['screen_seal_sha256']!=sha(view/'screen-seal.json'):raise ValueError('seal differs')
    return row

def aliases():
    return {label:v for label,v in zip(("base","both"),views().values())}
