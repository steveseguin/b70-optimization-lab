#!/usr/bin/env python3
"""Packet-local synthetic cleanup/path gates; no rank or device execution."""
import gzip,hashlib,json,tempfile
from pathlib import Path
import cleanup,pipeline_draft_agreement,storage
P=Path(__file__).resolve().parent

def run_gates():
 storage.admit(100_000)
 checks=[]
 def refuses(fn):
  try:fn()
  except AssertionError:return
  raise AssertionError('unsafe path admitted')
 with tempfile.TemporaryDirectory(prefix='cleanup-path-unit-',dir=P/'build') as tmp:
  root=Path(tmp);old=cleanup.B;cleanup.B=root/'build';cleanup.B.mkdir()
  try:
   d=cleanup.B/'draft-cpu-test';d.mkdir();rows=d/'draft-rows.jsonl';raw=b'{"token":1}\n{"token":2}\n';rows.write_bytes(raw)
   fixture=d/'layer-00.bf16';fixture.write_bytes(b'fixture-bf16')
   cache=d/'cache.bin';cache.write_bytes(b'full-cache')
   kd={p.name:p.read_bytes() for p in (fixture,cache)}
   want=pipeline_draft_agreement.lines(rows);reports=cleanup.compress_reference_rows()
   assert len(reports)==1 and not rows.exists() and gzip.decompress((d/'draft-rows.jsonl.gz').read_bytes())==raw
   assert pipeline_draft_agreement.lines(rows)==want
   checks.append('ordinary compression roundtrip and reader exactness')
   assert {p.name:p.read_bytes() for p in (fixture,cache)}==kd
   assert cleanup.capture_files(('timings.jsonl','prefill-timings.jsonl','progress.jsonl','sites.jsonl'))==[]
   checks.append('KD bf16 and bin inputs unchanged and excluded')
   outside=root/'outside';outside.mkdir();external=outside/'draft-rows.jsonl';external.write_bytes(raw)
   link=cleanup.B/'draft-cpu-parent-link';link.symlink_to(outside,target_is_directory=True)
   refuses(cleanup.compress_reference_rows);assert external.read_bytes()==raw and not (outside/'draft-rows.jsonl.gz').exists();link.unlink()
   checks.append('parent directory symlink refused before mutation')
   rows.symlink_to(external);refuses(cleanup.compress_reference_rows);assert external.read_bytes()==raw;rows.unlink()
   checks.append('input file symlink refused before mutation')
   rows.write_bytes(raw);target=d/'draft-rows.jsonl.gz';existing=target.read_bytes()
   refuses(cleanup.compress_reference_rows);assert rows.read_bytes()==raw and target.read_bytes()==existing
   checks.append('existing destination preserves both inputs')
   target.unlink();missing=outside/'missing';target.symlink_to(missing)
   refuses(cleanup.compress_reference_rows);assert rows.read_bytes()==raw and not missing.exists() and target.is_symlink()
   checks.append('dangling destination symlink refused')
  finally:cleanup.B=old
 return dict(passed=True,device_executed=False,rank_processes_started=0,synthetic_only=True,checks=checks,
             source_sha256={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in
                            ('cleanup.py','pipeline_draft_agreement.py','storage.py','test_cleanup_paths.py')})

if __name__=='__main__':
 result=run_gates();(P/'cleanup-path-gates.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
