"""Bundle8 fixed arithmetic plus the four registered bundle9 dimensions."""
import json
import bundle8_selection as old
from compositions import P,ROOT,sha,read,validate,key,native,all_compositions,DIMENSIONS
PLACEMENTS=old.PLACEMENTS
KEYS=old.KEYS+DIMENSIONS
FIXED=tuple(read(P/'lineage-inputs/inherited-root/bundle-selection.json')[k] for k in old.KEYS)
assert FIXED[-1]=='banks'
def name(*v):
 if tuple(v[:16])!=FIXED:raise ValueError('bundle8 choices must stay fixed')
 return 'bundle9-'+key(dict(zip(DIMENSIONS,v[16:])))
def views():return {name(*(FIXED+tuple(s[k] for k in DIMENSIONS))):FIXED+tuple(s[k] for k in DIMENSIONS) for s in all_compositions()}
def placements(v):name(*v);return PLACEMENTS
def configurations():return [(n,v,'1') for n,v in views().items()]
def selection(v):name(*v);return native(dict(zip(DIMENSIONS,v[16:])))
def choices(*v):return selection(v)['choices']
def draft(v):return selection(v)['draft']
def prefix_rows(v):return old.prefix_rows(v)
def view_path(row):return P/'selections'/key({k:row[k] for k in DIMENSIONS})
def aliases():return {'base':next(iter(views().values())),'both':list(views().values())[-1]}
def selected():
 row=read(P/'bundle-selection.json');values=tuple(row[k] for k in KEYS)
 if row['name']!=name(*values) or row['placement']!='1' or (row['draft_rank'],row['target_split'],row['layer_boundary'])!=(1,0,24) or row['miss']!='banks-batch':raise ValueError('composition/topology differs')
 view=view_path(row)
 for leaf in ('selection.json','memory-plan.json','dispatch-speed6.json'):
  if sha(P/leaf)!=sha(view/leaf):raise ValueError('active selection bytes differ '+leaf)
 if read(P/'selection.json')!=selection(values):raise ValueError('native choices differ')
 if row['selection_sha256']!=sha(P/'selection.json') or row['screen_seal_sha256']!=sha(view/'screen-seal.json'):raise ValueError('selection seal differs')
 return row
