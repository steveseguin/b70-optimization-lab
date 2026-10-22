"""Selected draft metadata shared by KD, the chain seal and submission replay."""
import json,re
from pathlib import Path
P=Path(__file__).resolve().parent
def identity(bundle):
 from bundle_selection import prefix_rows
 from build_engine import sha
 coverage=sha(P/'coverage.json')
 declared=re.search(r'coverage_sha256\[\]="([0-9a-f]{64})"',(P/'p83_head.hpp').read_text()).group(1)
 if coverage!=declared:raise ValueError('draft coverage identity changed')
 return dict(draft_vocab_rows=int(bundle['draft_prefix']),full_vocab_rows=248320,selection_sha256=coverage,head_choice=bundle['draft_head'],target_head_unchanged=True)
def validate_prefix(prefix,expected,mini=False):
 if not (prefix.get('rows')==(prefix.get('full_rows') if mini else expected['draft_vocab_rows']) and (mini or prefix.get('full_rows')==expected['full_vocab_rows']) and prefix.get('calibration_sha256')==expected['selection_sha256'] and prefix.get('target_head_unchanged') is True):
  raise ValueError('KD host prefix identity')
