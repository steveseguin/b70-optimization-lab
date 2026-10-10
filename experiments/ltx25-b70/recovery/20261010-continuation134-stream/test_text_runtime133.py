"""Matched CPU fake runtime cases; native identity is not inferred."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent

class TextRuntime133(unittest.TestCase):
    def test_parent_and_split36_keep_fake_outputs_and_mandatory_reference(self):
        command=[sys.executable,'-B',str(HERE/'harness_runtime.py'),'--frames','145','--anchor','frame',
            '--decoder-graph','1','--anchor-decode','cone','--bencode-overlap','1','--prep-ahead','1',
            '--display-schedule','eager-display','--display-device','xpu:3','--stream-chunks','2',
            '--decode-delay','0','--audio-delay','0','--client-delay','0']
        env=dict(os.environ,LTX_TEXT_RESIDENCY='legacy',LTX_CONE_GRAPH_MEMORY='off',
            LTX_CONE_CAPTURE_RESERVE='parent',LTX_DISPLAY_ALLOCATOR_RELEASE='off',LTX_DISPLAY_WORKER='serial',
            LTX_GC_INTERVAL_SECONDS='10',LTX_SNAPSHOT_DIGEST_CACHE='0',LTX_MAINTENANCE_MODE='parent')
        for key in ('LTX_DISPLAY_REPLICA_TRANSIENT_GIB','LTX_DECODER_GRAPH_POOL_CAP_GB'):env.pop(key,None)
        def run(args,environment):
            result=subprocess.run(args,env=environment,capture_output=True,text=True,timeout=180)
            self.assertEqual(result.returncode,0,result.stdout[-3000:]+result.stderr[-3000:])
            value=json.loads(result.stdout.strip().splitlines()[-1])
            self.assertNotIn('error',value,value.get('error'))
            return value
        off=run(command,env)
        self.assertTrue(off['verdict']['passed'],off['verdict'])
        with tempfile.TemporaryDirectory(prefix='text133-cpu-reference-') as tmp:
            ref=Path(tmp)/'reference.json';ref.write_text(json.dumps(off['cpu_reference_document']))
            on=run(command+['--cpu-reference-json',str(ref)],dict(env,LTX_TEXT_RESIDENCY='split36',LTX_CONE_GRAPH_MEMORY='text-shift'))
        self.assertTrue(on['verdict']['passed'],on['verdict'])
        self.assertEqual(off['cpu_reference_document'],on['cpu_reference_document'])
        self.assertEqual([r['decoded_tensors'] for r in off['chunks']],[r['decoded_tensors'] for r in on['chunks']])
        self.assertEqual(len(off['chunks']),11)
        self.assertTrue(all(r['server_options']['text_residency']=='split36' for r in on['chunks']))
