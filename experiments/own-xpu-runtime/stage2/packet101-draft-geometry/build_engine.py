"""Reuse packet97's unchanged compiled selection paths, bound to copied sources."""
import hashlib,json,os,resource
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build'
BASE=P.parent/'packet97-record-bundle'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,value):Path(p).write_text(json.dumps(value,indent=2)+'\n')
def limits():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
def check_map(root,rows):
    for n,h in rows.items():assert sha(root/n)==h,n
def provenance():
    row=json.loads((P/'build-device-receipt.json').read_text())
    check_map(ROOT,row['sources']);check_map(P,row['artifacts']);return row
def main():
    limits();prior=json.loads((BASE/'build-device-receipt.json').read_text())
    check_map(ROOT,prior['sources']);check_map(BASE,prior['artifacts'])
    copies=json.loads((P/'copy-lineage.json').read_text());sources=dict(prior['sources'])
    for dest,row in copies.items():
        # Python preparation tools may evolve; all runtime source stays identical.
        if Path(dest).suffix not in ('.hpp','.cpp','.inc'):continue
        assert sha(ROOT/dest)==sha(ROOT/row['source'])==row['sha256'],dest
        sources[dest]=row['sha256'];sources[row['source']]=row['sha256']
    sources[str((BASE/'build-device-receipt.json').relative_to(ROOT))]=sha(BASE/'build-device-receipt.json')
    artifacts={}
    for mode in ('gnu-host','device'):
        dest=B/mode/'own-rt-iq3';dest.parent.mkdir(exist_ok=True)
        if not dest.exists():os.link(BASE/'build'/mode/'own-rt-iq3',dest)
        artifacts[str(dest.relative_to(P))]=sha(dest)
        assert artifacts[str(dest.relative_to(P))]==prior['artifacts']['build/'+mode+'/own-rt-iq3']
    rope=B/'fusion-rope.hpp'
    if not rope.exists():rope.write_bytes((BASE/'build/fusion-rope.hpp').read_bytes())
    assert sha(rope)==sha(BASE/'build/fusion-rope.hpp')
    sources[str(rope.relative_to(ROOT))]=sha(rope)
    from kernel_gate import mirror
    mirror() # CPU fixture mirror only; no runtime rebuild or device execution.
    save(P/'build-device-receipt.json',dict(passed=True,device_executed=False,
         schema='packet101.unchanged-binary.v1',sources=sources,artifacts=artifacts,
         reason='Both draft choices already compiled in packet97; runtime sources copied byte-for-byte.'))
if __name__=='__main__':main()
