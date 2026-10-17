"""Independent, registered packet74 dense and packet73 HC/expert choices."""
import hashlib,json,itertools
from pathlib import Path
P=Path(__file__).resolve().parent
PLACEMENTS={'1':(1,0,24)}
DENSE=('production','head-packed','dense-packed','combined')
HC=('production','hc-wide')
EXPERTS=('wide64','experts2-a','experts2-b')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def name(dense,hc,experts):
    if dense not in DENSE or hc not in HC or experts not in EXPERTS:raise ValueError('unregistered composed view')
    return dense+'--'+hc+'--'+experts
def views():return {name(*v):v for v in itertools.product(DENSE,HC,EXPERTS)}
def choices(dense,hc,experts):
    name(dense,hc,experts)
    return dict(route='route-exp32-rank4',recurrence='rows4-shared',hc='production',miss='batch',experts=experts,packed_dense=dense,hc_gate='wide' if hc=='hc-wide' else 'production')
def selected():
    row=json.loads((P/'bundle-selection.json').read_text())
    if row['name']!=name(row['dense'],row['hc'],row['experts']):raise ValueError('view differs')
    if (row['placement'],row['draft'],row['miss'],row['draft_rank'],row['target_split'],row['layer_boundary'])!=('1','draft-hc','batch',1,0,24):raise ValueError('packet70 preset differs')
    selection=json.loads((P/'selection.json').read_text())
    if selection['choices']!=choices(row['dense'],row['hc'],row['experts']):raise ValueError('selection differs')
    view=P/'selections'/row['name']
    for leaf in ('selection.json','memory-plan.json','dispatch-speed6.json'):
        if sha(view/leaf)!=sha(P/leaf):raise ValueError('active bytes differ: '+leaf)
    if row['selection_sha256']!=sha(P/'selection.json') or row['screen_seal_sha256']!=sha(view/'screen-seal.json'):raise ValueError('seal differs')
    return row
