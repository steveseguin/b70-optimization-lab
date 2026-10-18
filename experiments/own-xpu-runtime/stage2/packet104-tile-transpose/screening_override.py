"""Explicit coordinator exception, never a retroactive 15% micro pass."""
import json
from build_engine import P,ROOT,sha
CANDIDATES=('target-gate-tile16','target-gate-halfcache-tile16')
def verify():
 from restore_evidence104b import restore
 restore()
 from qualification import measured
 from chain_seal import check_map
 row=json.loads((P/'screening-override.json').read_text());check_map(ROOT,row['sources'])
 result=measured()
 assert not result['qualified'] and row['original_micro_gate_passed'] is False
 assert tuple(row['candidates'])==CANDIDATES and row['screen_only'] is True
 assert row['authorization']=='coordinator-p104b-2026-10-18'
 return CANDIDATES
