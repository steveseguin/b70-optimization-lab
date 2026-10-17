"""Independent CPU-qualified choices; placement is separately memory-qualified."""
import hashlib,itertools,json
from pathlib import Path
P=Path(__file__).resolve().parent
PLACEMENTS={'1':(1,0,24),'1-split23':(1,23,23),'0':(0,24,24),'0-split23':(0,23,23)}
DENSE=('production',); EXPERTS=('wide64','gate-input-packed','down-input-packed','input-packed')
HC=('production','hc-wide'); HOST=('production','ordered')
ROUTE=('production','fast'); NORM=('production','fused')
RECURRENCE=('production','rec-gates','rec-parallel')
DRAFT_HEAD=('production','q4-g32','prefix990','prefix985')
KEYS=('dense','hc','experts','host','route','norm','recurrence','draft_head')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def name(dense,hc,experts,host='production',route='production',norm='production',recurrence='production',draft_head='production'):
    values=(dense,hc,experts,host,route,norm,recurrence,draft_head)
    if any(v not in allowed for v,allowed in zip(values,(DENSE,HC,EXPERTS,HOST,ROUTE,NORM,RECURRENCE,DRAFT_HEAD))):
        raise ValueError('unregistered composition; dense must be production, experts wide64')
    return '--'.join(values)
def views():return {name(*v):v for v in itertools.product(DENSE,HC,EXPERTS,HOST,ROUTE,NORM,RECURRENCE,DRAFT_HEAD)}
def placements(v):
    # Packet83 preregisters rank1 / 24+24 only. Q4 also exceeds split23's arena.
    return PLACEMENTS if v[-1]=='production' else {'1':PLACEMENTS['1']}
def configurations():
    return [(n,v,p) for n,v in views().items() for p in placements(v)]
def draft(v):
    d=json.loads((P/'selection-template.json').read_text())['draft']
    d.update(head_format='q4-g32' if v[-1]=='q4-g32' else 'production',head_prefix={'prefix990':'coverage990','prefix985':'coverage985'}.get(v[-1],'production'))
    return d
def selection(v):
    s=json.loads((P/'selection-template.json').read_text());s.update(choices=choices(*v),draft=draft(v));return s
def prefix_rows(value):return {'production':91392,'q4-g32':91392,'prefix990':80128,'prefix985':74752}[value]
def choices(dense,hc,experts,host='production',route='production',norm='production',recurrence='production',draft_head='production'):
    name(dense,hc,experts,host,route,norm,recurrence,draft_head)
    return dict(route='route-fast' if route=='fast' else 'route-exp32-rank4',
        recurrence='rows4-shared' if recurrence=='production' else recurrence,hc='production',miss='batch',experts=experts,
        packed_dense=dense,hc_gate='wide' if hc=='hc-wide' else 'production',
        host_retire=host,hc_norm='subgroup' if norm=='fused' else 'production')
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
