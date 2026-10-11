"""CPU-only executable/oracle checks. No device API imports or calls.

Real files are opened rb and only headers plus four rows of each present type
are read. Run at nice19, ionice idle, OMP_NUM_THREADS=2. Scratch stays in build/.
"""
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import sys

HERE=Path(__file__).resolve().parent
PACKET=HERE.parent
ROOT=PACKET.parents[3]
OLD=PACKET.parents[1]/'stage1/packet1b'
sys.path[:0]=[str(OLD),str(OLD/'tests'),str(PACKET/'kernels')]
from loaders.headers import gguf_header, TYPES
from loaders.dequant import dequant_block, _f32
from test_headers import ggfile,string
from test_dequant import pack_fixture
from generate_grids import render
import torch

KINDS=['F32','F16','BF16','Q8_0','Q3_K','Q6_K','IQ3_XXS','IQ4_NL','IQ3_S','IQ2_S']
IDS={v[0]:k for k,v in TYPES.items()}
MODEL=ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1'
def digest(b):return hashlib.sha256(b).hexdigest()
def write_json(p,obj):p.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
def plan_rows(tensors):
    lines=['# derived from admitted packet1 tensor-census.json; GGUF dimensions fastest first']
    for t in tensors:
        layer=t['layer'] if t['layer'] is not None else -1
        mask=0 if t['component'] in ('embedding','ple_lookup') else 3 if t['hc_projection_replicated'] else 1 if 0<=layer<24 else 2
        lines.append(' '.join(map(str,[Path(t['shard']).name,t['name'],t['component'],t['type_id'],t['data_offset'],t['bytes'],layer,mask,len(t['dimensions']),*t['dimensions']])))
    return '\n'.join(lines)+'\n'

