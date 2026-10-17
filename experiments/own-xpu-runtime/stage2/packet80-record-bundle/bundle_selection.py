"""Independent CPU-qualified choices; placement is separately memory-qualified."""
import hashlib,itertools,json
from pathlib import Path
P=Path(__file__).resolve().parent
PLACEMENTS={'1':(1,0,24),'1-split23':(1,23,23),'0':(0,24,24),'0-split23':(0,23,23)}
DENSE=('production',); EXPERTS=('wide64',)
HC=('production','hc-wide'); HOST=('production','ordered')
ROUTE=('production','fast'); NORM=('production','fused')
KEYS=('dense','hc','experts','host','route','norm')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def name(dense,hc,experts,host='production',route='production',norm='production'):
    values=(dense,hc,experts,host,route,norm)
    if any(v not in allowed for v,allowed in zip(values,(DENSE,HC,EXPERTS,HOST,ROUTE,NORM))):
        raise ValueError('unregistered composition; dense must be production, experts wide64')
    return '--'.join(values)
def views():return {name(*v):v for v in itertools.product(DENSE,HC,EXPERTS,HOST,ROUTE,NORM)}
def choices(dense,hc,experts,host='production',route='production',norm='production'):
    name(dense,hc,experts,host,route,norm)
    return dict(route='route-fast' if route=='fast' else 'route-exp32-rank4',
        recurrence='rows4-shared',hc='production',miss='batch',experts=experts,
        packed_dense=dense,hc_gate='wide' if hc=='hc-wide' else 'production',
        host_retire=host,hc_norm='subgroup' if norm=='fused' else 'production')
def view_path(row):return P/'selections'/(row['name']+'--placement-'+row['placement'])
def selected():
    row=json.loads((P/'bundle-selection.json').read_text());values=tuple(row[k] for k in KEYS)
    if row['name']!=name(*values):raise ValueError('view differs')
    if row['placement'] not in PLACEMENTS:raise ValueError('placement differs')
    if (row['draft_rank'],row['target_split'],row['layer_boundary'])!=PLACEMENTS[row['placement']]:raise ValueError('topology differs')
    if (row['draft'],row['miss'])!=('draft-hc','batch'):raise ValueError('record preset differs')
    selection=json.loads((P/'selection.json').read_text())
    if selection['choices']!=choices(*values):raise ValueError('selection differs')
    view=view_path(row)
    for leaf in ('selection.json','memory-plan.json','dispatch-speed6.json'):
        if sha(view/leaf)!=sha(P/leaf):raise ValueError('active bytes differ: '+leaf)
    if row['selection_sha256']!=sha(P/'selection.json') or row['screen_seal_sha256']!=sha(view/'screen-seal.json'):raise ValueError('seal differs')
    return row
