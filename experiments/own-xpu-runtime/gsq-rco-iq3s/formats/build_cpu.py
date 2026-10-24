#!/usr/bin/env python3
"""One bounded GNU CPU format proof; no inference, device or native build."""
import argparse, hashlib, importlib.util, json, os, pathlib, resource, shutil, subprocess, sys, time
HERE=pathlib.Path(__file__).resolve().parent
REPO=HERE.parents[3]
UP=pathlib.Path('/home/steve/build/flash-next-iq3-baseline-20261010/llama.cpp')
CENSUS=HERE.parent/'metadata/new-census.json'
THREADS=('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def dump(p,v): p.write_text(json.dumps(v,indent=2)+'\n')
def limits():
    assert os.getpriority(os.PRIO_PROCESS,0)>=19
    assert os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32))
    assert all(os.environ.get(k)=='2' for k in THREADS)
    assert shutil.disk_usage(REPO).free-50*1024**2>=27_000_000_000, 'root floor/reservation'
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
def stat(p):
    s=os.stat(p);return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def extract(text,signature):
    start=text.index(signature);brace=text.index('{',start);level=1;i=brace+1
    while level:
        level+=(text[i]=='{')-(text[i]=='}');i+=1
    return text[start:i]
def reference():
    impl=(UP/'ggml/src/ggml-impl.h').read_text();quants=(UP/'ggml/src/ggml-quants.c').read_text()
    blocks=[extract(impl,s) for s in ('static inline float fp32_from_bits(', 'static inline uint32_t fp32_to_bits(', 'static inline float ggml_compute_fp16_to_fp32(')]
    blocks += [extract(quants,s) for s in ('static inline void get_scale_min_k4(', 'void dequantize_row_q2_0(', 'void dequantize_row_q4_K(', 'void dequantize_row_q5_K(', 'void dequantize_row_iq4_xs(')]
    common=(UP/'ggml/src/ggml-common.h').read_text();start=common.index('GGML_TABLE_BEGIN(int8_t, kvalues_iq4nl, 16)');a=common.index('\n',start);z=common.index('GGML_TABLE_END()',a)
    table=common[a:z]
    text='#include <cstdint>\n#include <cassert>\n#include <cstddef>\n#define GGML_COMMON_DECL_C\n#include "'+str(UP/'ggml/src/ggml-common.h')+'"\nusing ggml_fp16_t=uint16_t;\n#define GGML_RESTRICT __restrict__\n'
    text+='\n'.join(blocks[:3])+'\n#define GGML_FP16_TO_FP32(x) ggml_compute_fp16_to_fp32(x)\nstatic const int8_t kvalues_iq4nl[16] = {'+table+'};\n'+'\n'.join(blocks[3:])
    text+='''
extern "C" float gsq_reference_half(uint16_t h){return ggml_compute_fp16_to_fp32(h);}
extern "C" void gsq_reference(unsigned t,const void*p,float*y,size_t n){switch(t){
case 42:dequantize_row_q2_0(static_cast<const block_q2_0*>(p),y,n);break;
case 12:dequantize_row_q4_K(static_cast<const block_q4_K*>(p),y,n);break;
case 13:dequantize_row_q5_K(static_cast<const block_q5_K*>(p),y,n);break;
case 23:dequantize_row_iq4_xs(static_cast<const block_iq4_xs*>(p),y,n);break;
default:assert(false);}}
'''
    return text,[hashlib.sha256(b.encode()).hexdigest() for b in blocks]