def main():
    p=argparse.ArgumentParser();p.add_argument('--host',type=Path,required=True);p.add_argument('--scratch',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--model-dir',type=Path,default=Path('/mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS'))
    a=p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
    assert 'idle' in subprocess.check_output(['ionice','-p',str(os.getpid())],text=True)
    assert PACKET/'build' in a.scratch.resolve().parents
    a.scratch.mkdir(parents=True,exist_ok=True);devices=a.scratch/'device-fixtures'
    if devices.exists():shutil.rmtree(devices)
    devices.mkdir()
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    def run(*args,ok=True):
        c=subprocess.run([str(a.host),*map(str,args)],capture_output=True)
        if ok:assert c.returncode==0,c.stderr.decode()
        else:assert c.returncode!=0,('expected rejection',args)
        return c.stdout
    records=[];rejections=[];values=0;gemv_rows=0
    assert (PACKET/'kernels/grids.hpp').read_text()==render()
    run('--ownership')
    run('--routes')
    # Metadata and parser checks use the pre-existing Python synthetic builder.
    metadata=[('text',8,string('hello\u03bb')),('flags',9,struct.pack('<IQBBB',7,3,1,0,1))]
    for kind,fmt in [(0,'B'),(1,'b'),(2,'H'),(3,'h'),(4,'I'),(5,'i'),(6,'f'),(7,'B'),(10,'Q'),(11,'q'),(12,'d')]:
        metadata.append((str(kind),kind,struct.pack('<'+fmt,1)))
    def parse_blob(label,b,ok=True):
        path=a.scratch/(label+'.gguf');path.write_bytes(b)
        raw=run('--headers',path,ok=ok)
        if ok:
            cpu=json.loads(raw)[0];py=gguf_header(io.BytesIO(b),len(b));compare_header(cpu,py)
        else:rejections.append(label)
        return path
    def compare_header(cpu,py):
        for ck,pk in [('file_bytes','file_bytes'),('header_bytes','header_bytes_read'),('data_start','data_start'),('read_bytes','header_bytes_read'),('metadata','metadata')]:assert cpu[ck]==py[pk],ck
        assert cpu['tensors']=={n:{k:t[k] for k in ('type_id','data_offset','bytes','dimensions')} for n,t in py['tensors'].items()}
    for kind in KINDS:parse_blob('valid-'+kind,ggfile([('w',[TYPES[IDS[kind]][1],2],IDS[kind],0)],metadata))
    bad={
      'version':ggfile(version=2),'unknown-type':ggfile([('w',[32],99,0)]),
      'cross-block-row':ggfile([('w',[16,2],8,0)]),'duplicate-tensor':ggfile([('w',[32],8,0),('w',[32],8,64)]),
      'overlap':ggfile([('a',[32],8,0),('b',[32],8,32)]),'unaligned':ggfile([('w',[32],8,1)]),
      'duplicate-meta':ggfile(metadata=[('x',4,struct.pack('<I',1))]*2),
      'bad-alignment':ggfile(metadata=[('general.alignment',4,struct.pack('<I',3))]),
      'bad-alignment-type':ggfile(metadata=[('general.alignment',5,struct.pack('<i',32))]),
      'bool':ggfile(metadata=[('x',7,b'\2')]),'nested':ggfile(metadata=[('x',9,struct.pack('<IQ',9,0))]),
      'metadata-kind':ggfile(metadata=[('x',13,b'')]),'array-kind':ggfile(metadata=[('x',9,struct.pack('<IQ',13,0))]),
      'array-count':ggfile(metadata=[('x',9,struct.pack('<IQ',1,1000001))]),
      'count':b'GGUF'+struct.pack('<IQQ',3,1000001,0),'incomplete-split':ggfile(metadata=[('split.no',2,struct.pack('<H',0))]),
      'zero-dim':ggfile([('w',[0],1,0)]),'zero-rank':ggfile([('w',[],1,0)]),'rank5':ggfile([('w',[1]*5,1,0)]),
    }
    base=ggfile()
    for n in (0,4,12,24,30,len(base)-1):bad['truncate-'+str(n)]=base[:n]
    b=bytearray(ggfile([('w',[1,1],1,0)]));struct.pack_into('<QQ',b,37,1<<62,8);bad['overflow']=b
    b=bytearray(base);b[32]=255;bad['utf8']=b
    b=bytearray(base);struct.pack_into('<Q',b,24,1<<40);bad['string-length']=b
    for label,b in bad.items():parse_blob(label,b,False)
    # Three shards including metadata-only split0, mirroring this release.
    split_paths=[];synthetic=[]
    for ordinal,ts in enumerate([[],[('blk.0.attn_qkv.weight',[32,2],8,0)],[('token_embd.weight',[32,2],8,0)]]):
        meta=[('split.no',2,struct.pack('<H',ordinal)),('split.count',2,struct.pack('<H',3)),('split.tensors.count',5,struct.pack('<i',2))]
        b=ggfile(ts,meta);path=a.scratch/f'split{ordinal}.gguf';path.write_bytes(b);split_paths.append(path)
        if ts:
            t=gguf_header(io.BytesIO(b),len(b))['tensors'][ts[0][0]]
            synthetic.append(dict(t,name=ts[0][0],component='gdn' if ordinal==1 else 'embedding',layer=0 if ordinal==1 else None,hc_projection_replicated=False,shard=path.name))
    run('--headers',*split_paths)
    for label,paths in [('missing-split',split_paths[:2]),('duplicate-split',[split_paths[0],split_paths[1],split_paths[1]])]:run('--headers',*paths,ok=False);rejections.append(label)
    synthetic_plan=a.scratch/'synthetic.tsv';synthetic_plan.write_text(plan_rows(synthetic));run('--reserve',synthetic_plan,*split_paths)
    assert json.loads(run('--model',synthetic_plan,*split_paths))==[68,0,68]
    lines=synthetic_plan.read_text().splitlines()
    for label,field,value in [('census-size',5,'69'),('host-on-device',7,'1'),('bad-component',2,'unknown'),('wrong-card',7,'2')]:
        copy=lines.copy();idx=2 if label=='host-on-device' else 1;parts=copy[idx].split();parts[field]=value;copy[idx]=' '.join(parts)
        bad_plan=a.scratch/(label+'.tsv');bad_plan.write_text('\n'.join(copy)+'\n');run('--model',bad_plan,*split_paths,ok=False);rejections.append(label)
    for label,changes in [('fake-host',{2:'embedding',7:'0'}),('fake-layer',{6:'24',7:'2'})]:
        copy=lines.copy();parts=copy[1].split()
        for field,value in changes.items():parts[field]=value
        copy[1]=' '.join(parts);bad_plan=a.scratch/(label+'.tsv');bad_plan.write_text('\n'.join(copy)+'\n');run('--model',bad_plan,*split_paths,ok=False);rejections.append(label)
    # Non-page-aligned mmap slice, byte identity and moved owner lifetime.
    payload=bytearray(ggfile([('w',[32,3],8,0)]));h=gguf_header(io.BytesIO(payload),len(payload));payload[h['data_start']:]=bytes(range(102))
    sf=parse_blob('mapped',payload);out=a.scratch/'slice.out';run('--slice',sf,'w',31,60,out);assert out.read_bytes()==bytes(range(31,91))
    run('--slice',sf,'w',102,1,out,ok=False);rejections.append('slice-end')
    # All 16-bit widening patterns, including signed zeros, subnormals and NaNs.
    wide=a.scratch/'wide.out';run('--widen',wide)
    expected=bytearray()
    for bits in range(65536):
        half_value=struct.unpack('<e',struct.pack('<H',bits))[0]
        bf_value=struct.unpack('<f',struct.pack('<I',bits<<16))[0]
        expected+=struct.pack('<ff',half_value,bf_value)
    assert wide.read_bytes()==expected,'all 16-bit widening patterns'
    rng=random.Random(20261011);float_values=[]
    for _ in range(20000):
        bits=rng.getrandbits(32)
        if bits&0x7f800000!=0x7f800000:float_values.append(struct.unpack('<f',struct.pack('<I',bits))[0])
    # Exact midpoint cases for every finite half pair plus adjacent FP32 values.
    for bits in range(0x7bff):
        lo=struct.unpack('<e',struct.pack('<H',bits))[0];hi=struct.unpack('<e',struct.pack('<H',bits+1))[0];mid=(lo+hi)*.5
        raw=struct.unpack('<I',struct.pack('<f',mid))[0]
        float_values.extend(struct.unpack('<f',struct.pack('<I',b))[0] for b in (raw-1,raw,raw+1))
    cast_in=a.scratch/'casts.in';cast_out=a.scratch/'casts.out';cast_in.write_bytes(struct.pack('<'+'f'*len(float_values),*float_values));run('--casts',cast_in,cast_out)
    cast_expected=bytearray()
    for v in float_values:
        try:h=struct.pack('<e',v)
        except OverflowError:h=struct.pack('<H',0xfc00 if v<0 else 0x7c00)
        bits=struct.unpack('<I',struct.pack('<f',v))[0];b=((bits+0x7fff+((bits>>16)&1))>>16)&65535
        cast_expected+=h+struct.pack('<H',b)
    assert cast_out.read_bytes()==cast_expected,'round-to-nearest-even output casts'
    def check_math(label,kind,raw,k,rows=4,activation='BF16',output='BF16',device=False,origin=None):
        nonlocal values,gemv_rows
        block,size=TYPES[IDS[kind]][1:]
        decoded=torch.cat([dequant_block(kind,raw[i:i+size]) for i in range(0,len(raw),size)])
        decoded_bytes=decoded.numpy().tobytes();weight=decoded.tolist()
        x=[_f32(((i*37)%127-63)/64) for i in range(k)]
        xbytes=b''.join(struct.pack('<f',v)[2:] if activation=='BF16' else struct.pack('<e',v) for v in x)
        xvalues=[struct.unpack('<f',b'\0\0'+xbytes[i:i+2])[0] if activation=='BF16' else struct.unpack('<e',xbytes[i:i+2])[0] for i in range(0,len(xbytes),2)]
        reference=[]
        for row in range(rows):
            lanes=[0.0]*32
            for lane in range(32):
                for col in range(lane,k,32):lanes[lane]=_f32(lanes[lane]+_f32(weight[row*k+col]*xvalues[col]))
            width=1
            while width<32:
                for i in range(0,32,2*width):lanes[i]=_f32(lanes[i]+lanes[i+width])
                width*=2
            reference.append(lanes[0])
        f=a.scratch/(label+'.fixture');f.write_bytes(struct.pack('<IIIII',IDS[kind],k,rows,IDS[activation],IDS[output])+raw+xbytes)
        result=a.scratch/(label+'.out');run('--math',f,result);data=result.read_bytes()
        assert data[:len(decoded_bytes)]==decoded_bytes,('dequant',label)
        sums=struct.pack('<'+'f'*rows,*reference)
        assert data[len(decoded_bytes):len(decoded_bytes)+4*rows]==sums,('gemv FP32',label)
        rounded=bytearray()
        for value in reference:
            if output=='BF16':bits=struct.unpack('<I',struct.pack('<f',value))[0];rounded+=struct.pack('<H',((bits+0x7fff+((bits>>16)&1))>>16)&65535)
            else:
                try:rounded+=struct.pack('<e',value)
                except OverflowError:rounded+=struct.pack('<H',0xfc00 if value<0 else 0x7c00)
        assert data[-rows*2:]==rounded,('output cast',label)
        # Fresh executable process repeat, comparing all output bytes.
        run('--math',f,result);assert data==result.read_bytes(),('fresh repeat',label)
        values+=len(weight);gemv_rows+=rows
        records.append(dict(label=label,type=kind,columns=k,rows=rows,packed_bytes=len(raw),packed_sha256=digest(raw),decoded_sha256=digest(decoded_bytes),gemv_fp32_sha256=digest(sums),fixture_sha256=digest(f.read_bytes()),output_sha256=digest(data),origin=origin))
        if device:(devices/f.name).write_bytes(f.read_bytes())
    for kind in KINDS:
        block,size=TYPES[IDS[kind]][1:];k=2560 if block>1 else 320
        logical,_=pack_fixture(kind);check_math('logical-'+kind,kind,logical*(4*k//block),k,device=False)
        for trial in range(2):
            blocks=[]
            for n in range(4*k//block):
                b=bytearray(rng.randbytes(size))
                if kind=='F32':b[:]=struct.pack('<f',rng.uniform(-2,2))
                elif kind=='F16':b[:]=struct.pack('<e',rng.uniform(-2,2))
                elif kind=='BF16':b[:]=struct.pack('<f',rng.uniform(-2,2))[2:]
                else:
                    scale=struct.pack('<e',(-1 if n%2 else 1)*(2**(-14) if trial else .0078125))
                    if kind in ('Q3_K','Q6_K'):b[-2:]=scale
                    else:b[:2]=scale
                if kind=='IQ2_S':
                    for q in range(32):
                        ix=(n*32+q)%1024;b[2+q]=ix&255;b[66+q//4]=(b[66+q//4]&~(3<<(2*(q%4))))|((ix>>8)<<(2*(q%4)))
                elif kind=='IQ3_S':
                    for q in range(64):
                        ix=(n*64+q)%512;b[2+q]=ix&255;b[66+q//8]=(b[66+q//8]&~(1<<(q%8)))|((ix>>8)<<(q%8))
                elif kind=='IQ3_XXS':
                    for q in range(64):b[2+q]=(n*64+q)%256
                blocks.append(bytes(b))
            check_math(f'random{trial}-'+kind,kind,b''.join(blocks),k,activation='F16' if trial else 'BF16',output='F16' if trial else 'BF16',device=True)
    # Read only current shard headers and small four-row ranges, never rehash payload.
    admission=json.loads((MODEL/'admission-receipt.json').read_text());census=json.loads((MODEL/'tensor-census.json').read_text())
    paths=[a.model_dir/Path(f['path']).name for f in admission['files']]
    cpp=json.loads(run('--headers',*paths));header_reads=0;header_pins=[]
    for path,info,parsed in zip(paths,admission['files'],cpp):
        with path.open('rb',buffering=0) as stream:
            py=gguf_header(stream,path.stat().st_size);stream.seek(0);raw=stream.read(py['header_bytes_read'])
        compare_header(parsed,py);assert digest(raw)==info['header_sha256'];assert path.stat().st_size==info['bytes']
        header_reads+=3*py['header_bytes_read'] # C++, Python and hash read
        header_pins.append(dict(file=path.name,header_bytes=py['header_bytes_read'],sha256=digest(raw)))
    plan=a.scratch/'iq3-plan.tsv';plan.write_text(plan_rows(census['tensors']))
    totals=json.loads(run('--model',plan,*paths));header_reads+=sum(x['header_bytes'] for x in header_pins)
    assert totals==[26506330880,26798288640,29321610240],totals
    real_bytes=0
    for kind in sorted(census['types']):
        candidates=[t for t in census['tensors'] if t['type']==kind and len(t['dimensions'])>=2 and t['dimensions'][1]>=4]
        t=sorted(candidates,key=lambda t:t['name'])[0];k=t['dimensions'][0];block,size=TYPES[IDS[kind]][1:]
        n=4*k//block*size;assert n<128*1024
        path=a.model_dir/Path(t['shard']).name;offset=t['file_offsets'][0]
        with path.open('rb',buffering=0) as stream:stream.seek(offset);raw=stream.read(n)
        assert len(raw)==n;real_bytes+=n
        check_math('real-'+kind,kind,raw,k,device=True,origin=dict(shard=path.name,tensor=t['name'],offset=offset,bytes=n))
    receipt=dict(schema='own-runtime.iq3.packet2.cpu.v1',passed=True,host_binary_sha256=digest(a.host.read_bytes()),python=sys.version,torch=torch.__version__,nice=19,OMP_NUM_THREADS='2',ionice='idle',header_bytes_read_total=header_reads,real_payload_bytes_read=real_bytes,headers=header_pins,census_tensors=len(census['tensors']),placement_bytes=totals,dequant_values=values,gemv_rows=gemv_rows,fresh_process_repeats=len(records),widen_patterns_per_type=65536,output_cast_values=len(float_values),routed_expert_ids_tested=512,parser_rejections=rejections,fixtures=records,device_execution=False)
    write_json(a.receipt,receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('headers','fixtures','parser_rejections')},indent=2))

if __name__=='__main__':main()
