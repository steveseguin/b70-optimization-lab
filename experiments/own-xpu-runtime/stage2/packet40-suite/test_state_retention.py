#!/usr/bin/env python3
"""CPU-only exact-byte request-state retention and corruption refusal gate."""
import hashlib,json,shutil
from pathlib import Path
import suite,storage
P=Path(__file__).resolve().parent

def run_gates():
 root=P/'build/reset-retention-unit';assert not root.exists();root.mkdir()
 try:
  storage.admit(1_000_000)
  state=root/'rank0/state-2147483647';state.mkdir(parents=True)
  raw=b'complete-target-bytes';h=hashlib.sha256(raw).hexdigest()
  (state/'x.bin').write_bytes(raw);(state/'state.json').write_text(json.dumps({'buffers':{'x':h}}))
  fixture=root/'rank0/step1/layer-00.bf16';fixture.parent.mkdir();fixture.write_bytes(b'fixture')
  original={str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in state.iterdir()}
  result=suite.retain_request_state(root);archive=suite.retained_state(root)
  assert {name:row['sha256'] for name,row in archive.items()}==original
  assert not list(state.iterdir()) and fixture.read_bytes()==b'fixture'
  bad=root/'rank1/state-2147483647';bad.mkdir(parents=True)
  (bad/'y.bin').write_bytes(b'wrong');(bad/'state.json').write_text(json.dumps({'buffers':{'y':h}}))
  rejected=False
  try:suite.retain_request_state(root)
  except ValueError as error:rejected='hash mismatch' in str(error)
  assert rejected and (bad/'y.bin').read_bytes()==b'wrong'
  return dict(passed=True,device_executed=False,metadata_gzip_roundtrip=True,
              all_original_file_hashes_preserved=True,raw_snapshot_removed=True,
              retained_fixture_unchanged=True,recorded_hash_corruption_rejected_before_deletion=True,
              retention=result,source_sha256={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in
                  ['suite.py','suite_gates.py','native_mini_gate.py','storage.py','test_state_retention.py']})
 finally:shutil.rmtree(root)

if __name__=='__main__':
 result=run_gates();(P/'reset-retention-gate-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
