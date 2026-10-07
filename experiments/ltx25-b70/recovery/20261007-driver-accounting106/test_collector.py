import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('collector', Path(__file__).with_name('collector.py'))
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.proc = self.root/'proc'; self.base = self.proc/'17'
        for name in ['fd', 'fdinfo', 'task/17']:
            (self.base/name).mkdir(parents=True)
        (self.proc/'sys/kernel/random').mkdir(parents=True)
        (self.proc/'sys/kernel/random/boot_id').write_text('boot\n')
        (self.base/'stat').write_text('17 (name with ) spaces) '+' '.join(['S']+['0']*18+['42']))
        (self.base/'task/17/children').write_text('')
        packet=self.root/'packet'; (packet/'resolution').mkdir(parents=True)
        run=self.root/'server';run.mkdir()
        plan={'plan':{'qualification_id':'q'*64}}
        plan['plan_sha256']=C.digest(C.canonical(plan['plan']))
        plan_path=packet/'resolution/candidate-plan.json';plan_path.write_bytes(C.canonical(plan))
        manifest={'resolution101':{'plan_sha256':plan['plan_sha256']},
                  'files':{'resolution/candidate-plan.json':C.digest(plan_path.read_bytes())}}
        manifest_path=packet/'manifest.json';manifest_path.write_bytes(C.canonical(manifest))
        identity=dict(pid=17,proc_start_ticks='42',boot_id='boot',source_packet_path=str(packet),
                      source_packet_manifest_sha256=C.digest(manifest_path.read_bytes()),
                      devices=[dict(ordinal=0,properties='synthetic XPU properties')])
        identity_path=run/'server-identity.json';identity_path.write_bytes(C.canonical(identity))
        mapping_path=self.root/'mapping.json';evidence=self.root/'reviewed-mapping.txt';evidence.write_text('synthetic existing evidence')
        order=[dict(ordinal=0,render_node='/dev/dri/renderD128',pci='0000:23:00.0',
                    properties_sha256=C.digest(identity['devices'][0]['properties'].encode()))]
        self.c=dict(schema='ltx.raw-drm-accounting.v1',pid=17,start_ticks='42',boot_id='boot',
                    collector_sha256=C.digest(Path(C.__file__).read_bytes()),
                    runtime_manifest_sha256=C.digest(manifest_path.read_bytes()),
                    plan_sha256=plan['plan_sha256'],qualification_id=plan['plan']['qualification_id'],
                    render_nodes={'/dev/dri/renderD128':'0000:23:00.0'},ordered_xpu_mapping=order,
                    fault_paths=[str(self.root/'FAULT.json'),str(run/'FAULT.json'),str(run/'resolution-halt.json')],bindings={})
        mapping=dict(schema='ltx.reviewed-render-xpu-map.v1',review_method='reviewed-existing-evidence',
                     server_identity_sha256=C.digest(identity_path.read_bytes()),
                     runtime_manifest_sha256=self.c['runtime_manifest_sha256'],plan_sha256=self.c['plan_sha256'],
                     render_nodes=self.c['render_nodes'],ordered_xpu_mapping=order,
                     evidence_sources=[dict(path=str(evidence),sha256=C.digest(evidence.read_bytes()))])
        mapping_path.write_bytes(C.canonical(mapping))
        for name,path in [('plan',plan_path),('server_identity',identity_path),('mapping_evidence',mapping_path),('runtime_manifest',manifest_path)]:
            self.c['bindings'][name]=dict(path=str(path),sha256=C.digest(path.read_bytes()))
        self.fd(8,99);self.collector=C.Collector(self.c,self.proc)

    def fd(self,n,client,busy=100,total=1000,capacity=None):
        p=self.base/'fd'/str(n)
        if not p.is_symlink():p.symlink_to('/dev/dri/renderD128')
        text=f'drm-driver: xe\ndrm-client-id: {client}\ndrm-pdev: 0000:23:00.0\n'
        for e in ['ccs','bcs']:
            text+=f'drm-cycles-{e}: {busy}\ndrm-total-cycles-{e}: {total}\n'
            if capacity is not None:text+=f'drm-engine-capacity-{e}: {capacity}\n'
        (self.base/'fdinfo'/str(n)).write_text(text)

    def test_contract_pins_and_identity(self):
        p=self.root/'contract.json';p.write_text(json.dumps(self.c));sha=C.digest(p.read_bytes())
        self.assertEqual(C.load_contract(p,sha),self.c)
        with self.assertRaisesRegex(ValueError,'digest'):C.load_contract(p,'0'*64)
        Path(self.c['bindings']['plan']['path']).write_text('changed')
        with self.assertRaisesRegex(ValueError,'Bound source'):C.load_contract(p,sha)

    def test_raw_counters_dedup_default_capacity(self):
        self.fd(9,99);self.fd(10,100,busy=0)
        row=self.collector.snapshot()
        self.assertTrue(row['complete']);self.assertEqual(len(row['clients']),2)
        v=row['clients']['0000:23:00.0/99']['engines']['bcs']
        self.assertEqual(v['busy'],100);self.assertEqual(v['total'],1000)
        self.assertTrue(v['capacity_defaulted']);self.assertEqual(v['capacity'],1)

    def test_regression_keeps_watermark_until_catchup(self):
        self.collector.snapshot()
        for value,high,incomplete in [(90,100,True),(95,100,True),(110,110,False)]:
            self.fd(8,99,busy=value,total=1000+value)
            row=self.collector.snapshot();v=row['clients']['0000:23:00.0/99']['engines']['ccs']
            self.assertEqual(v['busy'],value);self.assertEqual(v['busy_watermark'],high)
            self.assertEqual('busy-below-watermark' in row['issues'],incomplete)

    def test_client_capacity_missing_and_coverage(self):
        self.collector.snapshot();self.fd(8,99,total=1001,capacity=2)
        self.assertIn('capacity-changed',self.collector.snapshot()['issues'])
        self.fd(8,100,total=1002)
        self.assertIn('client-set-changed',self.collector.snapshot()['issues'])
        p=self.base/'fdinfo/8';p.write_text(p.read_text().replace('drm-cycles-bcs: 100\n',''))
        row=self.collector.snapshot();self.assertIn('missing-bcs-busy',row['issues'])
        self.assertIsNone(row['clients']['0000:23:00.0/100']['engines']['bcs']['busy'])
        (self.base/'task/17/children').write_text('777')
        self.assertIn('uncovered-child-processes',self.collector.snapshot()['issues'])

    def test_fault_identity_and_boundaries(self):
        (self.root/'FAULT.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'Fault'):self.collector.snapshot()
        (self.root/'FAULT.json').unlink();(self.proc/'sys/kernel/random/boot_id').write_text('different')
        with self.assertRaisesRegex(ValueError,'identity'):self.collector.snapshot()
        (self.proc/'sys/kernel/random/boot_id').write_text('boot')
        with patch.object(C,'MAX_FDS',0):
            with self.assertRaisesRegex(ValueError,'coverage cap'):self.collector.snapshot()
        with patch.object(C,'process_identity',side_effect=[None,ValueError('identity changed after')]):
            with self.assertRaisesRegex(ValueError,'after'):self.collector.snapshot()

    def test_wrong_pci_and_read_cap(self):
        p=self.base/'fdinfo/8';p.write_text(p.read_text().replace('23:','27:'))
        with self.assertRaisesRegex(ValueError,'PCI'):self.collector.snapshot()
        p.write_bytes(b'x'*17000)
        with self.assertRaisesRegex(ValueError,'Read cap'):self.collector.snapshot()

    def test_total_reset_missing_node_and_task_cap(self):
        self.collector.snapshot();self.fd(8,99,total=9)
        self.assertIn('nonincreasing-total',self.collector.snapshot()['issues'])
        (self.base/'fd/8').unlink()
        row=self.collector.snapshot()
        self.assertFalse(row['complete']);self.assertEqual(row['clients'],{})
        self.assertIn('missing-admitted-render-node',row['issues'])
        with patch.object(C,'MAX_TASKS',0):
            with self.assertRaisesRegex(ValueError,'coverage cap'):self.collector.snapshot()

    def test_run_duration_and_fault_stop_without_real_wait(self):
        out=self.root/'duration.jsonl'
        fake=type('Fake',(),{'snapshot':lambda self:{'complete':True}})()
        with patch.object(C,'Collector',return_value=fake),patch.object(C.time,'sleep'),patch.object(C.time,'monotonic',return_value=0):
            C.run(self.c,out,'a'*64)
        rows=[json.loads(x) for x in out.read_text().splitlines()]
        self.assertEqual(rows[-1]['terminal'],'duration-cap')
        self.assertEqual(sum('complete' in r for r in rows),60)
        out=self.root/'fault.jsonl'
        with patch.object(C,'Collector',return_value=fake),patch.object(fake,'snapshot',side_effect=ValueError('Fault marker present')),patch.object(C.time,'sleep'):
            C.run(self.c,out,'a'*64)
        rows=[json.loads(x) for x in out.read_text().splitlines()]
        self.assertEqual(len(rows),2);self.assertEqual(rows[-1]['terminal'],'observation-stopped')

    def test_cli_loop_exclusive_cap_and_no_live_proc(self):
        out=self.root/'output.jsonl'
        fake=type('Fake',(),{'snapshot':lambda self:{'large':'x'*10000}})()
        with patch.object(C,'Collector',return_value=fake),patch.object(C.time,'sleep'),patch.object(C.time,'monotonic',return_value=0):
            size=C.run(self.c,out,'a'*64)
            self.assertLessEqual(size['bytes'],C.MAX_OUTPUT)
            self.assertEqual(json.loads(out.read_text().splitlines()[-1])['terminal'],'output-cap')
            with self.assertRaises(FileExistsError):C.run(self.c,out,'a'*64)

    def test_contract_semantic_mapping_source_and_plan_pins(self):
        path=self.root/'contract.json'
        def load():
            path.write_bytes(C.canonical(self.c))
            return C.load_contract(path,C.digest(path.read_bytes()))
        load()
        mapping_path=Path(self.c['bindings']['mapping_evidence']['path'])
        original=mapping_path.read_bytes()
        for mutate in (lambda m:m.update(render_nodes={}),
                       lambda m:m['ordered_xpu_mapping'][0].update(ordinal=1),
                       lambda m:m.update(server_identity_sha256='0'*64),
                       lambda m:m.update(evidence_sources=[])):
            value=json.loads(original);mutate(value);mapping_path.write_bytes(C.canonical(value))
            self.c['bindings']['mapping_evidence']['sha256']=C.digest(mapping_path.read_bytes())
            with self.assertRaises((ValueError,KeyError)):load()
        mapping_path.write_bytes(original);self.c['bindings']['mapping_evidence']['sha256']=C.digest(original)
        source=json.loads(original)['evidence_sources'][0]['path'];Path(source).write_text('changed')
        with self.assertRaisesRegex(ValueError,'Bound source changed'):load()

    def test_rehashed_mapping_cannot_reorder_identity_properties(self):
        path=Path(self.c['bindings']['mapping_evidence']['path']);mapping=json.loads(path.read_bytes())
        self.c['ordered_xpu_mapping'][0]['properties_sha256']='0'*64
        mapping['ordered_xpu_mapping']=self.c['ordered_xpu_mapping'];path.write_bytes(C.canonical(mapping))
        self.c['bindings']['mapping_evidence']['sha256']=C.digest(path.read_bytes())
        with self.assertRaisesRegex(ValueError,'Ordered XPU mapping'):self.collector.snapshot()

    def test_strict_json_and_dead_process_states(self):
        for value in ('NaN','Infinity','-Infinity'):
            with self.assertRaisesRegex(ValueError,'Nonfinite'):C.strict('{"bad":'+value+'}')
        for state in ('Z','X','x'):
            path=self.base/'stat';path.write_text('17 (name) '+' '.join([state]+['0']*18+['42']))
            with self.assertRaisesRegex(ValueError,'zombie or exited'):self.collector.snapshot()

    def test_duplicate_capacity_and_counter_conflicts_preserve_provenance(self):
        self.fd(9,99,busy=90,total=900,capacity=2)
        row=self.collector.snapshot();client=row['clients']['0000:23:00.0/99']
        self.assertFalse(row['complete']);self.assertIn('duplicate-capacity-conflict',row['issues'])
        self.assertIn('duplicate-counter-regression',row['issues'])
        self.assertEqual(client['selected_fd'],'8');self.assertEqual(client['duplicate_observations'][0]['fd'],'9')
        self.assertEqual(client['engines']['ccs']['busy'],100)
        self.assertEqual(row['render_descriptors']['9']['client_key'],'0000:23:00.0/99')

    def test_total_watermark_survives_reset_and_partial_catchup(self):
        self.collector.snapshot()
        for total,incomplete in ((9,True),(10,True),(999,True),(1001,False)):
            self.fd(8,99,total=total)
            row=self.collector.snapshot();engine=row['clients']['0000:23:00.0/99']['engines']['ccs']
            self.assertEqual('total-below-watermark' in row['issues'],incomplete)
            self.assertEqual(engine['total_watermark'],max(1000,total))

    def test_reused_fd_number_and_child_change_during_scan(self):
        original=C.read;count=0
        def change_client(path,*args):
            nonlocal count
            if Path(path)==self.base/'fdinfo/8':
                count+=1
                if count==2:self.fd(8,100)
            return original(path,*args)
        with patch.object(C,'read',side_effect=change_client):row=self.collector.snapshot()
        self.assertIn('descriptor-client-changed',row['issues']);self.assertFalse(row['complete'])
        count=0
        def child(path,*args):
            nonlocal count
            if Path(path)==self.base/'task/17/children':
                count+=1
                if count==2:Path(path).write_text('77')
            return original(path,*args)
        with patch.object(C,'read',side_effect=child):row=self.collector.snapshot()
        self.assertIn('child-set-changed',row['issues']);self.assertEqual(row['child_pids'],['77'])

    def test_cadence_spacing_after_late_wakeup(self):
        clock={'now':0.0,'late':True};starts=[]
        def sleep(delay):
            clock['now']+=delay
            if delay and clock['late']:clock['now']+=1.9;clock['late']=False
        def sample():starts.append(clock['now']);return {'complete':True}
        fake=type('Fake',(),{'snapshot':lambda self:sample()})()
        with patch.object(C,'Collector',return_value=fake),patch.object(C.time,'sleep',side_effect=sleep), \
             patch.object(C.time,'monotonic',side_effect=lambda:clock['now']),patch.object(C,'DURATION',12):
            result=C.run(self.c,self.root/'late.jsonl','a'*64)
        self.assertTrue(all(b-a>=C.INTERVAL-1e-9 for a,b in zip(starts,starts[1:])))
        self.assertEqual(result['samples_recorded'],len(starts))

    def test_missed_slots_preserve_terminal_reserve_and_true_sample_count(self):
        clock={'now':0.0};calls=[]
        def sample():
            calls.append(clock['now']);clock['now']=100.0
            return {'complete':True}
        fake=type('Fake',(),{'snapshot':lambda self:sample()})()
        out=self.root/'missed.jsonl'
        with patch.object(C,'Collector',return_value=fake),patch.object(C.time,'sleep',side_effect=lambda s:clock.__setitem__('now',clock['now']+s)), \
             patch.object(C.time,'monotonic',side_effect=lambda:clock['now']),patch.object(C,'MAX_OUTPUT',3000):
            result=C.run(self.c,out,'a'*64)
        rows=[json.loads(line) for line in out.read_text().splitlines()]
        self.assertEqual(rows[-1]['terminal'],'output-cap')
        self.assertEqual(result['samples_recorded'],1);self.assertEqual(rows[-1]['samples_recorded'],1)
        self.assertGreater(result['missed_slots'],0);self.assertLessEqual(out.stat().st_size,3000)

    def test_short_writes_are_completed_and_interrupt_fsyncs_partial_evidence(self):
        builtin_open=open;syncs=[]
        class Short:
            def __init__(self,path,mode,**kw):self.inner=builtin_open(path,mode,**kw)
            def __enter__(self):return self
            def __exit__(self,*args):self.inner.close()
            def fileno(self):return self.inner.fileno()
            def write(self,raw):return self.inner.write(raw[:11])
        out=self.root/'short.jsonl';fake=type('Fake',(),{'snapshot':lambda self:{'complete':True}})()
        with patch.object(C,'open',Short,create=True),patch.object(C,'Collector',return_value=fake), \
             patch.object(C.time,'sleep'),patch.object(C.time,'monotonic',return_value=0),patch.object(C,'MAX_SAMPLES',1), \
             patch.object(C.os,'fsync',side_effect=lambda fd:syncs.append(fd)):
            result=C.run(self.c,out,'a'*64)
        self.assertEqual(result['bytes'],out.stat().st_size)
        self.assertEqual(json.loads(out.read_text().splitlines()[-1])['terminal'],'sample-cap')
        self.assertGreaterEqual(len(syncs),4)
        out=self.root/'interrupt.jsonl';syncs.clear()
        with patch.object(C,'Collector',return_value=fake),patch.object(fake,'snapshot',side_effect=KeyboardInterrupt), \
             patch.object(C.time,'sleep'),patch.object(C.os,'fsync',side_effect=lambda fd:syncs.append(fd)):
            with self.assertRaises(KeyboardInterrupt):C.run(self.c,out,'a'*64)
        self.assertEqual(json.loads(out.read_text().splitlines()[-1])['terminal'],'observer-failed')
        self.assertGreaterEqual(len(syncs),4)


    def test_source_manifest_plan_and_fault_paths_cannot_be_substituted(self):
        old=self.c['collector_sha256'];self.c['collector_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Collector source differs'):self.collector.snapshot()
        self.c['collector_sha256']=old
        old=self.c['runtime_manifest_sha256'];self.c['runtime_manifest_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Runtime manifest identity'):self.collector.snapshot()
        self.c['runtime_manifest_sha256']=old
        old=self.c['plan_sha256'];self.c['plan_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Server plan identity'):self.collector.snapshot()
        self.c['plan_sha256']=old
        path=Path(self.c['bindings']['plan']['path']);alternate=self.root/'other-plan.json';alternate.write_bytes(path.read_bytes())
        self.c['bindings']['plan']['path']=str(alternate)
        with self.assertRaisesRegex(ValueError,'Server packet paths'):self.collector.snapshot()
        self.c['bindings']['plan']['path']=str(path)
        self.c['fault_paths'].pop()
        with self.assertRaisesRegex(ValueError,'Missing server fault paths'):self.collector.snapshot()

    def test_duplicate_high_watermark_survives_missing_selected_counter(self):
        self.fd(9,99,busy=150)
        path=self.base/'fdinfo/8';path.write_text(path.read_text().replace('drm-cycles-ccs: 100\n',''))
        first=self.collector.snapshot()
        self.assertIn('missing-ccs-busy',first['issues'])
        self.assertEqual(first['clients']['0000:23:00.0/99']['engines']['ccs']['busy_watermark'],150)
        self.fd(8,99,busy=140,total=1100);self.fd(9,99,busy=140,total=1100)
        self.assertIn('busy-below-watermark',self.collector.snapshot()['issues'])

    def test_render_target_replacement_detected_with_unchanged_fd_names(self):
        original=C.os.readlink;count=0
        def replacement(path):
            nonlocal count
            if Path(path)==self.base/'fd/8':
                count+=1
                if count==2:return '/dev/null'
            return original(path)
        with patch.object(C.os,'readlink',side_effect=replacement):row=self.collector.snapshot()
        self.assertIn('render-descriptor-set-changed',row['issues']);self.assertFalse(row['complete'])

    def test_zero_write_and_fsync_failures_never_return_success(self):
        builtin_open=open;syncs=[]
        class Broken:
            def __init__(self,path,mode,**kw):self.inner=builtin_open(path,mode,**kw);self.calls=0
            def __enter__(self):return self
            def __exit__(self,*args):self.inner.close()
            def fileno(self):return self.inner.fileno()
            def write(self,raw):
                self.calls+=1
                return self.inner.write(raw[:10]) if self.calls==1 else 0
        with patch.object(C,'open',Broken,create=True),patch.object(C.os,'fsync',side_effect=lambda fd:syncs.append(fd)):
            with self.assertRaisesRegex(ValueError,'Incomplete output write'):
                C.run(self.c,self.root/'failed-write.jsonl','a'*64)
        self.assertEqual((self.root/'failed-write.jsonl').stat().st_size,10)
        self.assertGreaterEqual(len(syncs),2)
        with patch.object(C.os,'fsync',side_effect=OSError('synthetic sync failure')):
            with self.assertRaisesRegex(OSError,'sync failure'):
                C.run(self.c,self.root/'failed-sync.jsonl','a'*64)


    def test_nonrender_churn_does_not_invalidate_render_coverage(self):
        old=self.base/'fd/20';old.symlink_to('/dev/null')
        original=C.bounded_entries;counts={'fds':0}
        def churn(path,cap):
            if Path(path)==self.base/'fd':
                counts['fds']+=1
                if counts['fds']==2:
                    old.unlink();(self.base/'fd/21').symlink_to('anon_inode:dmabuf')
            return original(path,cap)
        with patch.object(C,'bounded_entries',side_effect=churn):row=self.collector.snapshot()
        self.assertTrue(row['complete']);self.assertEqual(row['nonrender_fd_churn'],dict(added=1,removed=1,retargeted=0))
        self.assertEqual(row['render_descriptors'],row['render_descriptors_after'])

    def test_new_render_descriptor_between_scans_is_not_ignored(self):
        original=C.bounded_entries;counts={'fds':0}
        def churn(path,cap):
            if Path(path)==self.base/'fd':
                counts['fds']+=1
                if counts['fds']==2:self.fd(9,100)
            return original(path,cap)
        with patch.object(C,'bounded_entries',side_effect=churn):row=self.collector.snapshot()
        self.assertIn('render-descriptor-set-changed',row['issues']);self.assertFalse(row['complete'])
        self.assertEqual(row['render_descriptors_after']['9']['client_key'],'0000:23:00.0/100')



if __name__=='__main__':unittest.main(verbosity=2)
