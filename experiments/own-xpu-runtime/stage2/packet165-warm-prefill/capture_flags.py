"""Capture real launch argv without exec; verify every flag against built help."""
import importlib.util,json,os,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch
from build_engine import P,ROOT,sha,save,limits
limits();name=sys.argv[1];p=P/name;sys.path.insert(0,str(p))
import worker,native_env
commands=[]
with tempfile.TemporaryDirectory(prefix='p165-flags-') as td:
    scratch=Path(td)
    if name=='one-card':
        table=scratch/'suite-inputs.tsv'
        table.write_text(''.join(e['prompt_id']+' '+str(p/'inputs'/e['prompt_id']/'tokens.txt')+'\n' for e in worker.entries()))
        commands=[worker.native_command(scratch,table)]
    else:
        import pipeline
        class Stop(Exception):pass
        class Child:
            pid=os.getpid()
            def poll(self):return 0
        def fake(argv,**kw):commands.append(argv[3:] if argv[:3]==['ionice','-c','3'] else argv);return Child()
        args=pipeline.parser().parse_args(['--output',str(scratch),'--device','--binary',str(p/'build/device/own-rt-iq3'),
            '--dispatch',str(p/'dispatch.json'),'--controller','native','--draft','mtp','--draft-rank','1','--target-split','0',
            '--context','4096','--tokens','512','--retain-steps','none','--timing','token','--native-nice','0','--card','0',
            '--seconds','7200','--wait-seconds','1200'])
        args.selection_sha256=sha(p/'selection.json');args.input=p/'inputs';pipeline.P=p
        out=scratch/'capture';out.mkdir();t=pipeline.Transport.__new__(pipeline.Transport)
        with patch.object(pipeline.subprocess,'Popen',side_effect=fake),patch.object(pipeline.Transport,'receive',side_effect=Stop):
            try:pipeline.Transport.__init__(t,args,out,native_env.environment('A'))
            except Stop:pass
        for f in t.logs:f.close()
        for s in t.sockets:s.close()
        t.mapping.close();os.close(t.stop_read);os.close(t.stop_write)
        assert len(commands)==2
    env=native_env.environment('A')
    cp=subprocess.run([str(p/'build/device/own-rt-iq3'),'--help'],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
    probes=[]
    for command in commands:
        flags=[s for s in command[1:] if s.startswith('--')]
        assert set(flags)<=set(cp.stdout.split()),set(flags)-set(cp.stdout.split())
        probes.append(dict(real_native_argv=command,flags=flags,all_flags_in_built_help=True))
    parent=read=json.loads((p/'evidence/parent-preparation-probe.json').read_text())
    assert parent['passed'] and sha(p/'build/device/own-rt-iq3')==json.loads((p/'inherited-native.json').read_text())['binary_sha256']
    save(p/'evidence/preparation-probe.json',dict(passed=True,device_executed=False,model_reads=False,
        environment=env,probes=probes,native_help=cp.stdout,
        scope='fresh relocated binary argv capture and pre-device help; unchanged kernel objects/arithmetic, parent preparation retained as provenance; new full reset-sequence gate separate',
        inherited_preparation_sha256=sha(p/'evidence/parent-preparation-probe.json')))
print(name,'captured native flags PASS')
