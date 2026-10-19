import json,tempfile,unittest
from pathlib import Path
from analyze import GROUPS,analyze,request_split

def fixture(folder,timed=True):
 for rank in (0,1):(folder/f'rank{rank}').mkdir(parents=True,exist_ok=True)
 r0=[];r1=[]
 def host(name,rank,seq,start,ms):return dict(p157_segment=name,rank=rank,sequence=seq,position=seq,start=start,end=start+ms/1000,ms=ms)
 for seq in range(1,64):
  start=100+seq-.9;r0.append(host('remote_reply_wait',0,seq,start,2.));r1.append(host('draft_issue',1,seq,start,1.7 if timed else 1.6))
  if timed:
   offset=0
   for n,g in enumerate(GROUPS):
    duration=(n+1)*1000
    r1.append(dict(p157_device=True,group=g,rank=1,sequence=seq,position=seq,event=n+1,start_ns=seq*1000000+offset,end_ns=seq*1000000+offset+duration));offset+=duration
    r1.append(host(g,1,seq,start+n*.00001,.01))
 for rank,rows in ((0,r0),(1,r1)):(folder/f'rank{rank}/timings.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
 return dict(prompt_id=folder.name,token_timestamps=list(range(100,164)))
class Tests(unittest.TestCase):
 def test_sum_and_groups(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);r=request_split(p,fixture(p/'p'))
   self.assertAlmostEqual(r['device_sum_ms'],.036);self.assertAlmostEqual(r['host_group_sum_ms'],.08);self.assertAlmostEqual(r['host_unassigned_ms'],1.62)
 def test_bracket_rank_and_overhead(self):
  with tempfile.TemporaryDirectory() as d:
   views=[]
   for i,c in enumerate(['control','candidate','control','candidate','control']):
    p=Path(d)/str(i);views.append(dict(index=i,choice=c,output=str(p),requests=[fixture(p/str(j),c=='candidate') for j in range(12)]))
   r=analyze(views);self.assertEqual(r['top_two_levers'][0]['group'],'argmax_publication');self.assertAlmostEqual(r['overhead'][0]['added_host_ms'],.1)
 def test_missing_empty_group_unmatched_duplicate_and_overlap(self):
  for mode in ('missing','empty','group','hostgroup','unmatched','duplicate','overlap','nan','hostsum'):
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as d:
    p=Path(d);req=fixture(p/'p');f=p/'p/rank1/timings.jsonl';rows=[json.loads(x) for x in f.read_text().splitlines()]
    if mode=='missing':f.unlink()
    elif mode=='empty':f.write_text('')
    else:
     dev=next(x for x in rows if x.get('p157_device'))
     if mode=='group':rows=[x for x in rows if x.get('group')!=GROUPS[0]]
     if mode=='hostgroup':rows=[x for x in rows if x.get('p157_segment')!=GROUPS[0]]
     if mode=='unmatched':dev['sequence']=999
     if mode=='duplicate':rows.append(dict(dev))
     if mode=='overlap':dev['end_ns']+=1000000
     if mode=='nan':rows[0]['ms']=float('nan')
     if mode=='hostsum':rows[0]['ms']=.001;rows[0]['end']=rows[0]['start']+.000001
     f.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    with self.assertRaises(ValueError):request_split(p,req)
 def test_control_forbids_events(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);req=fixture(p/'p')
   with self.assertRaises(ValueError):request_split(p,req,timed=False)
 def test_control_and_timestamp_refusal(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);req=fixture(p/'p',False);self.assertIsNone(request_split(p,req,False)['device_sum_ms'])
   req['token_timestamps'][2]=0
   with self.assertRaises(ValueError):request_split(p,req,False)
if __name__=='__main__':unittest.main()
