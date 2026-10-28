#!/usr/bin/env python3
"""Bounded post-capture comparison; run only after coordinator CPU release.
Never launches a device/model or alters frozen observer sources.
"""
import argparse,array,hashlib,json,math,pathlib,struct,sys
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import validate as V
import validate_prepared as P
RAW_FIELDS={'conv':(0,40960),'alpha':(40960,192),'beta':(41152,192),'y':(41344,24576)}
PREP_FIELDS={'q_scaled':(0,8192),'k':(8192,8192),'decay':(16384,192),'beta':(16576,192)}
def read(path,maximum=64*1024**2):
 path=pathlib.Path(path);before=V.stamp(path);assert before[2]<=maximum
 raw=path.read_bytes();assert V.stamp(path)==before;return raw
def doc(path):return V.load(read(path))
def sha(b):return hashlib.sha256(b).hexdigest()
def delta(a,b):
 assert len(a)==len(b) and len(a)%4==0
 if a==b:return dict(unequal_words=0,max_abs=0.,rms=0.)
 x=array.array('f');x.frombytes(a);y=array.array('f');y.frombytes(b);assert sys.byteorder=='little'
 count=0;maximum=0.;total=0.;first=None
 for i,(u,v)in enumerate(zip(x,y)):
  assert math.isfinite(u)and math.isfinite(v);d=float(u)-v;maximum=max(maximum,abs(d));total+=d*d
  if a[4*i:4*i+4]!=b[4*i:4*i+4]:
   count+=1
   if first is None:first=dict(index=i,actual=u,replay=v,actual_bits=a[4*i:4*i+4].hex(),replay_bits=b[4*i:4*i+4].hex())
 return dict(unequal_words=count,max_abs=maximum,rms=math.sqrt(total/len(x)),first=first)
