"""Explicit fixture-only layout projection; never used by device screen."""
import copy,json
from build_engine import P,sha,save
def prepare():
    paths=[]
    for name in ('selection','candidate'):
        row=json.loads((P/'lineage'/(name+'.json')).read_text())
        original=copy.deepcopy(row)
        # Packet100 correctly refuses its full-model layout on miniature shapes.
        row['choices']['experts']='wide64'
        row['choices']['head']='production'
        assert row['draft']==original['draft']
        assert all(row['choices'][k]==v for k,v in original['choices'].items() if k not in ('experts','head'))
        path=P/'lineage'/('mini-'+name+'.json');save(path,row);paths.append(path)
    return paths
