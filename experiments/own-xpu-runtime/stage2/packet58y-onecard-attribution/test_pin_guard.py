import json,tempfile,unittest
from pathlib import Path
import source_pin_gate as G

class PinClosure(unittest.TestCase):
    def test_external_mutable_and_escape_refuse(self):
        for name in ('experiments/own-xpu-runtime/ops/lane-queue/queue-A.txt',
                     'experiments/own-xpu-runtime/stage2/sibling/build-receipt.json',
                     '../escape','/tmp/escape'):
            with self.subTest(name=name),self.assertRaises(ValueError):G.validate_pins(G.ROOT,{name:'a'*64})

    def test_exact_immutable_input_only(self):
        files=json.loads((G.P/'immutable-inputs.json').read_text())['files']
        name,row=next(iter(files.items()))
        G.validate_pins(G.ROOT,{name:row['sha256']})
        with self.assertRaises(ValueError):G.validate_pins(G.ROOT,{name:'0'*64})

    def test_local_symlink_cannot_escape(self):
        with tempfile.TemporaryDirectory(dir=G.P) as tmp:
            p=Path(tmp)/'escape';p.symlink_to('/tmp')
            with self.assertRaises(ValueError):G.validate_pins(G.P,{str(p.relative_to(G.P)):'0'*64})

    def test_nested_external_pin_refuses(self):
        with tempfile.TemporaryDirectory(dir=G.P) as tmp:
            path=Path(tmp)/'test-seal.json'
            path.write_text(json.dumps({'nested':{'sources':{'experiments/own-xpu-runtime/stage2/sibling/build-receipt.json':'0'*64}}}))
            with self.assertRaises(ValueError):G.validate_metadata()

if __name__=='__main__':unittest.main()
