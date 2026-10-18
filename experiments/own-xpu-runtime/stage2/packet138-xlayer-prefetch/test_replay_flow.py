"""CPU-only end-to-end layout test; all synthetic outputs stay in TemporaryDirectory."""
import contextlib,gzip,io,json,resource,struct,tempfile,unittest
from array import array
from pathlib import Path
from unittest.mock import patch
import capture_inputs,router_replay as replay

class Flow(unittest.TestCase):
 def test_layout_and_coverage(self):
  with tempfile.TemporaryDirectory(prefix='p138-flow-') as td:
   p=Path(td);(p/'evidence').mkdir();(p/'evidence/capture-inputs.json').write_text('{}')
   entries=[dict(prompt_id=f'p{i}',category=f'c{i%6}',analysis_included=True) for i in range(12)]
   (p/'suite.snapshot.json').write_text(json.dumps(dict(prompts=entries)))
   # Two real-sized files reused by all twelve fixtures. Distinct fields and
   # token/layer sentinels catch rank, stride, row-order and offset mistakes.
   for rank in range(2):
    with (p/f'rank{rank}.bin').open('wb') as f:
     for token in range(48):
      for local in range(24):
       layer=rank*24+local;ids=[(layer*3+token+i)%512 for i in range(10)]
       f.write(b''.join(struct.pack('<III',i,0,2560) for i in ids))
       for field,width in [(1,2560),(2,2560),(3,2560),(4,2560),(5,2560),(6,512)]:
        f.write(struct.pack('<H',field*1000+layer*10+token%10)*width)
   rows=[dict(prompt_id=e['prompt_id'],rank=r,path=f'rank{r}.bin',analysis_included=True) for e in entries for r in (0,1)]
   calls=[]
   class Weights:
    receipts=[];header_receipts=[]
    def router(self,layer):return layer
    def sizes(self):return [dict(layer=i,bytes=1971200) for i in range(48)]
   def run(lib,layer,inputs):
    same=(len(calls)==0 or calls[-1][0]!=layer)
    index=0 if same else calls[-1][1]+1;calls.append((layer,index))
    previous=layer if index==0 else layer-1
    field=1 if index<2 else index
    out=array('H');ids=array('I')
    self.assertEqual(len(inputs),12*48*2560)
    for n in range(12*48):
     token=n%48;expected=field*1000+previous*10+token%10
     self.assertEqual(inputs[n*2560],expected)
     self.assertEqual(inputs[(n+1)*2560-1],expected)
     out.extend([6000+layer*10+token%10]*512)
     ids.extend((layer*3+token+i)%512 for i in range(16))
    return out,ids
   with patch.object(replay,'P',p),patch.object(replay,'ROOT',p),patch.object(replay,'analysis_identity',return_value='fixture-only'),patch.object(replay,'Weights',Weights),patch.object(replay,'library',return_value=None),patch.object(replay,'run_router',side_effect=run),patch.object(capture_inputs,'require_ready',return_value=dict(rows=rows)),contextlib.redirect_stdout(io.StringIO()):
    replay.main(None)
   result=json.loads(gzip.decompress((p/'evidence/router-replay.json.gz').read_bytes()))
   pred=json.loads(gzip.decompress((p/'evidence/predictions.json.gz').read_bytes()))
   self.assertTrue(result['passed']);self.assertEqual(result['analysis_seal_sha256'],'fixture-only');self.assertEqual(len(calls),48+47*5)
   self.assertEqual(len(result['oracle']),48);self.assertEqual(len(result['per_prompt_layer']),12*47*5*3)
   self.assertEqual(len(pred['rows']),12*47*5);self.assertEqual(len(pred['truth']),12)
   self.assertTrue(all(r['recall']==1 for r in result['predictors']))
   self.assertEqual(pred['truth']['p11'][47][47],[(47*3+47+i)%512 for i in range(10)])
   self.assertEqual(json.loads((p/'evidence/analysis-status.json').read_text())['status'],'exact_replay_complete')

if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));unittest.main()
