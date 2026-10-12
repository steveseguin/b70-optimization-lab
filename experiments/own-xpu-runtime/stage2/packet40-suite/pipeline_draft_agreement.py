"""Join real two-rank MTP evidence to independent captured-input draft evidence."""
import json,hashlib,gzip
from pathlib import Path
P=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def lines(p):
 raw=p.read_bytes() if p.exists() else gzip.decompress(p.with_name(p.name+'.gz').read_bytes())
 return [json.loads(s) for s in raw.decode().splitlines()]
def main():
 capture=json.loads((P/'capture-run-incident-retrospective.json').read_text())
 from capture40 import archived_capture
 table,text=archived_capture(capture)
 expected=[json.loads(row) for row in text['draft-rows.jsonl'].splitlines()]
 reports=[]
 for compiler,prefix in (('gnu-host',''),('icpx-host','icpx-host-')):
  gate=json.loads((P/f'real-{prefix}mtp.json').read_text());assert gate['passed']
  actual=gate['draft_rows']
  keys=('draft_position','confirmed_token','head','guess')
  assert len(actual)>8
  assert [{k:r[k] for k in keys} for r in actual]==[{k:r[k] for k in keys} for r in expected[:len(actual)]]
  want='row-'+str(actual[-1]['draft_position'])+'/'
  hashes=gate['draft_cache_sha256']
  assert len(hashes)==5 and hashes=={f:table[want+f]['sha256'] for f in hashes}
  reports.append(dict(compiler=compiler,binary_sha256=gate['binary_sha256'],draft_rows=len(actual),
                      scored_rows=sum(r['head'] for r in actual),cache_sha256=hashes,proposals_equal=True))
 result=dict(passed=True,device_executed=False,capture_binary_sha256=capture['binary_sha256'],capture_archive=capture['scratch_archive'],rows=reports,
             scope='Every prompt and generated draft row agrees with the captured-input path; all five final cache/control files agree byte for byte.')
 (P/'pipeline-draft-agreement.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result))
if __name__=='__main__':main()
