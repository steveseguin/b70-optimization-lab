import copy
import importlib.util
from pathlib import Path
import struct
import unittest
import sys
import tempfile
import json
sys.path.insert(0,str(Path(__file__).parent))
import prepare

spec=importlib.util.spec_from_file_location('dedicated_compare',Path(__file__).with_name('compare.py'))
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)

def commands():
    hidden='ab'*32;request='cd'*32;prefix='ef'*32
    row=dict(token=11,position=1,fixture=1,epoch=0,id=3,parent=2,request=request,after=prefix)
    proposal=struct.pack('<4I6Q8i32s32s32s',0x44525032,2,224,3,0,1,3,2,7,1,1,1,3,3,21,22,0,1,
        bytes.fromhex(request),bytes.fromhex(prefix),bytes.fromhex(hidden))+struct.pack('<i',23)+bytes(28)
    result=dict(provider_serial=1,seed_position=1,restored_position=1,parent_hidden_sha256=hidden,restored=True,
        proposal_hex=proposal.hex(),proposal_sha256=C.sha256(proposal).hexdigest(),final_commit=7,available_depth=3,
        guesses=[21,22,23],reply_hex=struct.pack('<8i4d',0,21,0,224,1,-1,0x50525631,1,0.,0.,0.,0.).hex())
    return [dict(owner='provider',event='issued',sequence=1,row=row,
        request_hex=struct.pack('<8i',27,11,1,1,3,1,0x50525631,1).hex(),parent_hidden_sha256=hidden),
        dict(owner='provider',event='completed',sequence=1,provider=result)]

class PairProof(unittest.TestCase):
    def test_actual_native_pair(self):
        self.assertEqual(C.canonical_pairs(commands(),2),[dict(position=1,token=11,hidden_bytes=40960,hidden_sha256='ab'*32)])
    def test_missing_completion(self):
        with self.assertRaises(ValueError):C.canonical_pairs(commands()[:1],2)
    def test_hidden_mutation(self):
        rows=commands();rows[0]['parent_hidden_sha256']='00'*32
        with self.assertRaises(ValueError):C.canonical_pairs(rows,2)
    def test_native_serial_mutation(self):
        rows=commands();raw=bytearray.fromhex(rows[1]['provider']['proposal_hex']);raw[56]=2
        rows[1]['provider']['proposal_hex']=raw.hex();rows[1]['provider']['proposal_sha256']=C.sha256(raw).hexdigest()
        with self.assertRaises(ValueError):C.canonical_pairs(rows,2)
    def test_reply_failure(self):
        rows=commands();raw=bytearray.fromhex(rows[1]['provider']['reply_hex']);raw[0]=1;rows[1]['provider']['reply_hex']=raw.hex()
        with self.assertRaises(ValueError):C.canonical_pairs(rows,2)
    def test_duplicate_command(self):
        rows=commands();rows.append(copy.deepcopy(rows[0]))
        with self.assertRaises(ValueError):C.canonical_pairs(rows,2)

class ManifestPaths(unittest.TestCase):
    def test_actual_retained_paths_and_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);output=root/'output';output.mkdir();reference=root/'reference';reference.mkdir()
            rows=commands();(output/'commands.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            (output/'driver-result.json').write_text(json.dumps(dict(input_position=2,output_ids=[21])))
            stages=[]
            for i,(begin,end) in enumerate(((0,17),(17,33),(33,48))):
                native=output/f'stage{i}'/'native';native.mkdir(parents=True)
                (native/'receipt.json').write_text('{"passed":true}')
                stages.append(dict(id=i,begin=begin,end=end,native_output=str(native)))
            provider=output/'stageprovider'/'native';provider.mkdir(parents=True)
            (provider/'provider-dump-2').mkdir();(provider/'receipt.json').write_text('{"passed":true}')
            identity=dict(model_sha256='11'*32,draft_model_sha256='22'*32,pair_sequence_sha256='33'*32,position=1,arithmetic='F32-target/BF16-draft')
            (reference/'draft-set.json').write_text(json.dumps(dict(input_identity=identity)))
            plan=root/'plan.json';plan.write_text(json.dumps(dict(output=str(output),stages=stages,provider=dict(native_output=str(provider)),model_identity_sha256='11'*32,draft_model_sha256='22'*32)))
            result=prepare.prepare(plan,reference,root/'comparison');manifest=json.loads(result.read_text())
            self.assertTrue(manifest['stages'][0]['dump'].endswith('stage0/native/state-2147483647'))
            draft=json.loads(Path(manifest['draft_set']).read_text())
            self.assertEqual(draft['dump'],str(provider/'provider-dump-2'))
            self.assertEqual(len(manifest['process_receipts']),4)
            self.assertNotEqual(draft['input_identity']['pair_sequence_sha256'],identity['pair_sequence_sha256'])
            with self.assertRaises(FileExistsError):prepare.prepare(plan,reference,root/'comparison')

if __name__=='__main__':unittest.main()
