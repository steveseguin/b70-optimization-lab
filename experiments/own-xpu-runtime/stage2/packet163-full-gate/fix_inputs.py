import json,shutil,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent
for name in ['one-card','two-card']:
 p=P/name
 for f in (p/'inputs').glob('*/input.json'):
  if f.parent.name=='prefill512':continue
  old=json.loads(f.read_text());hist=p/'lineage/input-metadata'/f.parent.name/'input.json';hist.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,hist)
  source=f.parent/'source.txt';shutil.copy2(old['prompt'],source)
  assert hashlib.sha256(source.read_bytes()).hexdigest()==old['prompt_sha256']
  new=dict(model_dir=old['model_dir'],prompt=str(source),prompt_sha256=old['prompt_sha256'],tokens=old['tokens'],files={'tokens.txt':old['files']['tokens.txt']},historical_metadata=str(hist))
  f.write_text(json.dumps(new,indent=2)+'\n')
 (p/'inputs/input.json').write_bytes((p/'inputs/incident-retrospective/input.json').read_bytes())
 f=p/'worker.py';s=f.read_text().replace("observed={}\n try:\n  exec_limits.check();pipeline.Transport", "observed={};previous=None\n def completed_streams(dest):\n  for rank in (0,1):measurement.check_file_stream(dest/f'rank{rank}/timings.jsonl')\n try:\n  exec_limits.check();pipeline.Transport")
 s=s.replace("check();dest=output/'requests'/entry['prompt_id'];suite.reset(transport,dest)","check();dest=output/'requests'/entry['prompt_id'];suite.reset(transport,dest)\n   if previous is not None:completed_streams(previous)")
 s=s.replace("    measurement.check_file_stream(dest/f'rank{rank}/timings.jsonl')\n",'')
 s=s.replace("observed[entry['prompt_id']]=record_request(dest,entry,result)\n  suite.reset(transport,output/'after-suite');transport.close(True)","observed[entry['prompt_id']]=record_request(dest,entry,result);previous=dest\n  suite.reset(transport,output/'after-suite');completed_streams(previous);transport.close(True)")
 f.write_text(s)
