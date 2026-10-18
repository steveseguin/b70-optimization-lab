"""One-time explicit adaptations of copied consumers (never parent files)."""
from pathlib import Path
import json,shutil
P=Path(__file__).resolve().parents[2]/'stage2/packet84-record-bundle'
BASE=P.parent/'packet80-record-bundle'
def edit(n,a,b):
 f=P/n;t=f.read_text();assert a in t,(n,a);f.write_text(t.replace(a,b))
for name in ('dispatch-speed6-provenance.json','dispatch-default.json','dispatch-p45.json'):
 shutil.copyfile(BASE/name,P/name)
edit('fast_reseal.py','NORM, KEYS','NORM, RECURRENCE, DRAFT_HEAD, KEYS')
edit('fast_reseal.py',"    a=ap.parse_args();start=time.monotonic()","    ap.add_argument('--recurrence',choices=RECURRENCE,default='production')\n    ap.add_argument('--draft_head',choices=DRAFT_HEAD,default='production')\n    a=ap.parse_args();start=time.monotonic()")
edit('fast_reseal.py',"    seal=json.loads((view/'screen-seal.json').read_text())","    from prepare_packet import seal_view\n    seal_view(tuple(getattr(a,k) for k in KEYS),a.placement)\n    seal=json.loads((view/'screen-seal.json').read_text())")
edit('fast_reseal.py','norm=a.norm,','norm=a.norm,recurrence=a.recurrence,draft_head=a.draft_head,')
edit('p49_dispatch.py',"    new_coverage=measured_coverage", "    if inherited.get('recurrence') in ('rec-gates','rec-parallel'):inherited['recurrence']='rows4-shared'\n    new_coverage=measured_coverage")
edit('packet56_submission.py','from bundle_selection import name, choices, PLACEMENTS, KEYS','from bundle_selection import name, choices, PLACEMENTS, KEYS, draft as selected_draft, placements')
edit('packet56_submission.py',"    draft=selection.get('draft', {})","    require(bundle['placement'] in placements(values),'draft head placement differs')\n    draft=selection.get('draft', {})\n    require(draft==selected_draft(values),'draft head selection differs')")
edit('packet56_submission.py',"all(value in ('production','packet59') for value in draft.values())","all(value in ('production','packet59') for key,value in draft.items() if key not in ('head_format','head_prefix'))")
edit('packet56_submission.py',"'Draft prefix 91,392/248,320 rows; private prefix only on rank0, shared head on rank1. unchanged full target verifies all accepted tokens. '","f\"Recurrence={bundle['recurrence']}; draft_head={bundle['draft_head']}. \"\n        f\"Draft prefix {__import__('bundle_selection').prefix_rows(bundle['draft_head'])}/248320 rows. Q4/g32 changes draft-only arithmetic when selected; smaller N changes proposals only. Unchanged full target verifies every accepted token. \"")
edit('packet56_submission.py',"('host','route','norm','hc','placement','experts','dense')","('host','route','norm','hc','placement','experts','dense','recurrence','draft_head')")
edit('packet56_submission.py','draftHeadPrefix=dict(rows=91392,','draftHeadPrefix=dict(rows=__import__(\'bundle_selection\').prefix_rows(bundle[\'draft_head\']),format=bundle[\'draft_head\'],')
edit('placement.py',"require(audit['draft_prefix_rows']==91392", "require(audit['draft_prefix_rows'] in (91392,80128,74752)")
print('Consumers adapted')
