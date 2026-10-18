"""Bind static linked-code scheduling evidence; no latency/speed inference."""
import gzip,json,re
from build_engine import P,ROOT,sha,save,limits

def main():
 limits();report=json.loads((P/'register-report-offline.json').read_text());rows=[];sources={str((P/'inspect_schedule.py').relative_to(ROOT)):sha(P/'inspect_schedule.py'),str((P/'register-report-offline.json').relative_to(ROOT)):sha(P/'register-report-offline.json')}
 for kernel in report['kernels']:
  path=ROOT/kernel['assembly'];assert sha(path)==kernel['sha256'];sources[kernel['assembly']]=sha(path)
  lines=gzip.decompress(path.read_bytes()).decode().splitlines();windows=[]
  flag_moves=[(i+1,l) for i,l in enumerate(lines) if re.search(r'\bmov\b.*\bf\d+\.\d+',l) and not l.lstrip().startswith('//')]
  assert not flag_moves,flag_moves
  assert not kernel['scratch_messages'] and not kernel['spill_metadata']
  for i,line in enumerate(lines):
   if 'load.ugm.d32x2.a64' not in line:continue
   token=re.search(r'\$(\d+)',line)[1]
   end=next((j for j in range(i+1,len(lines)) if '$'+token+'.dst' in lines[j]),None)
   if end is None:continue
   fp=[j+1 for j in range(i+1,end) if re.search(r'\b(mul|add) \(',lines[j]) and ':f' in lines[j]]
   windows.append(dict(issue_line=i+1,first_destination_wait_line=end+1,scoreboard_token=int(token),static_fp32_mul_add_lines=fp,issue=line.strip(),wait=lines[end].strip()))
  rows.append(dict(kernel=kernel['name'],assembly=kernel['assembly'],configured_grf=kernel['configured_grf'],static_instructions=kernel['static_instructions'],static_load_instructions=len(kernel['static_load_lines']),scratch_messages=0,flag_register_moves=0,windows=windows))
 candidate=next(r for r in rows if 'p95exp' in r['kernel']);assert len([w for w in candidate['windows'] if len(w['static_fp32_mul_add_lines'])>=8])==8
 save(P/'evidence/linked-schedule.json',dict(passed=True,device_executed=False,sources=sources,kernels=rows,scope='Static linked BMG-G31 code only. Control-flow alternatives count separately; not executed instruction counts, latency, overlap duration or measured speed. Source/table-address inspection identifies eight next-tile table loads; destination waits occur after intervening current-tile FP32 arithmetic.'))
 print('eight next-tile static scheduling windows; no scratch/flag register moves')
if __name__=='__main__':main()
