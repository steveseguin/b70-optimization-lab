from pathlib import Path
import json,hashlib,struct
ROOT=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime')
OUT=Path('/dev/shm/sc117-l4-native-replay-20261028-r1');OUT.mkdir()
prior=json.loads((ROOT/'research/pp4-review-2026-10-28/reference-one-row/hc-down/extraction.json').read_text())
placement=ROOT/'gsq-rco-iq3s/loader/placement.tsv';auth=ROOT/'gsq-rco-iq3s/loader/shard-auth.tsv'
assert hashlib.sha256(placement.read_bytes()).hexdigest()=='a9ab0302d85f208717748c70be9d09d0a494e07f494a0e67b39dac6cc9468253'
assert hashlib.sha256(auth.read_bytes()).hexdigest()==prior['model_manifest_sha256']
model=Path('/mnt/usb-models/llm-models/SC117-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-eec4e10a')
shard=model/prior['tensor']['shard'];expected=prior['shard_stat_verified']
def stamp():
 s=shard.stat();return[s.st_size,s.st_dev,s.st_ino,s.st_mtime_ns,s.st_ctime_ns]
assert stamp()==expected
start=prior['tensor']['file_offset']-prior['tensor']['data_offset'];assert start==11024384
records=[];payload=b''
with shard.open('rb') as f:
 header=f.read(prior['header_bytes_read']);assert hashlib.sha256(header).hexdigest()==prior['header_sha256']
 for name in ['blk.4.ssm_a','blk.4.ssm_dt.bias']:
  row=next(line.split() for line in placement.read_text().splitlines() if line.split()[1]==name)
  assert row[0]==shard.name and row[2]=='gdn' and row[3]=='0' and row[5]=='192' and row[8:] == ['1','48']
  offset=start+int(row[4]);assert offset+192<=expected[0];f.seek(offset);data=f.read(192);assert len(data)==192
  records.append(dict(name=name,type='F32',shape=[48],data_offset=int(row[4]),absolute_offset=offset,bytes=192,sha256=hashlib.sha256(data).hexdigest()));payload+=data
assert stamp()==expected
assert all(x<0 for x in struct.unpack('<48f',payload[:192]))
(OUT/'controls.f32').write_bytes(payload)
(OUT/'extraction.json').write_text(json.dumps(dict(shard=str(shard),stat_before_after=expected,header_sha256=prior['header_sha256'],data_start=start,placement_sha256=hashlib.sha256(placement.read_bytes()).hexdigest(),auth_sha256=hashlib.sha256(auth.read_bytes()).hexdigest(),payload_sha256=hashlib.sha256(payload).hexdigest(),tensors=records,scope='384B raw F32 controls; gsq_load upload_f32 type0 identity, no synthesize -exp transform.'),indent=2)+'\n')
print('PASS exact384B controls/stat/header/placement',hashlib.sha256(payload).hexdigest())
