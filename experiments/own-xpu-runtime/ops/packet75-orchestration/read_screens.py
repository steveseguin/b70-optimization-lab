"""Isolated imports of each frozen packet's original compare and best logic."""
import contextlib,hashlib,io,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def collect(packet):
    suffix={73:'hc-experts2',74:'packed-dense'}[packet]
    screen=ROOT/f'experiments/own-xpu-runtime/stage2/packet{packet}-{suffix}/screen'
    sys.path.insert(0,str(screen))
    import compare as c
    import winner
    c.cpu_gate();c.verify()
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    result=dict(packet=packet,boot_id=boot,status='pending',lanes={},receipts={},sources={str(f.relative_to(ROOT)):sha(f) for f in screen.glob('*.py')})
    def load(lane,path):
        rows=[]
        for job in c.jobs(path,lane):
            r=c.load(job,lane);out=c.HERE/'evidence'/job['out']
            c.require(c.read(out/'window.json')['boot_id']==boot,'stale screen boot')
            r['exact_count']=13 if r['exact'] else 0;rows.append(r)
            for f in out.rglob('*'):
                if f.is_file() and not f.is_symlink() and f.suffix in ('.json','.jsonl'):
                    result['receipts'][str(f.relative_to(ROOT))]=sha(f)
        result['lanes'][lane]=rows
        return rows
    try:
        a=load('A',screen/'jobs-A.txt')
        # The packet's own best rule is authoritative (p73 mean, p74 both controls).
        try:best=winner.choose(a)
        except ValueError:
            if all(r['exact_count']==13 for r in a):
                result['status']='no-winner';return result
            raise
        result['best']=best
        b=load('B',screen/(f"jobs-B-{best['choice']}.txt" if packet==74 else 'jobs-B.txt'))
        c.require(len(b)==3 and [r['choice'] for r in b]==['production',best['choice'],'production'],'B confirmation differs from A best')
        c.require(all(r['exact_count']==13 for r in b),'B exactness failed')
        control=max(b[0]['rate'],b[2]['rate']) if packet==74 else c.baseline(b)
        result['status']='winner' if b[1]['rate']>control else 'no-winner'
        result['confirmation']=dict(choice=best['choice'],control=control,rate=b[1]['rate'],ratio=b[1]['rate']/control)
    except (OSError,ValueError,KeyError,TypeError) as error:result['error']=str(error)
    return result
if __name__=='__main__':
    with contextlib.redirect_stdout(io.StringIO()):result=collect(int(sys.argv[1]))
    print(json.dumps(result))
