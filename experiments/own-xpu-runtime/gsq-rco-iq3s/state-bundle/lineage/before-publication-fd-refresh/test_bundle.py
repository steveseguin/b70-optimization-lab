import hashlib,importlib.util,json,os,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import reader
P=Path(__file__).resolve().parent;BINARY=Path(os.environ['BUNDLE_TEST_BINARY'])
def run(mode,path,passed=True):
 r=subprocess.run([str(BINARY),mode,str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=10)
 if passed:assert r.returncode==0,(r.returncode,r.stderr)
 else:assert r.returncode!=0,r.stdout
 return r
def expected():
 a=bytes((i*37+11)%256 for i in range(70001));b=bytes([0,255,17,128]);hashes={'tensor.bin':reader.digest(a),'alternate-carry.bin':reader.digest(b)}
 state='{"history0":1,"history1":2,"buffers":{"tensor":"'+hashes['tensor.bin']+'","alternate:carry":"'+hashes['alternate-carry.bin']+'"},"fp32_cache_valid":false,"fp32_extent":0}'
 return {**hashes,'state.json':reader.digest(state.encode())},state.encode()
def snap(p):return {f.name:(f.stat().st_ino,f.stat().st_size,f.stat().st_mtime_ns,reader.digest(f.read_bytes())) for f in p.iterdir()}
def reseal(p):
 lines=(p/'state-seal.txt').read_text().splitlines();lines[1]=str((p/'state.bundle').stat().st_size);lines[2]=reader.digest((p/'state.bundle').read_bytes());lines[3]=reader.digest((p/'state-index.tsv').read_bytes());lines[4]=reader.digest((p/'state.json').read_bytes());(p/'state-seal.txt').write_text('\n'.join(lines)+'\n')
class BundleTests(unittest.TestCase):
 def test_full_legacy_map_and_exact_json(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'state';run('create',p);h,state=expected();self.assertEqual(h,reader.read_state(p));self.assertEqual(state,(p/'state.json').read_bytes());self.assertEqual(reader.FILES,set(x.name for x in p.iterdir()))
 def test_repeat_dump_never_overwrites(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'state';run('create',p);before=snap(p);run('repeat',p);self.assertEqual(before,snap(p));self.assertEqual(expected()[0],reader.read_state(p))
 def test_current_changed_or_missing_preserves_old(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'state';run('create',p);before=snap(p)
   for mode in ('mismatch','metadata-mismatch','missing','duplicate'):
    with self.subTest(mode=mode):run(mode,p,False);self.assertEqual(before,snap(p))
 def test_corrupted_stored_bytes_even_resealed_refuse_repeat(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'state';run('create',p);f=p/'state.bundle';b=bytearray(f.read_bytes());b[10]^=1;f.write_bytes(b);reseal(p);run('repeat',p,False)
   with self.assertRaises(ValueError):reader.read_state(p)
 def test_partial_failures_refuse_success_and_preserve(self):
  for point in ('before-write','after-write','payload-fsync','closed','file-fsync','publication-linked','data-directory-fsync','seal-directory-fsync'):
   with self.subTest(point=point),tempfile.TemporaryDirectory() as t:
    p=Path(t)/'state';r=run('fail:'+point,p,False);self.assertIn('injected '+point,r.stderr);self.assertTrue(list(p.iterdir()))
    if point!='seal-directory-fsync':
     self.assertFalse((p/'state-seal.txt').exists());run('create',p,False)
     if point=='publication-linked':
      a=(p/'state.bundle').stat();b=(p/'state.bundle.partial').stat();self.assertEqual((a.st_ino,a.st_nlink),(b.st_ino,2))
      with self.assertRaises(ValueError):reader.read_state(p)
    else:self.assertEqual(expected()[0],reader.read_state(p)) # bytes valid; failed RPC still forbids operation success
 def test_index_refusals_after_rebinding_metadata_hash(self):
  for kind in ('duplicate','gap','overlap','range','missing','unknown','negative','leading-zero','extra-field'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as t:
    p=Path(t)/'state';run('create',p);lines=(p/'state-index.tsv').read_text().splitlines();rows=[x.split('\t') for x in lines[1:]]
    if kind=='duplicate':rows[1][0]=rows[0][0]
    if kind=='gap':rows[1][1]='70002'
    if kind=='overlap':rows[1][1]='70000'
    if kind=='range':rows[1][2]=str(reader.CAP)
    if kind=='missing':rows.pop()
    if kind=='unknown':rows[1][0]='other.bin'
    if kind=='negative':rows[0][1]='-1'
    if kind=='leading-zero':rows[0][1]='00'
    if kind=='extra-field':rows[1].append('extra')
    (p/'state-index.tsv').write_text(lines[0]+'\n'+'\n'.join('\t'.join(x) for x in rows)+'\n');reseal(p)
    with self.assertRaises(ValueError):reader.read_state(p)
 def test_payload_tail_truncation_and_json_duplicate(self):
  for kind in ('tail','truncated','json-duplicate'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as t:
    p=Path(t)/'state';run('create',p)
    if kind=='json-duplicate':f=p/'state.json';s=f.read_text();f.write_text(s.replace('"history0":1','"history0":1,"history0":1'))
    else:f=p/'state.bundle';b=f.read_bytes();f.write_bytes(b+b'x' if kind=='tail' else b[:-1])
    reseal(p)
    with self.assertRaises(ValueError):reader.read_state(p)
 def test_symlink_and_hardlink_refusal(self):
  for kind in ('symlink','hardlink'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as t:
    p=Path(t)/'state';run('create',p);f=p/'state.bundle';other=Path(t)/'other'
    if kind=='symlink':f.rename(other);f.symlink_to(other)
    else:os.link(f,other)
    with self.assertRaises((ValueError,OSError)):reader.read_state(p)
 def test_bound_adapter_dump_then_reset_then_last_finish(self):
  s=importlib.util.spec_from_file_location('state_bundle_test_adapter',P/'generated/adapter.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
  class HostRPC:
   def __init__(self,path):self.request_output=path;self.calls=[];self.pending=[False,False];self.out=path;self.seq=[0,0];self.mapping=bytearray(a.BASE.SHARED);self.children=[]
   def call(self,rank,op,**kw):
    self.calls.append((rank,op));run('repeat' if (self.request_output/f'rank{rank}/state-2147483647/state-seal.txt').exists() else 'create',self.request_output/f'rank{rank}/state-2147483647')
  with tempfile.TemporaryDirectory() as t:
   transport=HostRPC(Path(t));first=a.state_hashes(transport);self.assertEqual({'0':expected()[0],'1':expected()[0]},first)
   before={rank:snap(Path(t)/f'rank{rank}/state-2147483647') for rank in (0,1)}
   # Actual Writer's repeated capture models the inherited RESET-before-clear and last FINISH boundary.
   for rank in (0,1):transport.call(rank,11)
   self.assertEqual(first,a.state_hashes(transport))
   for rank in (0,1):transport.call(rank,a.BASE.FINISH)
   self.assertEqual(before,{rank:snap(Path(t)/f'rank{rank}/state-2147483647') for rank in (0,1)})
   self.assertEqual(8,len(transport.calls))
if __name__=='__main__':unittest.main(verbosity=2)
