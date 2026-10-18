"""Packet97's ten dimensions plus the existing independent draft attention flag."""
import importlib.util,itertools,json
from pathlib import Path
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('p101_frozen_p97_selection',P.parent/'packet97-record-bundle/bundle_selection.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
KEYS=base.KEYS+('draft_attention','draft_hc')
BASELINE=('production','hc-wide','wide64','ordered','production','production','rec-parallel','production','production','production')
def name(*v):
    assert len(v)==12 and v[10] in ('production','split32') and v[11]=='packet59'
    return base.name(*v[:10])+'--draft_attention-'+v[10]+'--draft_hc-'+v[11]
def choices(*v):name(*v);return base.choices(*v[:10])
def selection(v):
    name(*v);s=base.selection(v[:10]);s['draft']['qsa_attention']='packet59' if v[10]=='split32' else 'production'
    return s
def views():
    return {name(*v,a,'packet59'):(*v,a,'packet59') for v in base.views().values() for a in ('production','split32')}
def aliases():
    return {'control':(*BASELINE,'production','packet59'),
            'draft_attention':(*BASELINE,'split32','packet59'),
            'draft_hc':(*BASELINE,'production','packet59'),
            'combined':(*BASELINE,'split32','packet59')}
