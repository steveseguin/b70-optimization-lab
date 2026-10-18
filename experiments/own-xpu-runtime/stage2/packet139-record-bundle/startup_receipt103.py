"""Unchanged packet137 production-shape evidence, explicitly reused."""
import json
from build_engine import P,ROOT,sha
from chain_seal import check_map
def verify():
 row=json.loads((P/'startup103.json').read_text())
 assert row['passed'] and row['device_executed'] is False and row['reused_unchanged'] is True
 check_map(ROOT,row['sources'])
 from reuse_build import verify_native
 verify_native()
 assert json.loads((P/'selection.json').read_text())==json.loads((P.with_name('packet137-token-input')/'v5/lineage/candidate.json').read_text())
 return row
