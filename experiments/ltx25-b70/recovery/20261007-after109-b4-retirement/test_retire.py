"""Synthetic files only; no real raw hashing, process inspection or model imports."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('old97_b4_retire',Path(__file__).with_name('retire.py'))
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
# Bounded historical JSON only, never raw tensors or process state.
ORIGINAL_THROUGHPUT=M.THROUGHPUT.read_bytes()
assert M.hashlib.sha256(ORIGINAL_THROUGHPUT).hexdigest()==M.PINS['throughput']
ORIGINAL_EMITTED=[r for r in json.loads(ORIGINAL_THROUGHPUT)['rows'] if r['fill'] is False]


class Controls(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.top=Path(temp.name)
        root=self.top/'artifacts';root.mkdir();self.root=root
        for key,value in [('ROOT',root),('RUN',root/'old-run'),('PACKET',root/'packet'),
                          ('DATA',self.top/'metadata'),('THROUGHPUT',self.top/'historical-throughput.json'),('PINS',dict(M.PINS))]:
            ctx=patch.object(M,key,value);ctx.start();self.addCleanup(ctx.stop)
        M.RUN.mkdir();M.DATA.mkdir();M.THROUGHPUT.write_bytes(ORIGINAL_THROUGHPUT)
        self.exists=patch.object(M,'process_exists',return_value=False);self.proc=self.exists.start();self.addCleanup(self.exists.stop)
        self.identity={'pid':M.PID,'proc_start_ticks':M.START,'boot_id':M.BOOT,
            'source_packet_path':str(M.PACKET),'source_packet_manifest_sha256':M.PINS['manifest']}
        M.exclusive_json(M.RUN/'server-identity.json',self.identity)
        M.PINS['identity']=M.fp(M.RUN/'server-identity.json')['sha256']
        self.base={'server_identity':self.identity,'retire':[],'keep_first_per_fixture':[],
                   'raw_files':[],'evidence':[],'prefix':M.PREFIX,
                   'validation':{'completed_prompts':600,'exact_emitted_clips':587}}
        records={}
        for original in ORIGINAL_EMITTED:
            i=original['index'];fixture=original['emitted_fixture'];a=original['prompt'];b=original['reference']
            for name in (a,b):
                p=M.archive(name)
                if not p.exists():p.parent.mkdir(parents=True);p.write_bytes(('archive-'+fixture).encode())
                records[str(p)]=M.fp(p)
            row={'fixture':fixture,'candidate':records[str(M.archive(a))],'reference':records[str(M.archive(b))]}
            self.base['keep_first_per_fixture' if i<23 else 'retire'].append(row)
        self.base['raw_files']=list(records.values())
        self.evidence={p:r for p,r in records.items()}
        self.original_reconstruct=M.reconstruct
        ctx=patch.object(M,'reconstruct',return_value=(self.base,self.evidence))
        self.proof=ctx.start();self.addCleanup(ctx.stop)
        self.plan=M.build_plan();self.path=self.top/'plan.json';M.exclusive_json(self.path,self.plan)
        self.digest=M.fp(self.path)['sha256'];self.receipt=self.top/'applied.json'

    def apply(self):M.operate('apply',self.path,self.digest,self.receipt)

    def test_exact_scope_roundtrip_protects_refs_first10_and_unrelated109(self):
        live=self.root/'requests/resolution-duration109-20261007';live.mkdir(parents=True)
        sentinel=live/'protected';sentinel.write_text('live109 untouched')
        self.assertEqual(len(self.plan['retire']),577)
        self.assertEqual(len(M.protected()),20)
        self.assertEqual(len({r['retained']['path'] for r in self.plan['retire']}),10)
        protected={p:M.fp(p) for p in M.protected()}
        self.apply();self.assertEqual(self.proof.call_count,2)
        self.assertEqual(M.read_json(self.receipt)['status'],'completed')
        self.assertTrue(all(not Path(r['candidate']['path']).exists() for r in self.plan['retire']))
        with patch.object(M,'storage_admission',return_value={'admitted':True}):
            M.operate('restore',self.path,self.digest,self.top/'restored.json')
        for row in self.plan['retire']:
            a,b=M.fp(row['candidate']['path']),M.fp(row['retained']['path'])
            self.assertEqual(a['sha256'],b['sha256']);self.assertEqual(a['st_nlink'],1)
            self.assertNotEqual(a['st_ino'],b['st_ino'])
        self.assertEqual(protected,{p:M.fp(p) for p in protected})
        self.assertEqual(sentinel.read_text(),'live109 untouched')
        self.assertTrue(all(call.args==(2241785,) for call in self.proc.call_args_list))

    def test_mapping_matches_actual_pinned_rotating_campaign_not_modulo_suffix(self):
        expected=[(r['prompt'],r['reference'],r['emitted_fixture']) for r in ORIGINAL_EMITTED[10:]]
        self.assertEqual(M.selection(),expected)
        mapped={a:(b,f) for a,b,f in M.selection()}
        self.assertEqual(mapped[M.PREFIX+'-23'],('stability-01-b4-marble','marble'))
        self.assertEqual(mapped[M.PREFIX+'-32'],('stability-01-b4-boat','boat'))
        self.assertEqual(mapped[M.PREFIX+'-33'],('stability-01-b4-bird','bird'))
        self.assertTrue(any(f != M.FIXTURES[(int(n.rsplit('-',1)[1])-13)%10] for n,_,f in expected))
        value=json.loads(ORIGINAL_THROUGHPUT)
        value['rows'][23]['reference']='stability-01-b4-boat'
        M.THROUGHPUT.write_bytes(M.canonical(value))
        with self.assertRaisesRegex(RuntimeError,'fixture-order source'):M.selection()
        M.PINS['throughput']=M.fp(M.THROUGHPUT)['sha256']
        with self.assertRaisesRegex(RuntimeError,'fixture/reference mapping'):M.selection()

    def test_old_owner_alive_or_reused_refuses_before_proof(self):
        self.proc.return_value=True;self.proof.reset_mock()
        with self.assertRaisesRegex(RuntimeError,'PID still exists'):self.apply()
        self.proof.assert_not_called();self.assertFalse(self.receipt.exists())

    def test_owner_identity_source_and_start_cannot_be_relabelled(self):
        p=M.RUN/'server-identity.json'
        for key,value in [('pid',3380321),('proc_start_ticks','0'),('boot_id','other'),('source_packet_path','/wrong')]:
            d=dict(self.identity);d[key]=value;p.write_bytes(M.canonical(d));M.PINS['identity']=M.fp(p)['sha256']
            with self.assertRaisesRegex(RuntimeError,'PID/start/boot/source'):M.build_plan()

    def test_proof_failure_or_drift_precedes_intent_and_unlink(self):
        self.proof.side_effect=RuntimeError('original exact comparator refused')
        with self.assertRaisesRegex(RuntimeError,'exact comparator'):self.apply()
        self.assertFalse(self.receipt.with_name('applied.json.intent.json').exists())
        self.assertTrue(all(Path(r['candidate']['path']).exists() for r in self.plan['retire']))

    def test_whole_byte_drift_or_equal_replacement_after_proof_refused(self):
        row=self.plan['retire'][0];Path(row['candidate']['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'after comparison'):self.apply()
        Path(row['retained']['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'after comparison'):M.build_plan()
        self.assertFalse(self.receipt.with_name('applied.json.intent.json').exists())

    def test_missing_symlink_hardlink_archive_refused(self):
        row=self.plan['retire'][0];p=Path(row['candidate']['path']);raw=p.read_bytes()
        p.unlink()
        with self.assertRaisesRegex(RuntimeError,'missing path'):self.apply()
        p.symlink_to(row['retained']['path'])
        with self.assertRaisesRegex(RuntimeError,'symlink'):self.apply()
        p.unlink();p.write_bytes(raw);alias=self.top/'hardlink';os.link(p,alias)
        with self.assertRaisesRegex(RuntimeError,'nlink1'):self.apply()

    def test_wrong_candidate_keeper_and_digest_refused(self):
        with self.assertRaisesRegex(RuntimeError,'plan SHA'):
            M.operate('apply',self.path,'0'*64,self.receipt)
        for side in ('candidate','retained'):
            plan=copy.deepcopy(self.plan);plan['retire'][0][side]['path']=str(self.root/'unrelated109')
            self.path.write_bytes(M.canonical(plan))
            with self.assertRaisesRegex(RuntimeError,'restoration mapping'):
                M.checked_plan(self.path,M.fp(self.path)['sha256'])

    def test_partial_failure_has_durable_intent_and_prefix_no_retry(self):
        original=M.unlink_exact;calls=[]
        def fail(record):
            calls.append(record)
            if len(calls)==2:raise OSError('synthetic unlink failure')
            return original(record)
        with patch.object(M,'unlink_exact',side_effect=fail):
            with self.assertRaises(OSError):self.apply()
        receipt=M.read_json(self.receipt)
        self.assertEqual(receipt['status'],'incomplete-no-automatic-retry')
        self.assertEqual(len(receipt['completed']),1)
        events=self.receipt.with_name('applied.json.events.jsonl').read_text().splitlines()
        self.assertEqual([json.loads(v)['phase'] for v in events],['file-intent','file-completed','file-intent'])
        self.assertEqual(M.read_json(self.receipt.with_name('applied.json.intent.json'))['plan'],self.plan)
        with self.assertRaises(RuntimeError):self.apply()

    def test_restore_headroom_and_overwrite_refused(self):
        self.apply();receipt=self.top/'restore.json'
        with patch.object(M,'storage_admission',side_effect=RuntimeError('storage refused')):
            with self.assertRaisesRegex(RuntimeError,'storage refused'):M.operate('restore',self.path,self.digest,receipt)
        self.assertFalse(receipt.with_name('restore.json.intent.json').exists())
        p=Path(self.plan['retire'][0]['candidate']['path']);p.write_bytes(b'partial retained')
        with self.assertRaisesRegex(RuntimeError,'destination exists'):M.operate('restore',self.path,self.digest,receipt)
        self.assertEqual(p.read_bytes(),b'partial retained')

    def test_restore_budget_actual_filesystem50GiB_plus_all577_and_margin(self):
        def inspect(path,floor,writes):
            self.assertEqual(path,self.root/'output/validation');self.assertEqual(floor,50*2**30)
            self.assertEqual(writes,577*4096+16*2**20);return {'admitted':False}
        with patch.object(M,'load',return_value=types.SimpleNamespace(inspect_destination=inspect)):
            with self.assertRaisesRegex(RuntimeError,'admission refused'):M.storage_admission(self.plan['retire'])

    def test_fresh_original_gate_dispatch_all587_not_passed_boolean(self):
        for row in ORIGINAL_EMITTED:
            M.exclusive_json(M.DATA/(row['prompt']+'-parity.json'),{'status':'passed','fixture':row['emitted_fixture']})
        seen=[]
        def compare(ref,name):
            seen.append((ref,name));return M.read_json(M.DATA/(name+'-parity.json'))
        with patch.object(M,'source_evidence',return_value={}),patch.object(M.B,'build_plan',return_value=self.base),\
             patch.object(M,'replay_comparator',side_effect=compare):
            self.original_reconstruct()
        self.assertEqual(len(seen),587)
        self.assertEqual(seen[0],('stability-01-b4-boat',M.PREFIX+'-13'))
        self.assertEqual(seen[-1][1],M.PREFIX+'-599')
        with patch.object(M,'source_evidence',return_value={}),patch.object(M.B,'build_plan',return_value=self.base),\
             patch.object(M,'replay_comparator',return_value={'status':'failed'}):
            with self.assertRaisesRegex(RuntimeError,'fresh comparator report'):self.original_reconstruct()

    def test_original_comparator_execution_restores_argv_and_refuses_failure(self):
        comparator=self.top/'compare-clip.py';comparator.write_text('# synthetic source only\n')
        M.PINS['comparator']=M.fp(comparator)['sha256'];previous=sys.argv
        def run(path,run_name):
            self.assertEqual(path,str(comparator));self.assertEqual(run_name,'__main__')
            self.assertEqual(sys.argv[1:3],['reference','candidate'])
            Path(sys.argv[-1]).write_text('{"status":"passed"}')
            raise SystemExit(0)
        with patch.object(M,'COMPARATOR',comparator),patch.object(M.runpy,'run_path',side_effect=run):
            self.assertEqual(M.replay_comparator('reference','candidate'),{'status':'passed'})
        self.assertIs(sys.argv,previous)

        with patch.object(M,'COMPARATOR',comparator),patch.object(M.runpy,'run_path',side_effect=SystemExit(1)):
            with self.assertRaisesRegex(RuntimeError,'comparator failed'):M.replay_comparator('reference','candidate')
        self.assertIs(sys.argv,previous)

    def test_python_optimization_refused_before_comparator_or_payload_read(self):
        with patch.object(M.sys,'flags',types.SimpleNamespace(optimize=1)),\
             patch.object(M,'fp') as fingerprint,patch.object(M.runpy,'run_path') as run:
            with self.assertRaisesRegex(RuntimeError,'disables original comparator assertions'):
                M.replay_comparator('reference','candidate')
        fingerprint.assert_not_called();run.assert_not_called()

    def test_source_campaign_and_prereg_hashes_are_required_before_proof(self):
        M.PACKET.mkdir()
        paths={'manifest':M.PACKET/'manifest.json','summary':M.DATA/'summary.json',
               'throughput':M.DATA/'throughput.json','prereg':M.DATA/'prereg.json'}
        docs={'manifest':{'files':{}},'summary':{'run':str(M.RUN),'batch':4,'missing_or_failed':[],
                'context_sentry_gate_passed':True,'arms':{M.PREFIX:{'all_exact':True,'exact':587,
                'clips_verified':587,'prompts':600}}},
              'throughput':{'server_run':str(M.RUN),'prefix':M.PREFIX,'batch':4,'count':600,
                'distinct_clips_emitted':587,'references_from':str(paths['prereg'])},
              'prereg':{'fixtures':[{'id':f,'reference':'stability-01-b4-'+f} for f in M.FIXTURES]}}
        for key,path in paths.items():
            M.exclusive_json(path,docs[key]);M.PINS[key]=M.fp(path)['sha256']
        with patch.object(M,'SUMMARY',paths['summary']),patch.object(M,'THROUGHPUT',paths['throughput']),\
             patch.object(M,'PREREG',paths['prereg']):
            evidence=M.source_evidence()
            self.assertTrue(all(str(p) in evidence for p in paths.values()))
            old=paths['summary'].read_bytes();paths['summary'].write_bytes(old+b' ')
            with self.assertRaisesRegex(RuntimeError,'pinned source differs: summary'):M.source_evidence()
            paths['summary'].write_bytes(old)
            docs['summary']['arms'][M.PREFIX]['exact']=586
            paths['summary'].write_bytes(M.canonical(docs['summary']))
            M.PINS['summary']=M.fp(paths['summary'])['sha256']
            with self.assertRaisesRegex(RuntimeError,'timed census'):M.source_evidence()


if __name__=='__main__':unittest.main()
