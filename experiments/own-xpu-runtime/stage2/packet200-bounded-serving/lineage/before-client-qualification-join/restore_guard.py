#!/usr/bin/env python3
"""One pinned p196 restore, with p200 manifest and per-operation incident guards."""
import importlib.util
import json
from pathlib import Path
import runpy
import subprocess
import sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('_p200_restore_driver',HERE/'driver.py')
D=importlib.util.module_from_spec(spec);sys.modules[spec.name]=D;spec.loader.exec_module(D)
VALIDATIONS=[['--base','http://127.0.0.1:18130','--model','qwen38-27b-fp8','--kind','vllm'],
             ['--base','http://127.0.0.1:18131','--model','qwen38-27b-fp8','--kind','vllm'],
             ['--base','http://127.0.0.1:18100','--model','qwen38-27b-vision','--kind','llamacpp','--vision']]


def admit_restore(manifest,validate,args):
    evidence=Path(manifest['controller']['evidence'])
    marker=evidence/'restore-admission.json'
    if validate:
        D.S.require(args in VALIDATIONS,'only exact inherited validation arguments admitted')
        row=json.loads(marker.read_text())
        D.S.require(row.get('manifest_sha256')==D.EXPECTED_MANIFEST_SHA and row.get('passed') is True,
                    'parent restoration admission missing or changed')
        # Each fixed validation may run once; failures are never replayed.
        with (evidence/f'validation-{VALIDATIONS.index(args)}.started').open('x') as file:
            file.write(D.EXPECTED_MANIFEST_SHA+'\n')
    else:
        D.S.require(args==[manifest['controller']['restore_suffix']],'fixed admitted restore suffix required')
        D.S.require(not marker.exists(),'restoration already attempted; no retry')
        pre=json.loads((evidence/'preflight.json').read_text())
        D.S.require(pre['manifest_sha256']==D.EXPECTED_MANIFEST_SHA and D.C.digest(pre['plan'])==manifest['plan_sha256'],
                    'controller preflight identity differs')
        state=D.status()
        # Independently gate direct adapter invocation; physical drain is done only
        # before the first endpoint starts, never between legitimate restores.
        D.S.require(state.get('ActiveState')=='inactive' and state.get('Result')=='success' and
                    state.get('ExecMainStatus')=='0','worker must exit successfully before restoration')
        drain=D.S.require_drained()
        result=D.terminal(pre['plan'],state,passive_drained=True)
        with marker.open('x') as file:
            json.dump(dict(passed=True,manifest_sha256=D.EXPECTED_MANIFEST_SHA,
                           terminal=result,passive_drain=drain),file,indent=2,ensure_ascii=False)
            file.write('\n')


def main(argv=None):
    args=list(sys.argv[1:] if argv is None else argv)
    D.S.require(len(args)>=3 and args[0]=='--manifest-sha256','exact admitted manifest hash required')
    D.EXPECTED_MANIFEST_SHA=args[1];args=args[2:]
    manifest,_=D.admission();D.H.verify();D.restore_clear()
    validate=args[0]=='--validate'
    admit_restore(manifest,validate,args[1:] if validate else args)
    validator=D.H.PARENT/'validate.py';target=validator if validate else D.H.RESTORE
    original_run=subprocess.run;original_argv=sys.argv;prior=sys.modules.get('window')

    def dispatch(command,*a,**kw):
        if len(command)>1 and command[0]=='/usr/bin/python3' and Path(command[1])==validator:
            command=['/usr/bin/python3','-B',str(Path(__file__).resolve()),'--manifest-sha256',
                     D.EXPECTED_MANIFEST_SHA,'--validate',*command[2:]]
        return original_run(command,*a,**kw)

    # Only this child process redirects the historical bare import. The frozen
    # p200 contract remains uniquely named and is never edited or executed live.
    sys.modules['window']=D
    sys.argv=[str(target),*(args[1:] if validate else args)]
    subprocess.run=dispatch
    primary=None
    try:
        runpy.run_path(str(target),run_name='__main__')
    except BaseException as error:
        primary=None if isinstance(error,SystemExit) and error.code in (None,0) else error
        raise
    finally:
        subprocess.run=original_run;sys.argv=original_argv
        if prior is None:sys.modules.pop('window',None)
        else:sys.modules['window']=prior
        try:D.restore_clear()
        except BaseException as secondary:
            if primary is None:raise
            primary.add_note('Secondary restoration guard refusal: '+str(secondary)[:2048])


if __name__=='__main__':main()
