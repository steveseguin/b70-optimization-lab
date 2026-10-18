#!/usr/bin/env python3
"""Freeze and verify packet38 draft golden bytes; this is not a packet44 pass."""
import argparse,base64,gzip,hashlib,json,struct,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;BASE=P.parent/'packet38-integrated'
NAME='incident-retrospective';ORACLE=P/'draft-baseline-oracle.json'
FILES=('blk.0.qsa.keys.bin','blk.0.qsa.values.bin','blk.0.qsa.raw.bin','blk.0.qsa.pooled.bin','position.bin','final.mix.bf16','logits.bf16')

def digest(raw):return hashlib.sha256(raw).hexdigest()
def sha(path):return digest(Path(path).read_bytes())
def sizes(name,position):
 if name in ('blk.0.qsa.keys.bin','blk.0.qsa.values.bin'):return 256*1024,position*1024
 if name=='blk.0.qsa.raw.bin':return 256*256,position*256
 if name=='blk.0.qsa.pooled.bin':return 64*256,(position//4)*256
 n={'position.bin':4,'final.mix.bf16':5120,'logits.bf16':496640}[name];return n,n

def prepare():
 disk=subprocess.check_output(['nice','-n','19','ionice','-c','3','df','-B1','/'],text=True)
 assert int(disk.splitlines()[-1].split()[3])>=8_050_000_000,'8 GB root floor plus 50 MB reference-write reserve'
 source_names=('build-receipt.json','capture-run-'+NAME+'.json','capture-input-'+NAME+'.json')
 source={n:(BASE/n).read_bytes() for n in source_names}
 build=json.loads(source['build-receipt.json']);capture=json.loads(source['capture-run-'+NAME+'.json'])
 assert build['passed'] and capture['passed'] and not capture['device_executed']
 assert capture['table_sha256']==json.loads(source['capture-input-'+NAME+'.json'])['table_sha256']
 assert build['draft_capture_input_sha256'][NAME]==digest(source['capture-input-'+NAME+'.json'])
 golden=build['draft_capture_fixture_sha256'][NAME];root=Path(capture['output'])
 archive=P/'evidence/draft-baseline-rows.jsonl.gz';archive.parent.mkdir(exist_ok=True)
 rows=[];valid={}
 with archive.open('wb') as compressed:
  with gzip.GzipFile(fileobj=compressed,mode='wb',mtime=0) as output:
   for j in range(85,94):
    for name in FILES:
     key=f'row-{j}/'+name;raw=(root/key).read_bytes();full,keep=sizes(name,j+1)
     assert len(raw)==full and digest(raw)==golden[key],key+' frozen byte identity'
     if name=='position.bin':assert struct.unpack('<i',raw)[0]==j+1
     row=dict(path=key,bytes=full,valid_bytes=keep,sha256=digest(raw),valid_sha256=digest(raw[:keep]))
     valid[key]=row['valid_sha256'];rows.append(row)
     output.write((json.dumps(dict(row,data_b64=base64.b64encode(raw).decode()),separators=(',',':'))+'\n').encode())
 receipt=dict(schema='packet44.draft-baseline-oracle.v1',role='Frozen packet38 CPU golden bytes only; no packet44 pass',
  device_executed=False,context=256,head_rows=list(range(85,94)),fixture_files=63,
  captured_binary_sha256=capture['binary_sha256'],source_directory=str(root),
  source_receipts={n:dict(sha256=digest(raw),gzip_base64=base64.b64encode(gzip.compress(raw,mtime=0)).decode()) for n,raw in source.items()},
  archive=dict(path=str(archive.relative_to(P)),sha256=sha(archive)),rows=rows,valid_fixture_sha256=valid)
 ORACLE.write_text(json.dumps(receipt,indent=2)+'\n');load();print('Frozen and verified',len(rows),'packet38 draft golden files')

def load():
 row=json.loads(ORACLE.read_text());assert row['fixture_files']==63 and row['context']==256 and not row['device_executed']
 sources={}
 for name,item in row['source_receipts'].items():
  raw=gzip.decompress(base64.b64decode(item['gzip_base64']));assert digest(raw)==item['sha256'];sources[name]=json.loads(raw)
 build=sources['build-receipt.json'];capture=sources['capture-run-'+NAME+'.json'];golden=build['draft_capture_fixture_sha256'][NAME]
 assert build['passed'] and capture['passed'] and not capture['device_executed']
 assert capture['table_sha256']==sources['capture-input-'+NAME+'.json']['table_sha256']
 assert capture['binary_sha256']==row['captured_binary_sha256']
 assert build['draft_capture_input_sha256'][NAME]==row['source_receipts']['capture-input-'+NAME+'.json']['sha256']
 archive=P/row['archive']['path'];assert sha(archive)==row['archive']['sha256']
 observed={};metadata=[]
 with gzip.open(archive,'rt') as source:
  for line in source:
   item=json.loads(line);raw=base64.b64decode(item.pop('data_b64'));key=item['path'];directory,name=key.split('/')
   position=int(directory.removeprefix('row-'))+1;assert position in range(86,95) and name in FILES
   full,keep=sizes(name,position)
   assert len(raw)==item['bytes']==full and item['valid_bytes']==keep
   assert digest(raw)==item['sha256']==golden[key] and digest(raw[:keep])==item['valid_sha256']
   if name=='position.bin':assert struct.unpack('<i',raw)[0]==position
   assert key not in observed;observed[key]=item['valid_sha256'];metadata.append(item)
 assert len(observed)==63 and metadata==row['rows'] and observed==row['valid_fixture_sha256']
 return row

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');a=p.parse_args()
 if a.prepare:prepare()
 else:print('Verified frozen reference files:',load()['fixture_files'])
