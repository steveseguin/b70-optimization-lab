"""CPU-only negative tests for byte/event closure and immutable companions."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import summarize as s
import window_support as w


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + '\n')


def lines(path, records):
    path.write_text(''.join(json.dumps(x) + '\n' for x in records))


def digest(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


def native(root, mode='exact'):
    root.mkdir(parents=True)
    comparisons = []
    events = []
    stamp = 1000
    for c, m, i in s.manifest(mode):
        n = 640 if c.startswith('expsgate') else 2560 if c == 'expsdown' else 10240 if 'qkv' in c else 6144
        slots = 10 if c.startswith('exps') else 1
        comparisons.append(dict(class_=c, M=m, iteration=i, bytes=m*(n*slots*4+slots*8+4),
                                sha256=digest((c,m,i)), input_sha256=digest(('input',c,m,i)), equal=True))
        comparisons[-1]['class'] = comparisons[-1].pop('class_')
        if mode == 'timing':
            for candidate in (False, True):
                ev=[]
                for _ in range(1 if candidate else m):
                    ev.append(dict(start_ns=stamp, end_ns=stamp+100));stamp+=200
                events.append({'class':c,'M':m,'iteration':i,'candidate':candidate,
                               'warmup':i<4,'events':ev,'gpu_ns':100*len(ev)})
    identity=digest(''.join(x['sha256'] for x in comparisons))
    receipt=dict(schema='ownrt.packet48.native.v1',passed=True,device_executed=True,
                 mode=mode,safe_teardown=True,checks=len(comparisons),exact_output_identity=identity)
    write(root/'receipt.json',receipt)
    lines(root/'comparisons.jsonl',comparisons)
    lines(root/'iterations.jsonl',events)
    return receipt, comparisons, events


class Validation(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def exact_mutation(self, mutate):
        root=self.root/'run';receipt,records,_=native(root)
        self.assertEqual(s.exact(root),receipt)
        mutate(receipt,records)
        write(root/'receipt.json',receipt);lines(root/'comparisons.jsonl',records)
        with self.assertRaises((ValueError,KeyError)):s.exact(root)

    def test_missing_capture(self):
        self.exact_mutation(lambda r,v:v.pop())

    def test_duplicate_capture(self):
        self.exact_mutation(lambda r,v:v.__setitem__(1,copy.deepcopy(v[0])))

    def test_truncated_extent(self):
        self.exact_mutation(lambda r,v:v[0].__setitem__('bytes',4))

    def test_reported_mismatch(self):
        self.exact_mutation(lambda r,v:v[0].__setitem__('equal',False))

    def test_output_identity_mutation(self):
        self.exact_mutation(lambda r,v:v[0].__setitem__('sha256',digest('changed')))

    def test_unchanged_inputs(self):
        self.exact_mutation(lambda r,v:v[1].__setitem__('input_sha256',v[0]['input_sha256']))

    def test_unsafe_teardown(self):
        self.exact_mutation(lambda r,v:r.__setitem__('safe_teardown',False))

    def test_empty_timing_not_allowed(self):
        root=self.root/'run';native(root,'timing');lines(root/'iterations.jsonl',[])
        with self.assertRaises(ValueError):s.timing(root)

    def test_timing_event_mutations(self):
        root=self.root/'run';_,_,records=native(root,'timing');self.assertTrue(s.timing(root)['passed'])
        for change in ('missing','sum','duplicate','end','warmup'):
            with self.subTest(change=change):
                rows=copy.deepcopy(records)
                if change=='missing':rows[0]['events']=[]
                if change=='sum':rows[0]['gpu_ns']+=1
                if change=='duplicate':rows[1]['events']=copy.deepcopy(rows[0]['events']);rows[1]['gpu_ns']=rows[0]['gpu_ns']
                if change=='end':rows[0]['events'][0]['end_ns']=rows[0]['events'][0]['start_ns']
                if change=='warmup':rows[0]['warmup']=False
                lines(root/'iterations.jsonl',rows)
                with self.assertRaises(ValueError):s.timing(root)

    def companions(self):
        current=dict(seal_sha256=digest('seal'),binary_sha256=digest('binary'),card=0,
                     boot_id='boot',environment={'TEST':'closed'},coordinator_fault_review='review')
        paths=[]
        for index in (1,2):
            out=self.root/f'e{index}';receipt,_,_=native(out/'run')
            row=dict(current,schema='own-runtime.packet48.window.v1',passed=True,mode='exact',
                     device_executed=True,child_still_running=False,pid=100+index,
                     process_start_ticks=1000+index,exact_output_identity=receipt['exact_output_identity'],
                     native_files={f'run/{name}':w.sha(out/'run'/name) for name in ('receipt.json','comparisons.jsonl','iterations.jsonl')})
            path=out/'window.json';write(path,row);paths.append(path)
        return paths,current

    def test_companion_identity_and_file_drift(self):
        paths,current=self.companions();self.assertEqual(len(w.prerequisite(paths,current)),2)
        changed=dict(current,boot_id='other')
        with self.assertRaises((ValueError,RuntimeError)):w.prerequisite(paths,changed)
        (paths[0].parent/'run/comparisons.jsonl').write_text('changed')
        with self.assertRaises((ValueError,RuntimeError)):w.prerequisite(paths,current)

    def test_companions_require_fresh_processes(self):
        paths,current=self.companions();a=json.loads(paths[0].read_text());b=json.loads(paths[1].read_text())
        b.update(pid=a['pid'],process_start_ticks=a['process_start_ticks']);write(paths[1],b)
        with self.assertRaises((ValueError,RuntimeError)):w.prerequisite(paths,current)

    def test_companion_complete_file_closure(self):
        paths,current=self.companions();row=json.loads(paths[0].read_text())
        row['native_files'].pop('run/comparisons.jsonl');write(paths[0],row)
        with self.assertRaises((ValueError,RuntimeError)):w.prerequisite(paths,current)

    def test_companion_native_output_identity(self):
        paths,current=self.companions();row=json.loads(paths[0].read_text())
        receipt=paths[0].parent/'run/receipt.json';r=json.loads(receipt.read_text())
        r['exact_output_identity']=digest('wrong');write(receipt,r)
        row['native_files']['run/receipt.json']=w.sha(receipt);write(paths[0],row)
        with self.assertRaises((ValueError,RuntimeError)):w.prerequisite(paths,current)

    def test_companion_revalidates_native_bytes(self):
        paths,current=self.companions();row=json.loads(paths[0].read_text())
        path=paths[0].parent/'run/comparisons.jsonl';records=s.rows(path);records[0]['equal']=False;lines(path,records)
        row['native_files']['run/comparisons.jsonl']=w.sha(path);write(paths[0],row)
        with self.assertRaises((ValueError,RuntimeError)):w.prerequisite(paths,current)

    def test_complete_seal_and_mutations(self):
        repo=self.root/'repo';root=repo/'packet';root.mkdir(parents=True)
        (repo/'source.cpp').write_text('source')
        binary=root/'build/device/bench';binary.parent.mkdir(parents=True);binary.write_bytes(b'binary')
        gates={}
        for name in ('python-gates.json','cpu-gates.json','build-gnu.json','build-intel.json','build-device.json'):
            write(root/name,dict(passed=True,device_executed=False));gates[name]=w.sha(root/name)
        seal=dict(schema='own-runtime.packet48.seal.v1',passed=True,device_executed=False,
                  sources={'source.cpp':w.sha(repo/'source.cpp')},
                  artifacts={'build/device/bench':w.sha(binary)},gates=gates)
        path=root/'seal.json';write(path,seal)
        self.assertEqual(w.sealed_gate(path,root=root,repo=repo),seal)
        for name in ('source','binary','missing_gate','bad_gate','unbound_binary'):
            with self.subTest(name=name):
                bad=copy.deepcopy(seal)
                if name=='source':bad['sources']['source.cpp']=digest('changed')
                if name=='binary':bad['artifacts']['build/device/bench']=digest('changed')
                if name=='missing_gate':bad['gates'].pop('cpu-gates.json')
                if name=='bad_gate':
                    write(root/'cpu-gates.json',dict(passed=False,device_executed=False))
                    bad['gates']['cpu-gates.json']=w.sha(root/'cpu-gates.json')
                if name=='unbound_binary':
                    bad['artifacts']={'cpu-gates.json':w.sha(root/'cpu-gates.json')}
                write(path,bad)
                with self.assertRaises((ValueError,RuntimeError)):w.sealed_gate(path,root=root,repo=repo)
                write(root/'cpu-gates.json',dict(passed=True,device_executed=False))

    def test_unsafe_sealed_paths(self):
        for name in ('../secret','/absolute'):
            with self.subTest(name=name),self.assertRaises((ValueError,RuntimeError)):w.inside(self.root,name)
        (self.root/'file').write_text('before')
        w.verify_files({'file':w.sha(self.root/'file')},self.root)
        with self.assertRaises((ValueError,RuntimeError)):w.verify_files({'file':digest('wrong')},self.root)


if __name__=='__main__':unittest.main()
