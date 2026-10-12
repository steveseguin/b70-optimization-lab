"""Lossless teardown storage for long oracle runs; never touches other directories."""
import gzip,json
from pathlib import Path

def load_teardown(directory):
 raw=directory/'teardown.json'
 if raw.exists():return json.loads(raw.read_text())
 with gzip.open(directory/'teardown.json.gz','rt') as f:return json.load(f)

def retain_teardown(directory,compress,save,sha):
 raw=directory/'teardown.json'
 if raw.exists():
  info=compress(raw)
  save(directory/'teardown-retention.json',dict(schema='iq3-long.lossless-retention.v1',original_name=raw.name,**info,
    reason='Full native CPU allocation/teardown receipt grows beyond GitHub single-file limits for long contexts. Lossless gzip, raw hash verified before removing raw file.',restore='gzip -dc teardown.json.gz > teardown.json; verify original SHA256 from this receipt'))
 info=json.loads((directory/'teardown-retention.json').read_text())
 assert sha(directory/'teardown.json.gz')==info['compressed_sha256']
 return info
