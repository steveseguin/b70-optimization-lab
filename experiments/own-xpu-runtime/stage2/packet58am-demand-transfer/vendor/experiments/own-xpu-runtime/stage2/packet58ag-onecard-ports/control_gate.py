"""Compare frozen record CPU miniature with the new production control."""
import json,resource,subprocess,tempfile
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits
from launch_env import environment

def main():
    limits();parent=P.parent/'packet58z-onecard-record/build/gnu-host/own-rt-iq3'
    current=P/'build/gnu-host/own-rt-iq3';rows=[];reference=None
    with tempfile.TemporaryDirectory(prefix='p58ag-control-',dir=P/'build') as directory:
        for name,binary in [('record',parent),('production',current)]:
            output=Path(directory)/name
            cmd=[str(binary),'--mini','--pipeline-mini','--memory','resident','--context','32','--tokens','8',
                 '--retain-steps','1-8','--cache-maintenance','overlap','--output',str(output)]
            cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,env=environment(),timeout=180)
            assert cp.returncode==0,cp.stderr[-2000:]
            result=json.loads((output/'result.json').read_text())
            state=dict(tokens=result['tokens'],files={str(f.relative_to(output)):sha(f) for f in sorted(output.glob('step*/*')) if f.is_file()})
            assert len(state['tokens'])==8 and state['files']
            if reference is None:reference=state
            else:assert state==reference,'production changed from frozen record CPU path'
            rows.append(dict(name=name,binary=str(binary.relative_to(ROOT)),binary_sha256=sha(binary),fixture_files=len(state['files']),tokens=8))
    save(P/'evidence/control-gate.json',dict(passed=True,device_executed=False,synthetic_only=True,records=rows,
        production_matches_record=True,source_full_model_device_parity_pending=True))
    print('Frozen record and new production miniature: eight tokens and every retained state file MATCH')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
