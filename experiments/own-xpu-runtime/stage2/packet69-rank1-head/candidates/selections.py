"""Independent site choices; unchanged production is default and both controls."""
import copy,json
from pathlib import Path
P=Path(__file__).resolve().parent
CHOICES=('production','target-wide64','target-wide128','draft-head-wide64','draft-attention','draft-hc','combined')

def selection(choice):
    assert choice in CHOICES
    base=json.loads((P.parent/'selection.json').read_text())
    base['decision']=None
    base['choices'].update(target_head='production',draft_head='production')
    if choice.startswith('target-'):base['choices']['target_head']=choice.removeprefix('target-')
    if choice in ('draft-head-wide64','combined'):base['choices']['draft_head']='wide64'
    if choice in ('draft-attention','combined'):base['draft']['qsa_attention']='packet59'
    if choice in ('draft-hc','combined'):
        hc=json.loads((P.parents[1]/'packet64-record-bundle/selections/1-draft-hc-control/selection.json').read_text())['draft']
        for key,value in hc.items():
            if value!='production':base['draft'][key]=value
    if choice=='combined':base['choices']['target_head']='wide64'
    return base

def prepare():
    for choice in CHOICES:
        d=P/'selections'/choice;d.mkdir(parents=True,exist_ok=True)
        assert not (d/'screen-seal.json').exists()
        (d/'selection.json').write_text(json.dumps(selection(choice),indent=2)+'\n')
    (P/'selection.json').write_text(json.dumps(selection('production'),indent=2)+'\n')
if __name__=='__main__':prepare()