def run():
    limits();pins=json.loads((HERE/'source-pins.json').read_text())
    for p,h in pins['sources'].items(): assert sha(p)==h, 'source changed '+p
    local={str(HERE/n):sha(HERE/n) for n in ('formats.hpp','fixture.cpp','build_cpu.py','source-pins.json')}
    attempt=HERE/'build'/str(time.time_ns());attempt.mkdir(parents=True)
    for p in local: shutil.copy2(p,attempt/pathlib.Path(p).name)
    receipt={'passed':False,'attempt':str(attempt),'sources':{**pins['sources'],**local},'model_payload_read_bytes':0,'native_executed':False,'device_executed':False}
    try:
        ref,blocks=reference();(attempt/'reference.cpp').write_text(ref);receipt['reference_functions_sha256']=blocks
        receipt['reference_sha256']=sha(attempt/'reference.cpp')
        compiler=pathlib.Path(shutil.which('g++')).resolve();receipt['compiler']={'path':str(compiler),'sha256':sha(compiler)}
        common=[str(compiler),'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-I'+str(HERE)]
        commands=[common+['-MMD','-MF',str(attempt/'fixture.d'),'-c',str(HERE/'fixture.cpp'),'-o',str(attempt/'fixture.o')],common+['-MMD','-MF',str(attempt/'reference.d'),'-c',str(attempt/'reference.cpp'),'-o',str(attempt/'reference.o')],[str(compiler),str(attempt/'fixture.o'),str(attempt/'reference.o'),'-lcrypto','-o',str(attempt/'format-proof')]]
        receipt['commands']=commands
        spec=importlib.util.spec_from_file_location('compile_turn',REPO/'experiments/own-xpu-runtime/ops/compile_turn.py');turn=importlib.util.module_from_spec(spec);spec.loader.exec_module(turn);sys.modules['build_engine']=sys.modules[__name__]
        with turn.turn():
            for index,cmd in enumerate(commands):
                with (attempt/('compile-'+str(index)+'.stdout')).open('w') as out,(attempt/('compile-'+str(index)+'.stderr')).open('w') as err:
                    cp=subprocess.run(cmd,stdout=out,stderr=err,timeout=120)
                receipt['compile_returncode']=cp.returncode;assert cp.returncode==0,'compile failed '+str(index)
        deps=set()
        for dep in attempt.glob('*.d'):
            deps.update(dep.read_text().replace('\\\n',' ').split(':',1)[1].split())
        receipt['dependencies']={str(pathlib.Path(p).resolve()):sha(p) for p in sorted(deps)}
        assert str(HERE/'formats.hpp') in receipt['dependencies'] and str(UP/'ggml/src/ggml-common.h') in receipt['dependencies']
        census=json.loads(CENSUS.read_text());records=[];argv=[str(attempt/'format-proof')]
        names=('blk.1.ffn_down_exps.weight','blk.0.attn_gate.weight','blk.1.attn_qkv.weight','token_embd.weight')
        for name in names:
            t=census['tensors'][name];block,bs={42:(64,18),12:(256,144),13:(256,176),23:(256,136)}[t['type_id']]
            cols=t['dimensions'][0];size=cols//block*bs;rows=t['bytes']//size
            shard=next(s for s in census['shards'] if pathlib.Path(s['path']).name==t['shard']);p=pathlib.Path(shard['path'])
            assert stat(p)==shard['stat_identity'],'model shard changed'
            fd=os.open(p,os.O_RDONLY)
            try:
                assert [os.fstat(fd).st_dev,os.fstat(fd).st_ino,os.fstat(fd).st_size,os.fstat(fd).st_mtime_ns,os.fstat(fd).st_ctime_ns]==shard['stat_identity']
                for row in (0,rows//2,rows-1):
                    offset=t['file_offset']+row*size;assert offset+size<=t['file_offset']+t['bytes']<=shard['file_bytes']
                    receipt['model_payload_read_bytes']+=size;assert receipt['model_payload_read_bytes']<=2*1024**2
                    data=os.pread(fd,size,offset);assert len(data)==size
                    dst=attempt/('slice-'+str(len(records))+'.bin');dst.write_bytes(data)
                    records.append({'tensor':name,'shard':str(p),'stat_identity':shard['stat_identity'],'row':row,'columns':cols,'type':t['type_id'],'offset':offset,'bytes':size,'sha256':sha(dst)})
                    argv += [str(t['type_id']),str(cols),str(dst)]
                assert stat(p)==shard['stat_identity'],'model shard changed during slices'
            finally:os.close(fd)
        receipt['slices']=records;receipt['run_command']=argv
        with (attempt/'run.stdout').open('w') as out,(attempt/'run.stderr').open('w') as err:
            cp=subprocess.run(argv,stdout=out,stderr=err,timeout=120)
        receipt['run_returncode']=cp.returncode;assert cp.returncode==0,'format proof failed'
        result=json.loads((attempt/'run.stdout').read_text());assert result['passed']
        assert len(result['real_slices'])==len(records)
        for got,want in zip(result['real_slices'],records):
            for k in ('type','columns','bytes','sha256'):assert got[k]==want[k]
        for p,h in receipt['sources'].items():assert sha(p)==h,'post-run source changed '+p
        for p,h in receipt['dependencies'].items():assert sha(p)==h,'post-run dependency changed '+p
        assert sha(compiler)==receipt['compiler']['sha256'],'compiler changed'
        receipt.update(passed=True,binary_sha256=sha(attempt/'format-proof'),result=result)
        evidence=HERE/'evidence';evidence.mkdir(exist_ok=True)
        assert not (evidence/'cpu-proof.json').exists(),'no overwrite'
        dump(evidence/'cpu-proof.json',receipt)
    except BaseException as e:
        receipt['error']=type(e).__name__+': '+str(e);raise
    finally:dump(attempt/'receipt.json',receipt)
    print(json.dumps({'passed':True,'attempt':str(attempt),'result':receipt['result'],'payload_bytes':receipt['model_payload_read_bytes']}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-cpu',action='store_true',required=True);p.parse_args();run()
