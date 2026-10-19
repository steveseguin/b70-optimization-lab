"""Two proposals only; temporary queue planning never touches live queues."""
import json,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits
Q=P/'screen';OPS=P.parents[1]/'ops';QUEUE=OPS/'lane-queue'
# Measured packet58as v5 bracket output (du -sb screen/evidence/card0-58as-v5-a, 2026-10-19).
PARENT_V5_OUTPUT_BYTES=40170623
def documents():
    from launch_env import library_path
    lib=library_path()
    sizes=json.loads((P/'payload-sizes.json').read_text())['records']
    for tag,arm in [('v5','resident')]:
        job=dict(name='packet176-'+tag+'-A',lane='A',argv=[
            '/usr/bin/python3','-B',str((Q/'queue_runner.py').relative_to(ROOT)),
            '--arm',arm,'--output',str(Q/'evidence/card0-176-v5-a'/arm),
            '--cache-maintenance','overlap','--fault-review','{REVIEW}',
            '--library-path',lib,'--authorized-device-window'],
            review=str((Q/'fault_review.py').relative_to(ROOT)),env_extra={},
            planned_write_bytes=2*PARENT_V5_OUTPUT_BYTES)
        job['plan']=dict(entry_rehearsal=dict(preparation_probe_note='Local device-define CPU preparation receipt: packet176-onecard-kernelio/evidence/preparation.json. Shared prepare_probe cannot admit this unranked one-card argv and private 4 MiB RoPE; keep its WARN explicit.',timing_evidence=[str((P.parent/'packet58as-onecard-spinwait/screen/evidence/card0-58as-v5-a/resident/WSCREEN/run/run/cold-start.json').relative_to(ROOT))],binaries=[
            dict(path=str((P/'build/device/own-rt-iq3').relative_to(ROOT)),sha256=sha(P/'build/device/own-rt-iq3')),
            dict(path=str((P/'build/device/p58-cache-fixtures').relative_to(ROOT)),sha256=sha(P/'build/device/p58-cache-fixtures'),args=['--help'],returncode=0,contains='--output')]))
        raw=('# PROPOSAL ONLY. packet176: one-card copy-engine-free foreground token I/O (compute-kernel tail store + head load).\n'
             '# Lane A, card 0, whole host; paused/drained lane B. No queue write or launch here.\n'
             '# Parent = packet58as spin line (git archive of HEAD). B: one CCS kernel stores error/next_token/stamp/route rows to pinned USM host\n'
             '# memory after the last launch, one CCS kernel loads the staged token/lookup rows; no copy command on any queue for them.\n'
             '# Fills, publication, kernels, arithmetic, selection, cache policy, spin and backend unchanged. Process-wide --foreground-io copy|kernel.\n'
             '# Full 58ah composition; resident allocation throughout; full BF16 KV; 21.55 GB device cache.\n'
             '# No separate smoke: K1a/K1b and exact A0 open this one-load bracket.\n'
             '# V5: spin/spin-kio/spin/spin-kio/spin; A0 exact warm-up. Both B >= +0.5% over every warm A, drift <=3%, 60/60 exact vs iq3-p49-split32-v1.\n'
             '# Mechanism readout (slow fraction, head/tail split and engine per arm, ms per same-token fill MB, wall slope) kept on every outcome.\n'
             '# Production admission 98,990,252,032 bytes including 8 GiB reserve. No settings changes.\n'
             '# Declared writes are twice the measured packet58as v5 output; retain 25 GB root free after reserved writes.\n'+json.dumps(job)+'\n')
        yield tag,job,raw
def main():
    limits();records=[]
    for tag,job,raw in documents():
        name='proposed-p176-'+tag+'-A.txt';local=Q/'proposals'/name;external=QUEUE/name
        if '--emit-only' in sys.argv:
            local.parent.mkdir(exist_ok=True);local.write_text(raw);external.write_text(raw);continue
        assert local.read_text()==external.read_text()==raw
        with tempfile.TemporaryDirectory(prefix='p58aj-plan-') as tmp:
            (Path(tmp)/'queue-A.txt').write_text(raw)
            cp=subprocess.run([sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane','A','--directory',tmp],
                stdin=subprocess.DEVNULL,capture_output=True,text=True,cwd=ROOT)
        log=P/'evidence'/('queue-plan-'+tag+'.log');log.write_text(cp.stdout+cp.stderr)
        assert cp.returncode==0,log.read_text()[-4000:]
        rows=[json.loads(line) for line in cp.stdout.splitlines()];assert len(rows)==1 and rows[0]['plan']=='passed'
        records.append(dict(proposal=str(external.relative_to(ROOT)),proposal_sha256=sha(external),plan=rows))
    if '--emit-only' not in sys.argv:save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,temporary_queue=True,queued=False,records=records))
if __name__=='__main__':main()
