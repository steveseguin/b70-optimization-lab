"""CPU regression: real bracket_job imports and report for each packet186 row (smoke, control views, U/V3 bracket).
Fixtures live only in scratch; device/process launches are forbidden.
"""
import copy,gzip,json,os,runpy,subprocess,sys,tempfile,types
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent

def probe(index,lane):
 import bracket_job,screen,report_recovery
 from common import D,ROOT,read,save,sha
 from p186_v5_build_engine import save
 from argument_gate import identity as current_identity
 D.oracle_inputs()  # Real manifest changes import path before the late reporter.
 with tempfile.TemporaryDirectory(prefix='p142-report-') as d:
  out=Path(d);source=P.parent/'lineage-inputs/report-fixture'
  from bracket_config import ROWS
  index=int(index);variant=ROWS[index]['variant'];kind=ROWS[index]['kind']
  identity=current_identity(index,lane);proof=read(source/'run/bracket-inputs.json');base=proof['views'][0]
  from conditions import LANES
  identity['conditions']=LANES[lane]
  def audit(event,args):
   if event in ('subprocess.Popen','os.posix_spawn','os.system','os.exec','os.kill','os.killpg'):raise AssertionError('CPU report attempted execution')
   if event=='open' and isinstance(args[0],(str,bytes)):
    path=Path(os.fsdecode(args[0])).absolute()
    assert not str(path).startswith(('/dev/dri/','/mnt/')),'device/model read forbidden'
  sys.addaudithook(audit)
  views=[];selections=[]
  for i,choice in enumerate([v['choice'] for v in identity['bracket']['views']]):
   count=identity['bracket']['views'][i]['max_new']
   view=copy.deepcopy(base);dest=out/'run/views'/f'{i:02d}-{choice}'
   selection=copy.deepcopy(identity['bracket']['views'][i]);selection['choice']=choice
   view.update(index=i,choice=choice,selection_sha256=selection['selection_sha256'],output=str(dest),started_utc_ns=100+i*10,finished_utc_ns=105+i*10)
   for boundary in view['boundary']:boundary['selection_sha256']=selection['selection_sha256']
   for rank,r in enumerate(view['boundary']):save(dest/'boundary'/f'boundary-rank{rank}.json',r)
   incident=read(source/'run/views/00-candidate/incident64/receipt.json');save(dest/'incident64/receipt.json',incident);view['incident64']['receipt_sha256']=sha(dest/'incident64/receipt.json')
   for row in view['requests']:
    tokens=D.CHECK.token_record(D.ORACLE/'results'/row['prompt_id'])[:count];ts=[1+j*.02 for j in range(count)]
    row.update(tokens=tokens,token_timestamps=ts,tok_s_1_100_intervals_after_ttft=50.,output_tokens=count,requested_max_new=count)
   for name in ['incident64',*D.CHECK.PROMPT_IDS]:
    destrow=dest/name/'rank1/draft-rows.jsonl';destrow.parent.mkdir(parents=True,exist_ok=True);destrow.write_text(json.dumps(dict(draft_position=1,confirmed_token=1,guess=1,head='synthetic'))+'\n')
    for rank in (0,1):
     folder=dest/name/f'rank{rank}';folder.mkdir(parents=True,exist_ok=True);(folder/'p105-transfers.jsonl').write_text('')
     (folder/'timings.jsonl').write_text('')
   views.append(view);selections.append(selection)
  identity['bracket'].update(kind=kind,views=selections)
  proof.update(kind=kind,views=views);save(out/'run/bracket-inputs.json',proof)
  report=read(source/'run/report-inputs.json');report['lane']=lane;report['requests']=views[-1]['requests'];report['incident64']=views[-1]['incident64'];save(out/'run/report-inputs.json',report)
  save(out/'run/device-isolation.json',dict(passed=True,synthetic_cpu_fixture=True))
  for rank in (0,1):
   bank=read(source/'run/ranks'/f'rank{rank}'/'class-layout.json');bank['class_layout_bank']=variant
   save(out/'run/ranks'/f'rank{rank}'/'class-layout.json',bank)
  seen=[]
  def recover(args):
   seen.append(args.kind)
   result=screen.report_completed(out,dict(started_utc_ns=1,boot_id='CPU-only'),identity,{})
   assert result['passed'] and result['kind']==kind
   return 0
  argv=['bracket_job.py','--variant',variant,'--kind',kind,'--index',str(index),'--lane',lane,'--output',str(out),'--report-only']
  with patch.object(sys,'argv',argv),patch.object(report_recovery,'recover',side_effect=recover):
   try:runpy.run_path(str(P/'bracket_job.py'),run_name='__main__')
   except SystemExit as e:assert e.code==0
  assert seen==[kind]
  summary=read(out/'bracket-summary.json')
  assert summary['kind']==kind and summary['row_index']==index and summary['variant']==variant and summary['s186_decision']['screen_winner'] is False
  assert len(summary['views'])==len(identity['bracket']['views']) and [v['variant'] for v in summary['views']]==[Path(v['selection']).parent.name for v in identity['bracket']['views']]
  return dict(passed=True,kind=kind,row_index=index,variant=variant,s186_decision_outcome=summary['s186_decision']['outcome'],real_entry='bracket_job.py',real_report='screen.report_completed',requests=12*len(views),sys_path=sys.path,device_executed=False,synthetic_fixtures_retained=False)

def main():
 rows=[]
 from bracket_config import ROWS
 for index in range(len(ROWS)):
  for lane in ('A','B'):
    cp=subprocess.run([sys.executable,'-B',str(P/'report_gate.py'),'--probe',str(index),lane],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
    assert cp.returncode==0,cp.stdout+cp.stderr
    rows.append(dict(json.loads(cp.stdout),lane=lane))
 from p186_v5_build_engine import ROOT,save,sha
 save(P/'evidence/report-gate.json',dict(passed=True,device_executed=False,rows=rows,sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'report_gate.py',P/'bracket_job.py',P/'screen.py',P/'p186_v5_compare.py',P/'report_recovery.py',P/'s186_decision.py',P/'analyze.py')}))
 print('Report gate PASS: both lanes, four packet186 rows, real report path (decision INCOMPLETE without real predecessors)')
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 if '--probe' in sys.argv:print(json.dumps(probe(*sys.argv[-2:])))
 else:main()
