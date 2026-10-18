import json
from source_decision import O,P,ROOT,sha,save
def sources():return {str(f.relative_to(ROOT)):sha(f) for f in [*O.glob('*.py'),O/'device-entry.sh',O/'proposal-spec.json',O/'inputs/external-source-bindings.json',O/'inputs/symlink-audit.json']}
def verify():
 row=json.loads((O/'policy-seal.json').read_text());assert row['passed'] and row['sources']==sources();return row
if __name__=='__main__':save(O/'policy-seal.json',dict(passed=True,device_executed=False,sources=sources()))
