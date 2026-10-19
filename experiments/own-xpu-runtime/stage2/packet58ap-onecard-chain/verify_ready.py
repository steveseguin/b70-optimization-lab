#!/usr/bin/env python3
"""Re-read the proposed v5 output at launch; saved booleans cannot release it."""
import argparse,hashlib,json,math,shlex
from decimal import Decimal
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
PROPOSAL=ROOT/'experiments/own-xpu-runtime/ops/lane-queue/proposed-p58am-v5-A.txt'
METRIC='class_balanced_tok_s_1_100_intervals_after_ttft'
RELEASE='packet58am v5: each candidate >=+0.5% over EVERY warm control; all 60 requests exact; warm-control drift <=3%; A0 is warm-up only for speed/drift; binary must match vendored build'
def require(ok,why):
    if not ok:raise ValueError(why)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def evaluate(rows):
    require([r['label'] for r in rows]==['A0','B0','A1','B1','A2'],'complete five-view bracket required')
    signatures=[];rates=[]
    for i,row in enumerate(rows):
        require(row.get('view')==('demand' if i%2 else 'parent'),'parent/demand order differs')
        requests=row['requests'];require(row.get('passed') is True and len(requests)==12,'complete exact suite required')
        require(len({r['prompt_id'] for r in requests})==12,'duplicate prompt')
        for r in requests:
            require(r.get('passed') is True and r.get('exact_oracle') is True and r.get('cached_tokens')==0 and len(r['tokens'])==128,'all views must be exact and uncached')
        signatures.append([(r['prompt_id'],r['prompt_token_sha256'],r['tokens']) for r in requests])
        v=row[METRIC]['median'];require(type(v) in (int,float) and math.isfinite(v) and v>0,'invalid rate');rates.append(Decimal(str(v)))
    require(all(s==signatures[0] for s in signatures),'prompt/token identity differs')
    controls=rates[2::2];candidates=rates[1::2];drift=max(controls)/min(controls)-1
    require(all(c>=a*Decimal('1.005') for a in controls for c in candidates),'candidate must gain >=0.5% over EVERY warm control')
    require(drift<=Decimal('.03'),'warm-control drift >3%')
    return dict(passed=True,rates=list(map(float,rates)),minimum_gain=float(min(candidates)/max(controls)-1),control_drift_fraction=float(drift),candidate_beats_all_controls=True,comparison_controls=['A1','A2'],warmup_view=dict(label='A0',exact=True,excluded_from_drift_and_comparison=True),submission_eligible=False)
def chain_unit():return 'packet58-onecard-'+P.name.split('-')[0].removeprefix('packet')+'-a'
def command_argv():
    from launch_env import library_path
    return ['systemd-run','--user','--unit='+chain_unit(),'--property=Restart=no','--property=SendSIGKILL=no','--property=TimeoutStopSec=infinity','--property=Nice=0','--working-directory='+str(ROOT),'/usr/bin/taskset','-c','0-3,16-19','/usr/bin/env','-i','PATH=/usr/bin:/bin','LD_LIBRARY_PATH='+library_path(),'OMP_NUM_THREADS=2','/usr/bin/python3','-B',str(P/'queue_runner.py'),'--authorized-device-window','--card','0','--view','down-tile16','--output-root',str(P/'evidence/card0-58ap-a'),'--fault-review',str(P/'evidence/fault-review-58ap-a.json')]
