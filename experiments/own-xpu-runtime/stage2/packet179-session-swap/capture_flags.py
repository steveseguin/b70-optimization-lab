"""Capture real launch argv without exec; verify every flag against built help."""
import importlib.util,json,os,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch
from build_engine import P,ROOT,sha,save,limits
limits();name=sys.argv[1];p=P/name;sys.path.insert(0,str(p))
import worker,native_env
commands=[]
with tempfile.TemporaryDirectory(prefix='p179-flags-') as td:
    scratch=Path(td)
    assert name=='one-card'
    table=scratch/'suite-inputs.tsv'
    table.write_text(''.join(e['prompt_id']+' '+str(p/'inputs'/e['prompt_id']/'tokens.txt')+'\n' for e in worker.entries()))
    commands=[worker.native_command(scratch,table)]
    # The packet165c whole-host ionice idle prefix is retained unchanged.
    assert commands[0][:2]==['/usr/bin/ionice','-c3'],commands[0][:2]
    # Additionally probe the checkpoint save/restore argv (single-request mode).
    commands.append(worker.checkpoint_command(scratch/'save',worker.CHECKPOINT_K,'--checkpoint-save',scratch/'ck'))
    commands.append(worker.checkpoint_command(scratch/'restore',worker.CHECKPOINT_M,'--checkpoint-restore',scratch/'ck'))
    assert commands[1][:2]==['/usr/bin/ionice','-c3'] and '--suite-inputs' not in commands[1]
    env=native_env.environment('A')
    # First-ever execution of the rebuilt binary: this sanctioned host-side --help.
    cp=subprocess.run([str(p/'build/device/own-rt-iq3'),'--help'],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
    probes=[]
    for command in commands:
        flags=[s for s in command[1:] if s.startswith('--')]
        assert set(flags)<=set(cp.stdout.split()),set(flags)-set(cp.stdout.split())
        probes.append(dict(real_native_argv=command,flags=flags,all_flags_in_built_help=True))
    parent=json.loads((p/'evidence/parent-preparation-probe.json').read_text())
    assert parent['passed'] and sha(p/'build/device/own-rt-iq3')==json.loads((p/'inherited-native.json').read_text())['binary_sha256']
    save(p/'evidence/preparation-probe.json',dict(passed=True,device_executed=False,model_reads=False,
        environment=env,probes=probes,native_help=cp.stdout,
        scope='fresh relinked binary argv capture and pre-device help; first-ever execution of the rebuilt binary is this host-side --help; kernel objects byte-identical to packet165; checkpoint argv probed; arithmetic/performance unqualified until the device run; parent preparation retained as provenance; new full reset-sequence gate separate',
        inherited_preparation_sha256=sha(p/'evidence/parent-preparation-probe.json')))
print(name,'captured native flags PASS')
