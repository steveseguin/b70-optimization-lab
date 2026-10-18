"""Consume only packet91's matched compositions; historical leads cannot win."""
import contextlib,io,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
P=ROOT/'experiments/own-xpu-runtime/stage2/packet91-record-bundle'
sys.path.insert(0,str(P))
from build_engine import sha

def collect():
 from screen_jobs import jobs,verify,choose,output,WRAPPER
 from compare import load,compare
 boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 result=dict(packet=91,status='pending',lanes={},receipts={},sources={},boot_id=boot)
 def rows(lane,entries):
  found=[]
  for j in entries:
   path=output(j) if j['mode']=='grid' else WRAPPER/'evidence'/f'p91-{lane}-confirm-{j["index"]}'
   for f in path.rglob('*.json'):
    if f.is_file() and not f.is_symlink():result['receipts'][str(f.relative_to(ROOT))]=sha(f)
   r=load(j)
   if r['boot_id']!=boot:raise ValueError('stale screen boot')
   found.append(r)
  return found
 try:
  pin=verify();result['sources']=pin['sources']
  a=rows('A',jobs('A'));compare(a);result['lanes']['A']=a
  try:best=choose(a)
  except ValueError:
   if all(r['rate']<=max(a[0]['rate'],a[-1]['rate']) for r in a[1:-1]):result['status']='no-winner';return result
   raise
  result['best']=dict(best,ratio=best['rate']/max(a[0]['rate'],a[-1]['rate']))
  # Prefer exact A-winner confirmation; a complete full B grid is also valid.
  errors=[];invalid=[];b=None
  for mode in ('confirm','grid'):
   try:
    candidate=rows('B',jobs('B',best['choice'],mode));compare(candidate,tuple(j['choice'] for j in jobs('B',best['choice'],mode)));b=candidate;break
   except FileNotFoundError as e:errors.append(str(e))
   except (OSError,ValueError,AssertionError,KeyError,TypeError) as e:errors.append(str(e));invalid.append(str(e))
  if b is None and invalid:raise ValueError('invalid B evidence: '+'; '.join(invalid))
  if b is None:raise FileNotFoundError('B confirmation/grid pending: '+'; '.join(errors))
  result['lanes']['B']=b
  selected=next(r for r in b[1:-1] if r['choice']==best['choice'])
  result['confirmation']=dict(selected,ratio=selected['rate']/max(b[0]['rate'],b[-1]['rate']))
  result['status']='winner' if result['confirmation']['ratio']>1 else 'no-winner'
 except FileNotFoundError as e:result['error']=str(e)
 except (OSError,ValueError,AssertionError,KeyError,TypeError) as e:result.update(status='failed',error=str(e))
 return result
if __name__=='__main__':
 with contextlib.redirect_stdout(io.StringIO()):result=collect()
 print(json.dumps(result))
