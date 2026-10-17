"""Use each frozen packet's compare/best logic in an isolated interpreter."""
import contextlib,hashlib,io,json,sys,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def collect(packet):
 suffix={81:'experts3',82:'recurrence',83:'draft-bytes'}[packet]
 folder=ROOT/f'experiments/own-xpu-runtime/stage2/packet{packet}-{suffix}'
 sys.path.insert(0,str(folder));import compare as c;import screen_jobs as jobs
 boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 result=dict(packet=packet,boot_id=boot,status='pending',lanes={},receipts={},sources={str(f.relative_to(ROOT)):sha(f) for f in folder.glob('*.py')})
 def load(lane,entries):
  rows=[]
  for job in entries:
   path=c.HERE/'evidence'/job['out']
   # Retain failed/incomplete receipt identity as well as winning evidence.
   for f in path.rglob('*'):
    if f.is_file() and not f.is_symlink() and f.suffix in ('.json','.jsonl'):result['receipts'][str(f.relative_to(ROOT))]=sha(f)
   r=c.load(job,lane);c.require(c.read(path/'window.json')['boot_id']==boot,'stale screen boot')
   c.require(math.isfinite(r['rate']) and r['rate']>0,'invalid rate');r['exact_count']=13 if r['exact'] else 0;rows.append(r)
  return rows
 def direction(source):
  other='B' if source=='A' else 'A';proof=dict(source_lane=source,status='pending',lanes={})
  try:
   a=load(source,jobs.jobs(source,mode='grid') if packet==83 else jobs.jobs(source));proof['lanes'][source]=a
   c.require(all(r['exact'] and r['exact_count']==13 for r in a),'all grid requests must be exact')
   try:best=jobs.choose(a)
   except ValueError:
    if all(r['rate']<=max(a[0]['rate'],a[-1]['rate']) for r in a[1:-1]):proof['status']='no-winner';return proof
    raise
   control=max(a[0]['rate'],a[-1]['rate']);proof['best']=dict(best,control=control,ratio=best['rate']/control)
   b=load(other,jobs.jobs(other,best['choice'],mode='confirm') if packet==83 else jobs.jobs(other,best['choice']));proof['lanes'][other]=b
   c.require([r['choice'] for r in b]==['production',best['choice'],'production'],'confirmation selection differs')
   c.require(all(r['exact_count']==13 and r['exact'] for r in b),'confirmation must be 13/13 exact')
   control=max(b[0]['rate'],b[-1]['rate']);proof['confirmation']=dict(choice=best['choice'],rate=b[1]['rate'],control=control,ratio=b[1]['rate']/control)
   proof['status']='winner' if b[1]['rate']>control else 'no-winner'
  except (OSError,ValueError,KeyError,TypeError,AssertionError) as e:proof['error']=str(e)
  return proof
 try:
  c.cpu_gate();jobs.verify()
  directions=[direction('A')]
  if packet==83:directions.append(direction('B'))
  result['directions']=directions;winners=[r for r in directions if r['status']=='winner']
  if len({r['best']['choice'] for r in winners})>1:result.update(status='conflict',error='valid directional confirmations disagree')
  elif winners:result.update(winners[0])
  elif all(r['status']=='no-winner' for r in directions):result['status']='no-winner'
  # For packet83 a valid complete no-winner grid closes the lever unless the
  # other direction has an improving candidate awaiting its confirmation.
  elif packet==83 and any(r['status']=='no-winner' for r in directions) and not any('best' in r and r['status']=='pending' for r in directions):result['status']='no-winner'
 except (OSError,ValueError,KeyError,TypeError,AssertionError) as e:result['error']=str(e)
 return result
if __name__=='__main__':
 with contextlib.redirect_stdout(io.StringIO()):
  try:r=collect(int(sys.argv[1]))
  except (OSError,ValueError,KeyError,TypeError,AssertionError) as e:r=dict(packet=int(sys.argv[1]),status='pending',error=str(e),lanes={},receipts={},sources={})
 print(json.dumps(r))
