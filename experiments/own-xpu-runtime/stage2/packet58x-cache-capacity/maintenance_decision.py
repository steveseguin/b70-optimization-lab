"""Read the frozen parent's completed bracket; never run a device or edit it."""
import hashlib,json,resource,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent
PARENT=P.parent/'packet58v-async-cache'


def main():
    window=PARENT/'evidence/card0-async-a/overlap/WSCREEN/window.json'
    row=dict(passed=True,device_executed=False,default='serial',parent_bracket_complete=False,
             reason='No completed exact faster parent bracket at decision time.',sources={})
    if window.exists():
        receipt=json.loads(window.read_text())
        if receipt.get('passed') and not receipt.get('child_still_running') and not receipt.get('stop_reasons'):
            # Separate interpreter prevents imported packet58x modules substituting
            # for the frozen parent's own views, oracle checker or comparison.
            code=("import json,suite_driver as D; from pathlib import Path; "
                  "print(json.dumps(D.summarize_bracket(Path("+repr(str(window.parent/'run'))+
                  "),'overlap',D.oracle_inputs())))")
            result=subprocess.run([sys.executable,'-B','-c',code],cwd=PARENT,stdin=subprocess.DEVNULL,
                                  capture_output=True,text=True,check=True,timeout=120)
            decision=json.loads(result.stdout)
            row.update(parent_bracket_complete=True,decision={k:decision[k] for k in
                ('rates','control_drift_fraction','candidate_beats_all_controls','minimum_gain_vs_best_control')})
            row['default']='overlap' if decision['candidate_beats_all_controls'] else 'serial'
            row['reason']='Rechecked all parent oracle outputs, boundaries, clean teardown and five-view speed gate.'
            for source in (window,window.parent/'summary.json',PARENT/'build-receipt.json'):
                row['sources'][str(source.relative_to(P.parents[3]))]=hashlib.sha256(source.read_bytes()).hexdigest()
    (P/'maintenance-decision.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps(row))


if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
