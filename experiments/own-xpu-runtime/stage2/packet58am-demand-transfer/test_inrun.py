"""Real parent stream replay through the inherited live driver adapter."""
import importlib.util,json,shutil,tempfile,unittest
from pathlib import Path
from packet_io import P,AH
from analyze import request,stream
class InRun(unittest.TestCase):
    def test_real_stream_deferred_consistency_and_oracle(self):
        spec=importlib.util.spec_from_file_location('screen_stream_gate',P/'screen/analyze.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        prompt='incident-retrospective';source=AH/f'evidence/card0-58ah-b/WS128/run/run/{prompt}'
        with tempfile.TemporaryDirectory(prefix='p58an-inrun-') as tmp:
            out=Path(tmp);folder=out/'run/A0'/prompt;folder.mkdir(parents=True)
            for leaf in ('result.json','timings.jsonl','prefill-timings.jsonl'):shutil.copy2(source/leaf,folder/leaf)
            (folder/'lookup-request-complete.json').write_text('{"passed":true}\n')
            manifest={'prompts':[{'prompt_id':prompt}]}
            self.assertEqual(m.partial(out,manifest,set(),'demand')['complete_exact_requests'],1)
            rows=stream(folder/'timings.jsonl');rows[1]=rows[0]
            (folder/'timings.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            self.assertTrue(m.partial(out,manifest,set(),'demand')['passed'])
            result=json.loads((folder/'result.json').read_text())
            with self.assertRaises(ValueError):request(result,rows,stream(folder/'prefill-timings.jsonl'))
            result['tokens'][0]+=1;(folder/'result.json').write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError,'stream/oracle'):m.partial(out,manifest,set(),'demand')
if __name__=='__main__':unittest.main()
