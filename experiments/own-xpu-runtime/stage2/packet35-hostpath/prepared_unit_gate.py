"""Reproduce packet35's CPU argument and sanitizer invalidation unit gates."""
import hashlib,json,os,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 (B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 flags=['-fno-fast-math','-ffp-contract=off'];common=['g++','-std=c++20',*flags,'-DOWN_RT_HOST_ONLY','-I',str(P)]
 arg=B/'argument-block-test'
 command=[*common,'-O2',str(P/'argument_block_test.cpp'),'-o',str(arg)]
 subprocess.run(command,check=True);r=json.loads(subprocess.check_output([arg],text=True))
 assert r['passed'] and r['checks']==9
 r.update(source_sha256=sha(P/'argument_block_test.cpp'),serializer_sha256=sha(P/'argument_block.hpp'),binary_sha256=sha(arg),compile_argv=command,compile_and_link_precision_flags=flags)
 (P/'argument-block-tests.json').write_text(json.dumps(r,indent=2)+'\n')
 binary=B/'prepared-invalidation-tests-asan';names=['prepared_invalidation_test.cpp','owner.cpp','owner_retire.cpp']
 command=[*common,'-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',*[str(P/n) for n in names],'-o',str(binary)]
 subprocess.run(command,check=True)
 environment=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
 r=json.loads(subprocess.check_output([binary],text=True,env=environment));assert r['passed'] and r['tests']==13
 r.update(schema='packet35.prepared-invalidation.v1',sanitizers=['address','undefined'],leak_detection=True,precision_flags_compile_and_link=flags,binary_sha256=sha(binary),source_sha256={n:sha(P/n) for n in names+['owner_api.hpp','owner.hpp','argument_block.hpp']},compile_argv=command,run_argv=[str(binary)],run_environment={k:environment[k] for k in ('ASAN_OPTIONS','UBSAN_OPTIONS','OMP_NUM_THREADS')})
 (P/'prepared-invalidation.json').write_text(json.dumps(r,indent=2)+'\n');print('argument checks 9/9; ASAN+UBSAN invalidation checks 13/13')
if __name__=='__main__':main()
