#!/usr/bin/env python3
"""Serial wrapper regression and tiny host-only CLI suite; no real-model runs."""
import gzip, hashlib, json, os, re, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
import suite
P=Path(__file__).resolve().parent
E=P/'evidence/long-wrapper-20261013'
PREFIX=['nice','-n','19','ionice','-c','3',sys.executable,'-B']

def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def run(name,argv):
    assert shutil.disk_usage('/').free>=8_000_000_000,'root free space below 8 GB'
    r=subprocess.run(PREFIX+list(map(str,argv)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    log=E/(name+'.log.gz');log.write_bytes(gzip.compress(r.stdout,mtime=0))
    assert r.returncode==0,r.stdout.decode(errors='replace')
    return dict(passed=True,archive=str(log.relative_to(P)),raw_sha256=hashlib.sha256(r.stdout).hexdigest())

def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
    E.mkdir(exist_ok=True);rows=[]
    for script,count in [('test_suite_long.py',14),('test_suite_compiler.py',10),('test_suite_export_retention.py',9),
                         ('test_suite_warmup.py',11),('test_window_storage.py',4),('context_window_gate.py',10),('test_window.py',37)]:
        extra=['--output',E/'window-storage.json'] if script=='test_window_storage.py' else []
        row=run('final-'+script,[P/script,*extra]);row.update(script=script,checks=count)
        raw=gzip.decompress((P/row['archive']).read_bytes()).decode()
        if script in ('test_suite_long.py','context_window_gate.py','test_window.py'):
            assert int(re.search(r'Ran (\d+) tests',raw)[1])==count
        else:
            result=json.loads(raw.splitlines()[-1]);actual=result.get('checks',result.get('gates'))
            assert (len(actual) if isinstance(actual,list) else actual)==count,(script,actual,count)
        rows.append(row);print(script,count,'PASS',flush=True)
    import test_window
    names=unittest.defaultTestLoader.getTestCaseNames(test_window.Gate)
    tests=unittest.TestSuite(test_window.Gate(n) for n in names if n!='test_class_diagnostic_contract')
    import io
    log=io.StringIO();r=unittest.TextTestRunner(stream=log,verbosity=2).run(tests)
    assert r.wasSuccessful() and r.testsRun==36,log.getvalue()
    raw=log.getvalue().encode();archive=E/'final-window-mocked-inherited.log.gz';archive.write_bytes(gzip.compress(raw,mtime=0))
    save(P/'window-mocked-inherited-tests.json',dict(passed=True,tests=36,device_executed=False,
         excluded='test_class_diagnostic_contract is separately included in the 37-test mini-host run',
         archive=str(archive.relative_to(P)),raw_sha256=hashlib.sha256(raw).hexdigest()))
    rows.append(dict(script='window-mocked-inherited',checks=36,passed=True))
    from cpu_gates import host
    binary=P/'build/gnu-host/own-rt-iq3';host(binary)
    dry=[]
    with tempfile.TemporaryDirectory(prefix='long-mini-',dir=P/'build') as temp:
        root=Path(temp);manifest=root/'manifest.json'
        save(manifest,dict(arithmetic='iq3-p17-detmath-v2',token_cap=32,context=4096,complete=True,
             prompts=[dict(prompt_id=n,input_bundle='unused',mini_tokens=t,prompt_tokens=len(t))
                      for n,t in [('LONG-A',[2,5,3,7,1]),('LONG-B',[1,2,3])]]))
        for controller in ('python','native'):
            out=root/controller
            argv=[P/'suite.py','--mini','--binary',binary,'--suite-manifest',manifest,'--context','4096',
                  '--output',out,'--repeat','2','--controller',controller]
            row=run('final-suite-mini-'+controller,argv)
            summary=json.loads((out/'summary.json').read_text());warm=json.loads((out/'warmup/receipt.json').read_text())
            assert summary['passed'] and len(summary['rows'])==4 and summary['token_cap']==32
            assert summary['fixture_steps_not_retained_by_this_binary']==[]
            assert summary['submission_median_tok_s'] is None and not summary['submission_all_requests_have_100_events']
            assert all(r['tokens']==32 and not r['submission_window_available'] and r['submission_tok_s'] is None for r in summary['rows'])
            assert warm['warmup_selection']['suite_prompt_count']==2 and warm['excluded_from_timing']
            row.update(controller=controller,requests=4,tokens=128,warmup_tokens=2,summary=summary,
                       command=list(map(str,PREFIX+argv)),warmup_selection=warm['warmup_selection'])
            dry.append(row);print(controller,'mini CLI: 4 requests / 128 tokens PASS',flush=True)
    save(E/'suite-mini-dry.json',dict(passed=True,mini_only=True,device_executed=False,rows=dry))
    # Read-only oracle admission, no model evaluation or payload load.
    manifest=suite.ROOT/'experiments/own-xpu-runtime/stage2/long-inputs-20261012/suite-manifest.json'
    m=json.loads(manifest.read_text());assert suite.validate_manifest(m,4096)==32
    checker=suite.checker_for_cap(32);admissions=[]
    for entry in m['prompts']:
        oracle=suite.ROOT/entry['oracle_directory'];n,f=checker.check_prompt(oracle,oracle,entry,suite.ROOT)
        admissions.append(dict(prompt_id=entry['prompt_id'],tokens=n,fixtures=f,passed=True))
    names=('suite.py','window.py','context_window_gate.py','test_suite_long.py','long_suite_cpu_gate.py',
           'test_suite_compiler.py','test_suite_export_retention.py','test_suite_warmup.py','test_window.py','test_window_storage.py')
    receipt=dict(passed=True,device_executed=False,real_model_executed=False,rows=rows,
                 checks=sum(r['checks'] for r in rows),mini_requests=8,mini_tokens=256,
                 oracle_admissions=admissions,source_sha256={n:suite.pipeline.sha(P/n) for n in names},
                 checker_sha256=suite.pipeline.sha(suite.CHECKER32),manifest_sha256=suite.pipeline.sha(manifest),
                 dry_receipt_sha256=suite.pipeline.sha(E/'suite-mini-dry.json'))
    save(P/'long-suite-wrapper-gates.json',receipt)
    print('PASS',receipt['checks'],'checks; 8 mini requests / 256 tokens; 2 read-only oracle admissions',flush=True)
if __name__=='__main__':main()