def comparison(root,reference,result,rows):
 plan=doc(root/'plan.json');oldplan=doc(reference/'plan.json');native=root/'output/native/rank0';oldnative=reference/'output/native/rank0'
 attempts=native/'l4-prepared-attempts.jsonl'
 if attempts.exists():
  observed=[V.load(x)for x in read(attempts,8*1024**2).splitlines()]
  result['observed_attempts']=dict(rows=len(observed),first=observed[0]if observed else None,sha256=sha(read(attempts)))
 result['terminal']=doc(root/'output/terminal.json')
 prep=native/'l4-prepared-history'
 if not(prep/'seal.json').exists():
  result.update(analysis_complete=False,qualification_passed=False,limitation='No complete prepared seal; observed pre-refusal metadata retained. No partial history promoted.')
  return
 receipts={}
 for label,p in [('actual_AOT',plan),('reference_capture_JIT',oldplan)]:
  cfg=doc(pathlib.Path(p['config']));receipt=doc(pathlib.Path(cfg['build_receipt']));commands=receipt['commands'];receipts[label]=receipt
  result.setdefault('builds',{})[label]=dict(binary_sha256=receipt['binary_sha256'],aot_in_all_compile_and_link=all('-fsycl-targets=intel_gpu_bmg_g31'in c['cmd']for c in commands.values()),receipt_sha256=sha(read(pathlib.Path(cfg['build_receipt']))))
 result['capture_source_differences']=[name for name in set(receipts['actual_AOT']['sources'])|set(receipts['reference_capture_JIT']['sources'])if receipts['actual_AOT']['sources'].get(name)!=receipts['reference_capture_JIT']['sources'].get(name)]
 assert result['builds']['actual_AOT']['aot_in_all_compile_and_link'] is True
 assert result['builds']['reference_capture_JIT']['aot_in_all_compile_and_link'] is False
 control=pathlib.Path(plan['prepared_control_reference'])
 try:result['prepared_validation']=P.verify(prep,attempts,control)
 except Exception as error:result['prepared_validation_error']=dict(type=type(error).__name__,message=str(error))
 # Independently require complete native seals before inspecting rejected control/shape values.
 data=read(prep/'prepared.bin');index=read(prep/'rows.jsonl');seal=doc(prep/'seal.json')
 assert len(data)==P.TOTAL and seal['payload_sha256']==sha(data)and seal['index_sha256']==sha(index)
 metadata=[V.load(x)for x in index.splitlines()];assert len(metadata)==244
 result['raw_validation']=V.verify(native/'l4-raw-history',plan['prompt_tokens'])
 result['reference_raw_validation']=V.verify(oldnative/'l4-raw-history',oldplan['prompt_tokens'])
 raw=read(native/'l4-raw-history/history.bin');oldraw=read(oldnative/'l4-raw-history/history.bin')
 result['AOT_vs_JIT_capture']=dict(raw_input_fields_all_equal=all(raw[p*65920:p*65920+41344]==oldraw[p*65920:p*65920+41344]for p in range(244)),raw_history_bytes_equal=raw==oldraw,actual_raw_sha256=sha(raw),reference_raw_sha256=sha(oldraw))
 device_root=pathlib.Path('/dev/shm/sc117-l4-raw-device-c27-20261028-r1/output')
 host_root=pathlib.Path('/dev/shm/sc117-l4-native-raw-replay-20261028-r2/output')
 pinned=doc(HERE/'device-r1-evidence/output-hashes.json')
 device={n:read(device_root/n)for n in ('device-prepared.f32','device-y.f32','device-final-state.f32')}
 for name,b in device.items():assert sha(b)==pinned[str(device_root/name)]
 host={name:read(host_root/path)for name,path in [('device-prepared.f32','native-prepared.f32'),('device-y.f32','native-host-y.f32'),('device-final-state.f32','native-host-final-state.f32')]}
 result['standalone_JIT_GPU_vs_host']={name:host[name]==b for name,b in device.items()}
 assert all(result['standalone_JIT_GPU_vs_host'].values())
 build=doc(HERE/'device-build-r2.json');assert not any('-fsycl-targets='in x for x in build['argv'])
 result['standalone_replay_identity']=dict(device_build_sha256=sha(read(HERE/'device-build-r2.json')),device_prepared_manifest_sha256=sha(read(HERE/'device-prepared-r2.json')),mode='JIT GPU (not an AOT replay) and byte-identical host replay')
 expected_controls=read(control,384);controls_bad=[];first_raw=None;first_prep=None;all_prep=bytearray();actual_y=bytearray()
 for p in range(244):
  record=dict(position=p,actual_AOT_vs_previous_JIT_capture={},actual_prepared_vs_standalone_JIT_GPU={})
  for field,(off,n)in RAW_FIELDS.items():
   a=raw[p*65920+off:p*65920+off+n];b=oldraw[p*65920+off:p*65920+off+n];metric=delta(a,b);record['actual_AOT_vs_previous_JIT_capture'][field]=metric
   if field=='y':actual_y.extend(a)
   if metric['unequal_words']and first_raw is None:first_raw=dict(position=p,field=field,metric=metric)
  scratch=data[p*P.ROW_BYTES:p*P.ROW_BYTES+P.SCRATCH];all_prep.extend(scratch)
  for field,(off,n)in PREP_FIELDS.items():
   metric=delta(scratch[off:off+n],device['device-prepared.f32'][p*P.SCRATCH+off:p*P.SCRATCH+off+n]);record['actual_prepared_vs_standalone_JIT_GPU'][field]=metric
   if metric['unequal_words']and first_prep is None:first_prep=dict(position=p,field=field,metric=metric,actual_invocation=metadata[p]['invocation'])
  ctrl=data[p*P.ROW_BYTES+P.SCRATCH:(p+1)*P.ROW_BYTES]
  metrics={name:delta(ctrl[off:off+192],expected_controls[off:off+192])for name,off in [('a',0),('dt',192)]}
  record['bound_GGUF_controls']=metrics;record['actual_control_words']=list(struct.unpack('<3i',ctrl[-12:]))
  if any(m['unequal_words']for m in metrics.values()):controls_bad.append(dict(position=p,metrics=metrics))
  rows.append(record)
 result.update(first_AOT_vs_JIT_capture_difference=first_raw,first_actual_prepared_vs_standalone_difference=first_prep,bound_controls_differing_rows=controls_bad,
  actual_prepared_full_vs_standalone=delta(bytes(all_prep),device['device-prepared.f32']),actual_y_full_vs_standalone=delta(bytes(actual_y),device['device-y.f32']),
  first_actual_invocation=metadata[0]['invocation'],actual_prepared_payload_sha256=seal['payload_sha256'],analysis_complete=True,
  qualification_passed=False,scope='Numerical boundary localization only. Standalone qualification remains failed unless all actual y words match. Build identity alone cannot establish an AOT/JIT cause; inputs and prepared boundary must first match.')
 result['qualification_passed']=result['actual_y_full_vs_standalone']['unequal_words']==0 and 'prepared_validation_error'not in result
 if (root/'output/source-neutrality.json').exists():result['source_neutrality']=doc(root/'output/source-neutrality.json')

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=pathlib.Path,default=pathlib.Path('/dev/shm/sc117-l4-history-target244-20261028-r3'));ap.add_argument('--reference',type=pathlib.Path,default=pathlib.Path('/dev/shm/sc117-l4-history-target244-20261028-r2'));ap.add_argument('--out',type=pathlib.Path,required=True);args=ap.parse_args();assert not args.out.exists();row_path=args.out.with_suffix('.rows.jsonl');assert not row_path.exists()
 result={'schema':'ownrt.l4-prepared-boundary-comparison.v1','analysis_complete':False,'helper_sha256':sha(read(__file__))};rows=[]
 try:comparison(args.root,args.reference,result,rows)
 except Exception as error:result['error']=dict(type=type(error).__name__,message=str(error))
 with row_path.open('x')as f:
  for row in rows:f.write(json.dumps(row,separators=(',',':'))+'\n')
 result['per_row']=dict(path=str(row_path),sha256=sha(read(row_path)),rows=len(rows))
 with args.out.open('x')as f:json.dump(result,f,indent=2);f.write('\n')
 raise SystemExit(0 if result['analysis_complete']else 1)
