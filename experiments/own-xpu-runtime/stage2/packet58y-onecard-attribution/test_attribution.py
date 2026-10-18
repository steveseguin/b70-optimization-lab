import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import attribution_gate as A
import batch_gate as B
import views as V
import suite_driver as D
from types import SimpleNamespace

class Attribution(unittest.TestCase):
    def test_single_overlap_view_unchanged_arithmetic(self):
        self.assertEqual(V.bracket('attrib'),[('D0','overlap')])
        self.assertEqual(V.digest('attrib'),V.digest('overlap'))
        command=D.native_command(SimpleNamespace(view='attrib',window='WSCREEN',miss_mode='zerocopy',output=Path('/tmp/unused')),D.oracle_inputs(),Path('/tmp/table'))
        for flag,value in [('--timing','token'),('--attribution','host'),('--max-new','128'),('--retain-steps','none')]:
            self.assertEqual(command[command.index(flag)+1],value)

    def test_missing_or_replaced_pause_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'PAUSE-B'
            with self.assertRaises(ValueError):B.pause_identity(p)
            p.touch();first=B.pause_identity(p);p.unlink();p.write_text('new')
            self.assertNotEqual(first,B.pause_identity(p))
            p.unlink();p.symlink_to(Path(tmp)/'target');(Path(tmp)/'target').touch()
            with self.assertRaises(ValueError):B.pause_identity(p)

    def test_hold_recheck_refuses_change(self):
        with patch.object(B,'pause_identity',return_value={'inode':2}):
            with self.assertRaises(ValueError):B.recheck({'pause':{'inode':1}})

    def test_null_device_time_is_not_zero(self):
        row=dict(schema='packet58y.token.v1',profiling=False,extra_device_waits=0,
            device_class_ms={'compute':0},zero_copy_miss_stall_ms=None)
        with self.assertRaises((ValueError,KeyError)):A.validate(row)


class BatchAdmission(unittest.TestCase):
    def fixture(self,root):
        packet=root/'packet';packet.mkdir();parent=root/'parent';parent.mkdir()
        (packet/'batch-contract.json').write_text(json.dumps({'predecessor_proposals':{}}))
        (parent/'build-receipt.json').write_text('{}')
        paths=[]
        clock=100
        for arm in ('smoke','max'):
            out=parent/'evidence/card0-capacity-a'/arm;out.mkdir(parents=True)
            (out/'queue.json').write_text(json.dumps(dict(passed=True,completed=['K1a','K1b','WSCREEN'],running=None)))
            for stage in ('K1a','K1b','WSCREEN'):
                dest=out/stage;dest.mkdir()
                f=dest/'window.json';f.write_text(json.dumps(dict(passed=True,device_executed=True,child_still_running=False,stop_reasons=[],boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),build_receipt_sha256=B.sha(parent/'build-receipt.json'),started_utc_ns=clock,finished_utc_ns=clock+10)))
                clock+=20
                paths.append(f)
        return packet,parent,paths

    def test_completed_predecessors_same_pause(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);packet,parent,paths=self.fixture(root)
            with patch.object(B,'P',packet),patch.object(B,'P58X',parent),patch.object(B,'ROOT',root),patch.object(B,'pause_identity',return_value=dict(mtime_ns=50,ctime_ns=50)):
                self.assertTrue(B.verify()['passed'])
                for field,value in [('passed',False),('child_still_running',True),('stop_reasons',['fault']),('boot_id','wrong'),('build_receipt_sha256','wrong')]:
                    old=paths[0].read_text();row=json.loads(old);row[field]=value;paths[0].write_text(json.dumps(row))
                    with self.subTest(field=field),self.assertRaises(ValueError):B.verify()
                    paths[0].write_text(old)
                with patch.object(B,'pause_identity',return_value=dict(mtime_ns=101,ctime_ns=50)),self.assertRaises(ValueError):B.verify()
                with patch.object(B,'pause_identity',return_value=dict(mtime_ns=50,ctime_ns=101)),self.assertRaises(ValueError):B.verify()

class TraceIntegrity(unittest.TestCase):
    def row(self,index,token):
        import attribution_schema as S
        return dict(schema='packet58y.token.v1',profiling=False,extra_device_waits=0,
            device_class_ms={n:None for n in S.CLASSES},zero_copy_miss_stall_ms=None,
            host_exclusive_ms={n:0 for n in S.PHASES},host_wait_ms={n:0 for n in S.CAUSES},host_wait_calls={n:0 for n in S.CAUSES},
            residual_ms=1,wall_ms=1,enqueue_class_ms=[0]*10,class_submissions=[0]*10,
            **{n:0 for n in S.COUNTERS if n!='hits'},hits=480,fill_pending_end=False,
            position=index,generated_index=index,token_id=token)

    def test_missing_truncated_reordered_and_mismatch_refuse(self):
        import attribution_schema as S
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace';result=dict(prompt_tokens=2,tokens=[10,11])
            rows=[self.row(0,9),self.row(1,10),self.row(2,11)]
            path.write_text('\n'.join(map(json.dumps,rows))+'\n')
            self.assertTrue(S.check_request(path,result)['passed'])
            for bad in (rows[:-1],rows+rows[:1],[rows[1],rows[0],rows[2]],rows[:2]+[dict(rows[2],token_id=12)],rows[:2]+[dict(rows[2],wall_ms=2)],rows[:2]+[dict(rows[2],hits=479)]):
                path.write_text('\n'.join(map(json.dumps,bad))+'\n')
                with self.assertRaises(ValueError):S.check_request(path,result)
            path.unlink()
            with self.assertRaises(FileNotFoundError):S.check_request(path,result)

    def test_actual_suite_summary_requires_all_twelve_traces(self):
        from test_bracket import SummaryTests
        helper=SummaryTests();helper.manifest=D.oracle_inputs()
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);helper.fixture(out)
            (out/'run/B0').rename(out/'run/D0')
            for entry in helper.manifest['prompts']:
                folder=out/'run/D0'/entry['prompt_id'];result=D.read(folder/'result.json')
                rows=[]
                for position in range(result['prompt_tokens']-1+len(result['tokens'])):
                    index=max(0,position-result['prompt_tokens']+2)
                    row=self.row(position,result['tokens'][index-1] if index else 0)
                    row['generated_index']=index;rows.append(row)
                (folder/'attribution.jsonl').write_text('\n'.join(map(json.dumps,rows))+'\n')
            summary=D.summarize_bracket(out,'attrib',helper.manifest)
            self.assertTrue(summary['attribution_passed'])
            self.assertEqual(len(summary['attribution_checks']),12)
            (folder/'attribution.jsonl').unlink()
            with self.assertRaises(FileNotFoundError):D.summarize_bracket(out,'attrib',helper.manifest)

if __name__=='__main__':unittest.main()
