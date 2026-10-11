#!/usr/bin/env python3
"""CPU-only build and dependency inspection. Never executes the device program."""
import hashlib,json,os,shutil,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
PACKET=HERE.parent
ROOT=HERE.parents[2]
BUILD=PACKET/'build'/'issuing'
COMPILER=Path('/opt/intel/oneapi/compiler/2026.0/bin/icpx')
FLAGS=['-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if os.getpriority(os.PRIO_PROCESS,0)!=19 or os.environ.get('OMP_NUM_THREADS')!='2':raise SystemExit('nice19/OMP_NUM_THREADS=2 required')
    BUILD.mkdir(parents=True,exist_ok=True)
    scratch=PACKET/'build'/'scratch-issuing';scratch.mkdir(exist_ok=True)
    env=dict(os.environ,TMPDIR=str(scratch))
    lib='/opt/intel/oneapi/compiler/2026.0/lib'
    env['LD_LIBRARY_PATH']=lib+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    logs=[]
    def run(argv):
        command=['nice','-n','19','ionice','-c','3',*map(str,argv)]
        p=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env)
        logs.append({'command':command,'returncode':p.returncode,'output':p.stdout})
        if p.returncode:raise RuntimeError(p.stdout)
        return p.stdout
    try:
        version=run([COMPILER,'--version'])
        if '2026.0' not in version:raise RuntimeError('expected IntelLLVM2026.0')
        run(['cmake','-S',HERE,'-B',BUILD,'-DCMAKE_CXX_COMPILER='+str(COMPILER),'-DCMAKE_BUILD_TYPE=Release'])
        run(['cmake','--build',BUILD,'-j','1'])
        link=(BUILD/'CMakeFiles/launch-bench.dir/link.txt').read_text()
        compile_flags=(BUILD/'CMakeFiles/launch-bench.dir/flags.make').read_text()
        for flag in FLAGS:
            if flag not in link or flag not in compile_flags:raise RuntimeError('precision flag absent: '+flag)
        deps=run(['ldd',BUILD/'launch-bench'])
        if 'not found' in deps:raise RuntimeError('ldd missing library')
        sources=[HERE/'native.cpp',HERE/'dynamic_probe.cpp',HERE/'raw.cl',HERE/'CMakeLists.txt',HERE/'build.py',ROOT/'stage1/packet3-prep/src/owner.cpp',ROOT/'stage1/packet3-prep/src/owner.hpp']
        receipt={'schema':'packet20.issuing-build.v1','compiled':True,'device_executed':False,'compiler_version':version,'precision_flags_both_compile_and_link':FLAGS,'link_txt':link,'compile_flags':compile_flags,'ldd':deps,'methods_compiled':['explicit_in_order','explicit_out_of_order','explicit_wait_each','implicit_in_order','discard_in_order','graph','raw_regular','raw_immediate','fusion8'],'dynamic_parameter_binding_update_compiled':True,'raw_spirv_compiled':True,'missing_compile_apis':[],'runtime_support':'not tested; fault halt','expected_timing_rows':270,'device_requested_bytes':87040,'opaque_driver_allocation_bytes':None,'sha256':{str(p.relative_to(PACKET)) if p.is_relative_to(PACKET) else str(p):sha(p) for p in sources+[BUILD/'launch-bench',BUILD/'raw.spv']}}
        (HERE/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    finally:
        (HERE/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
        shutil.rmtree(scratch)
if __name__=='__main__':main()
