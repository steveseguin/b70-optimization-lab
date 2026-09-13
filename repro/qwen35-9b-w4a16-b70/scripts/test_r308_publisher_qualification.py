import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

PUBLISHER=Path(__file__).with_name('publish-r308-fixed-depth-image-ghcr.sh')
GATE=PUBLISHER.read_text().split("<<'PY_GATE'\n",1)[1].split('\nPY_GATE',1)[0]
IMAGE='sha256:'+'a'*64

class Tests(unittest.TestCase):
    def test_gate_rejects_pending_wrong_identity_missing_arm_and_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); observed=root/'evidence/rebuild/observed.sha256';observed.parent.mkdir(parents=True)
            observed.write_text('test inventory\n')
            inventory=root/'evidence/inventory/contract.sha256';inventory.parent.mkdir();inventory.write_bytes(observed.read_bytes())
            sha=hashlib.sha256(observed.read_bytes()).hexdigest()
            manifest=[{'path':str(p.relative_to(root)),'sha256':sha,'bytes':p.stat().st_size} for p in (observed,inventory)]
            (root/'source-manifest.json').write_text(json.dumps(manifest))
            pairs={k:{'passed':True,'prompts':12,'tokens':100} for k in ['mtp0-a-vs-mtp0-b','mtp3-a-vs-mtp3-b','mtp3-a-vs-mtp0-a','mtp3-b-vs-mtp0-a']}
            s={'passed':True,'candidate':'r308','image':IMAGE,'scope':{'tensor_parallel_size':1,'mtp_depth':3,'active_requests':1,'max_num_seqs':1},
               'boundary':{f'{m}-{a}':{'passed':True,'actual_numeric_ids_recomputed':True,'cases':20 if a=='oracle' else 26,'rows':60 if a=='oracle' else 52} for m in ('4b','9b') for a in ('oracle','mtp3-a','mtp3-b')},
               'strict4b':pairs,'strict9b':pairs,'inventory_path':str(inventory),
               'rebuild':{'recorded':True,'inventory_equal':True,'files':17,'source_file_hashes_receipt':'evidence/rebuild/observed.sha256','observed_inventory_sha256':sha,'committed_inventory_sha256':sha}}
            def run(data):
                (root/'summary.json').write_text(json.dumps(data))
                return subprocess.run(['python3','-c',GATE,str(root/'summary.json'),IMAGE],capture_output=True,text=True)
            self.assertEqual(run(s).returncode,0)
            for mutate in [lambda x:x.update(passed=False),lambda x:x.update(candidate='r307'),lambda x:x.update(image='sha256:'+'b'*64),lambda x:x.pop('strict4b'),lambda x:x['boundary'].pop('9b-mtp3-b'),lambda x:x['rebuild'].update(inventory_equal=False)]:
                bad=copy.deepcopy(s);mutate(bad)
                self.assertNotEqual(run(bad).returncode,0)
            observed.write_text('tampered')
            self.assertNotEqual(run(s).returncode,0)

if __name__=='__main__':unittest.main()
