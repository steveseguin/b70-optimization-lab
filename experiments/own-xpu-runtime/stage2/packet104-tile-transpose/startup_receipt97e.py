"""Verify all 33 startup paths and their exact selected input identities."""
import gzip,hashlib,json
from build_engine import P,ROOT,sha
from chain_seal import check_map

def verify():
 row=json.loads((P/'startup97e.json').read_text());assert row['passed'] and row['device_executed'] is False and row['total_windows']==33
 check_map(ROOT,row['sources']);a=row['archive'];assert sha(ROOT/a['path'])==a['sha256']
 raw=gzip.decompress((ROOT/a['path']).read_bytes());assert hashlib.sha256(raw).hexdigest()==a['uncompressed_sha256']
 runs=json.loads(raw)['runs']
 from bundle_selection import views,selection
 from startup97e import WINDOWS
 assert len(runs)==33 and {(r['view'],r['window']) for r in runs}=={(v,w) for v in views() for w in WINDOWS}
 for r in runs:assert r['selected']==selection(r['view']) and r['target_selection_sha256']==sha(P/'selections'/r['view']/'selection.json')
 assert row['old_code_refusal']['returncode']!=0
 return row
