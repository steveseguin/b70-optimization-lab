"""Fail closed on the new all-window CPU gate, including its retained archive."""
import gzip,hashlib,json
from build_engine import P,ROOT,sha
from bundle_selection import views

def verify():
    row=json.loads((P/'startup103.json').read_text())
    assert row['passed'] and row['device_executed'] is False and row['total_windows']==len(views())*11
    from chain_seal import check_map
    check_map(ROOT,row['sources'])
    archive=row['archive'];assert sha(ROOT/archive['path'])==archive['sha256']
    raw=gzip.decompress((ROOT/archive['path']).read_bytes())
    assert hashlib.sha256(raw).hexdigest()==archive['uncompressed_sha256']
    runs=json.loads(raw)['runs']
    from startup103 import WINDOWS
    assert len(runs)==len(views())*11
    assert {(r['view'],r['window']) for r in runs}=={(v,w) for v in views() for w in WINDOWS}
    assert row['old_code_refusal']['returncode']!=0 and any(message in row['old_code_refusal']['error'] for message in ('p90 cached layout requires', 'p100 locality requires sealed'))
    return row
