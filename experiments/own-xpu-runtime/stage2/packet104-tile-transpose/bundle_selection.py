"""Local packet97 snapshot + down-tile16; three screening choices only."""
import json
from build_engine import P
NAMES=('production','target-gate-tile16','target-gate-halfcache-tile16')
def views():return {n:(n,) for n in NAMES}
def selection(v):
 n=v if isinstance(v,str) else v[0]
 assert n in NAMES
 return json.loads((P/'selections'/n/'selection.json').read_text())
def choices(*v):return selection(v[0])['choices']
def selected():return dict(draft_rank=1,target_split=0,selection_sha256=None)
