"""Fail if a reviewed operation source gains unreviewed host argument state."""
import hashlib,json,re
from pathlib import Path
P=Path(__file__).resolve().parent

def main():
 registry=json.loads((P/'argument-state-registry.json').read_text());header=(P/'argument_block.hpp').read_text()
 for name,wanted in registry['source_sha256'].items():
  assert hashlib.sha256((P/name).read_bytes()).hexdigest()==wanted, 'review new operation members before resealing '+name
 fields=set(re.findall(r'FIELD\((\w+)\)',header));classes=registry['classes']
 for row in classes:assert set(row['members'])<=fields,row
 result=dict(passed=True,device_executed=False,reviewed_operation_types=len(classes),reviewed_source_files=len(registry['source_sha256']),members=sum(len(x['members']) for x in classes),registry_sha256=hashlib.sha256((P/'argument-state-registry.json').read_bytes()).hexdigest(),serializer_sha256=hashlib.sha256(header.encode()).hexdigest(),scope='Source-sealed manual member inventory plus serializer-field coverage; canonical full scalar-state blocks are compared in the runtime audit. This is not C++ reflection.')
 (P/'argument-state-gates.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
