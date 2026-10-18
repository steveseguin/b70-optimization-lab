"""CPU preparation checks only. Does not enqueue, launch or submit."""
import ast,hashlib,json,os,resource,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parents[4]
P=R/'experiments/own-xpu-runtime/stage2/packet58ah-onecard-record'
O=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text())
def save(p,row):p.write_text(json.dumps(row,indent=2)+'\n')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(script,*args,log,allow_pending=False):
    proc=subprocess.run([sys.executable,'-B',str(script),*map(str,args)],cwd=R,
        stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=300)
    log.write_text(proc.stdout+proc.stderr)
    assert proc.returncode==0 or allow_pending,(str(script),proc.stderr[-3000:])
    return proc
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    assert not (O/'READY-FOR-DEVICE.json').exists(),'final marker already written'
    assert not (P/'evidence/card0-58ah-a').exists()
    for root in (P,O):
        for path in root.rglob('*.py'):ast.parse(path.read_text(),filename=str(path))
    binding=read(P/'parent-binding.json')
    for n,h in binding['sources'].items():assert sha(R/n)==h
    run(P/'run_cpu_gates.py',log=O/'cpu-gates.log')
    run(P/'argument_gate.py',log=O/'arguments.log')
    run(P/'native_parser_gate.py',log=O/'native-parser.log')
    run(P/'rehearse_submission.py',log=O/'submission-rehearsal.log')
    sys.path.insert(0,str(P))
    import verify_ready
    command=verify_ready.command_argv()
    argv=command[command.index('/usr/bin/python3'):]
    argv[argv.index('--fault-review')+1]='{REVIEW}'
    binaries=[]
    for name in ('build/device/own-rt-iq3','build/device/p58-cache-fixtures'):
        row=dict(path=str((P/name).relative_to(R)),sha256=binding['native_artifacts'][name])
        if name.endswith('p58-cache-fixtures'):row.update(args=['--help'],returncode=1,contains='K1 unknown option')
        binaries.append(row)
    proposal=dict(name='packet58ah-chain-entry',lane='A',argv=argv,review=str(P/'fault_review.py'),
        plan=dict(entry_rehearsal=dict(binaries=binaries),rehearsal_only=True,actual_unit='packet58-onecard-58ah-a'))
    (O/'entry-proposal.jsonl').write_text(json.dumps(proposal)+'\n')
    proc=run(R/'experiments/own-xpu-runtime/ops/rehearse_entry.py',O/'entry-proposal.jsonl','--json',log=O/'entry-rehearsal.log')
    entry=json.loads(proc.stdout);assert entry['passed']
    save(O/'entry-rehearsal.json',entry)
    save(P/'evidence/native-entry.json',dict(passed=True,device_executed=False,entry=entry,
        proposal_sha256=sha(O/'entry-proposal.jsonl')))
    run(P/'seal.py',log=O/'seal.log')
    run(P/'seal.py','--verify',log=O/'seal-verify.log')
    run(P/'plan_gate.py',log=O/'plan.log')
    run(P/'verify_ready.py','--output',P/'ready.json',log=O/'readiness.log',allow_pending=True)
    ready=read(P/'ready.json')
    # A missing bracket is an expected pending device gate; never label it passed.
    sys.path.insert(0,str(R/'experiments/own-xpu-runtime/ops/lane-queue'))
    import pin_guard
    guard=pin_guard.check_job(proposal);save(O/'pin-guard.json',guard);assert guard['passed'],guard
    run(P/'submission_cli.py','--help',log=O/'submission-cli-help.log')
    tests=read(P/'evidence/python-cpu-gates.json');args=read(P/'evidence/argument-gate.json')
    rehearsal=read(P/'evidence/submission-rehearsal.json')
    assert len(args['records'])==7 and len(args['negative_records'])==28
    assert rehearsal['final_location_cli_passed'] and not rehearsal['cli_root_overridden']
    assert rehearsal['notes_characters']<=2000
    save(O/'validation.json',dict(passed=True,device_executed=False,python_tests=tests['tests'],
        entry_windows=7,wrong_unit_environment_refusals=28,submission_cli_final_location_passed=True,
        submission_notes_characters=rehearsal['notes_characters'],runtime_readiness_passed=ready['ready'],
        runtime_readiness_reason=ready.get('reason'),parent_bound=True,pin_guard_passed=True,
        no_model_reads=True,no_fullshape_reads=True,no_rebuild=True,launch_performed=False,
        services_started=False,live_queue_changed=False,submission_performed=False))
    print('CPU preparation passed; runtime smoke/bracket gate:',ready['ready'])
if __name__=='__main__':
    # Intercepted entry tests intentionally check unlimited runtime AS. They
    # allocate only small fixtures and independently record/assert <4 GiB RSS.
    main()
