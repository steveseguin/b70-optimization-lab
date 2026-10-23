#!/usr/bin/env python3
"""One pinned p196 restore, with p200 manifest and per-operation incident guards."""
import importlib.util
from pathlib import Path
import runpy
import subprocess
import sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('_p200_restore_driver',HERE/'driver.py')
D=importlib.util.module_from_spec(spec);sys.modules[spec.name]=D;spec.loader.exec_module(D)


def main(argv=None):
    args=list(sys.argv[1:] if argv is None else argv)
    D.S.require(len(args)>=3 and args[0]=='--manifest-sha256','exact admitted manifest hash required')
    D.EXPECTED_MANIFEST_SHA=args[1];args=args[2:]
    manifest,_=D.admission();D.H.verify();D.restore_clear()
    validate=args[0]=='--validate'
    D.S.require(validate or args==[manifest['controller']['restore_suffix']], 'fixed admitted restore suffix required')
    validator=D.H.PARENT/'validate.py';target=validator if validate else D.H.RESTORE
    original_run=subprocess.run;original_argv=sys.argv;prior=sys.modules.get('window')

    def dispatch(command,*a,**kw):
        if len(command)>1 and command[0]=='/usr/bin/python3' and Path(command[1])==validator:
            command=['/usr/bin/python3','-B',str(Path(__file__).resolve()),'--manifest-sha256',
                     D.EXPECTED_MANIFEST_SHA,'--validate',*command[2:]]
        return original_run(command,*a,**kw)

    # The frozen contract remains uniquely named. Only this child process redirects
    # inherited `from window import faults_clear` to the operational guard.
    sys.modules['window']=D
    sys.argv=[str(target),*(args[1:] if validate else args)]
    subprocess.run=dispatch
    try:
        runpy.run_path(str(target),run_name='__main__')
    finally:
        subprocess.run=original_run;sys.argv=original_argv
        if prior is None:sys.modules.pop('window',None)
        else:sys.modules['window']=prior
        D.restore_clear()


if __name__=='__main__':main()
