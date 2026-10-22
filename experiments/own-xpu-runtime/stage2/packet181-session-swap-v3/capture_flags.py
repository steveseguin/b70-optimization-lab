"""Capture real launch argv without exec at production shape; verify every flag against built help.

Builds the actual row-a suite argv and all five row-b lifecycle legs exactly as worker.py
will (real prompt file, NEW = P + packet179 row-a gen[0:256] + T at 469 tokens, real
tokenizer-identity.tsv, real checkpoint ids), plus the device-free host-tool argv, and checks
each flag against the rebuilt binary's --help. The only execution of the rebuilt binary is
this sanctioned host-side --help (it exits in parse() before any device or model access).
"""
import json,re,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits
limits();name=sys.argv[1];p=P/name;sys.path.insert(0,str(p))
import worker,native_env,measurement
ID=re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z')
def tokenizer_identity(path):
    """Python mirror of checkpoint.hpp checkpoint_tokenizer_identity (format + three 64-hex pins)."""
    values={}
    for line in path.read_text().splitlines():
        if not line or line.startswith('#'):continue
        key,value=line.split('\t');assert key not in values;values[key]=value
    assert values['format']=='ownrt.tokenizer-identity.v1'
    for key in ('gguf_header_sha256','tokenizer_source_sha256','vocab_bin_sha256'):assert re.fullmatch(r'[0-9a-f]{64}',values[key]),key
    return values
with tempfile.TemporaryDirectory(prefix='p181-flags-') as td:
    scratch=Path(td)
    assert name=='one-card'
    table=scratch/'suite-inputs.tsv'
    table.write_text(''.join(e['prompt_id']+' '+str(p/'inputs'/e['prompt_id']/'tokens.txt')+'\n' for e in worker.entries()))
    commands=[('full512',worker.native_command(scratch,table))]
    assert commands[0][1][:2]==['/usr/bin/ionice','-c3'],commands[0][1][:2]
    L=worker.LIFECYCLE
    prompt_path=p/'inputs'/L['prompt_id']/'tokens.txt';prompt=list(map(int,prompt_path.read_text().split()))
    gen=json.loads((p/'reference-p179-row-a.json').read_text())['prompts'][L['prompt_id']]['tokens'][:L['K']]
    turn=measurement.lifecycle_turn(L,p)
    new=measurement.lifecycle_input(prompt,gen,turn,L);new_path=scratch/'new.txt';new_path.write_text(' '.join(map(str,new))+'\n')
    root=scratch/'checkpoints'
    identity=tokenizer_identity(p/'tokenizer-identity.tsv')
    shape=[]
    for spec in worker.lifecycle_legs(root,prompt_path,new_path):
        cmd=worker.native_single_command(scratch/spec['leg'],spec['input'],spec['max_new'],spec['args'])
        assert cmd[:2]==['/usr/bin/ionice','-c3'] and cmd[2]==str(p/'build/device/own-rt-iq3')
        assert '--suite-inputs' not in cmd and cmd.count('--input')==1 and cmd[cmd.index('--retain-steps')+1]=='none'
        assert cmd[cmd.index('--context')+1]=='4096' and cmd[cmd.index('--max-new')+1]==str(spec['max_new'])
        has_ckpt=any(f in cmd for f in ('--checkpoint-save','--checkpoint-restore'))
        assert ('--tokenizer-identity' in cmd)==has_ckpt
        if has_ckpt:
            assert cmd[cmd.index('--tokenizer-identity')+1]==str(p/'tokenizer-identity.tsv')
            assert ID.match(cmd[cmd.index('--checkpoint-id')+1])
        if '--checkpoint-save-id' in cmd:
            assert ID.match(cmd[cmd.index('--checkpoint-save-id')+1]) and '--checkpoint-restore' in cmd and '--checkpoint-save' in cmd
            assert cmd[cmd.index('--checkpoint-save-id')+1]!=cmd[cmd.index('--checkpoint-id')+1]
        tokens=list(map(int,Path(cmd[cmd.index('--input')+1]).read_text().split()))
        assert len(tokens)+spec['max_new']<=4096
        commands.append((spec['leg'],cmd));shape.append(dict(leg=spec['leg'],input_tokens=len(tokens),max_new=spec['max_new'],
            operation=spec['operation'],checkpoint_flags=[a for a in cmd if a.startswith('--checkpoint') or a=='--tokenizer-identity']))
    assert [s['input_tokens'] for s in shape]==[87,469,469,469,469] and len(new)==469
    host_tools=[[str(p/'build/device/own-rt-iq3'),flag,str(root/'s1')] for flag in ('--checkpoint-inspect-metadata','--checkpoint-inspect','--checkpoint-delete')]
    env=native_env.environment('A')
    cp=subprocess.run([str(p/'build/device/own-rt-iq3'),'--help'],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
    help_flags=set(cp.stdout.split())
    probes=[]
    for label,command in commands:
        flags=[s for s in command[1:] if s.startswith('--')]
        assert set(flags)<=help_flags,set(flags)-help_flags
        probes.append(dict(label=label,real_native_argv=command,flags=flags,all_flags_in_built_help=True))
    for command in host_tools:
        assert command[1] in help_flags
        probes.append(dict(label='host-tool '+command[1],real_native_argv=command,flags=[command[1]],all_flags_in_built_help=True,device_free=True))
    assert json.loads((p/'native-help-flags.json').read_text())==[f for f in cp.stdout.split() if f.startswith('--')],'native-help-flags.json != built help'
    parent=json.loads((p/'evidence/parent-preparation-probe.json').read_text())
    assert parent['passed'] and sha(p/'build/device/own-rt-iq3')==json.loads((p/'inherited-native.json').read_text())['binary_sha256']
    save(p/'evidence/preparation-probe.json',dict(passed=True,device_executed=False,model_reads=False,
        environment=env,probes=probes,native_help=cp.stdout,lifecycle_shape=shape,tokenizer_identity_keys=sorted(identity),
        scope='fresh relinked binary argv capture at production shape and pre-device help; the only execution of the rebuilt binary is this host-side --help; kernel objects byte-identical to packet165; lifecycle legs and host tools probed; arithmetic/performance unqualified until the device run'))
print(name,'captured native flags PASS',len(commands),'native argv +',len(host_tools),'host tools')