def chain_command():return shlex.join(command_argv())+' < /dev/null'
def parent_evidence():
    lines=[json.loads(s) for s in PROPOSAL.read_text().splitlines() if s.strip() and not s.lstrip().startswith('#')]
    require(len(lines)==1,'one v5 proposal required');proposal=lines[0];argv=proposal['argv']
    require(argv[argv.index('--arm')+1]=='v5','proposal is not v5')
    output=(ROOT/Path(argv[argv.index('--output')+1])).resolve()
    require(output.is_relative_to(P.parent/'packet58am-demand-transfer/screen/evidence'),'v5 output outside parent evidence')
    q=read(output/'queue.json');require(q['passed'] is True and q['completed']==['K1a','K1b','WSCREEN'] and q.get('running') is None,'v5 chain incomplete')
    window=read(output/'WSCREEN/window.json');require(window['passed'] is True and window['device_executed'] is True and window['child_still_running'] is False and window['stop_reasons']==[],'v5 window incomplete')
    require({'run/summary.json','run/receipt.json','run/run/receipt.json'}<=set(window['native_files']),'v5 native closure missing')
    binding=read(P/'parent-binding.json');binary=binding['artifacts']['build/device/own-rt-iq3']
    require(binary in window['artifacts_sha256'].values(),'v5 was not run with the vendored candidate')
    sources={str(PROPOSAL.relative_to(ROOT)):sha(PROPOSAL),str((output/'queue.json').relative_to(ROOT)):sha(output/'queue.json'),str((output/'WSCREEN/window.json').relative_to(ROOT)):sha(output/'WSCREEN/window.json')}
    for name,digest in window['native_files'].items():
        path=(output/'WSCREEN'/name).resolve();require(path.is_relative_to(output/'WSCREEN'),'unsafe v5 member')
        require(sha(path)==digest,'v5 evidence changed: '+name);sources[str(path.relative_to(ROOT))]=digest
    summary=read(output/'WSCREEN/run/summary.json')
    require(summary.get('passed') is True and summary.get('model_lifetimes')==1 and summary.get('kv_dtype')=='BF16' and summary.get('prompt_kv_response_reuse') is False,'v5 scope differs')
    driver=read(output/'WSCREEN/run/receipt.json');command=driver['command']
    for flag,value in (('--lookups','resident'),('--demand','bcs-demand-retained32x2')):
        require(command.count(flag)==1 and command[command.index(flag)+1]==value,'v5 composition differs: '+flag)
    import suite_driver as D
    manifest=D.oracle_inputs()
    for view in summary['views']:
        for entry in manifest['prompts']:
            for leaf in ('result.json','reset.json'):
                require('run/run/'+view['label']+'/'+entry['prompt_id']+'/'+leaf in window['native_files'],'v5 request closure missing')
        rebuilt=[D.compare_request(output/'WSCREEN/run/run'/view['label']/entry['prompt_id'],D.ORACLE/'results'/entry['prompt_id'],entry,128,'none') for entry in manifest['prompts']]
        require(view['requests']==rebuilt,'v5 raw exact requests differ')
        require(view[METRIC]==D.METRICS.aggregate(rebuilt)[METRIC],'v5 rate differs from timestamps')
    return dict(evaluate(summary['views']),boot_id=window['boot_id'],v5_output=str(output),v5_summary_sha256=sha(output/'WSCREEN/run/summary.json'),screen_sources=sources,parent_binary_sha256=binary,release_condition=RELEASE)
def verify():
    import window as W
    seal=W.build_gate()
    require(seal.get('demand')=='bcs-demand-retained32x2' and seal.get('lookups')=='resident','candidate composition differs')
    pins=read(P/'submission-pins.json');require(pins['build_receipt_sha256']==sha(P/'build-receipt.json'),'stale submission pins');W.verify_files(ROOT,pins['sources'])
    require(not (P/'evidence/card0-58ap-a').exists(),'fresh output required; no retry')
    return dict(parent_evidence(),build_receipt_sha256=sha(P/'build-receipt.json'),submission_pins_sha256=sha(P/'submission-pins.json'))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path);args=ap.parse_args()
    row=dict(schema='packet58ap.ready.v1',passed=False,ready=False,device_executed=False,chain_command=chain_command(),release_condition=RELEASE)
    try:row.update(verify(),ready=True)
    except (ValueError,OSError,KeyError,TypeError,AssertionError) as error:row['reason']=str(error)
    if args.output:
        require(args.output.resolve()==P/'ready.json','only local ready.json may be written');args.output.write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps(row,indent=2));return 0 if row['ready'] else 1
if __name__=='__main__':raise SystemExit(main())
