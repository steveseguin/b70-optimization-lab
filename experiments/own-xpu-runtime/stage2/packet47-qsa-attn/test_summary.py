"""Negative controls for incomplete or misleading qualification evidence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import summarize as s


def dump(path,rows):
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows))


class SummaryTests(unittest.TestCase):
    def test_exact_matrix_cannot_be_shortened_or_duplicated(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);rows=[]
            for c,m,seed,v,control,buffer in sorted(s.exact_keys()):
                n={'attention.output':m*6144*2,'selection.ids':m*2051*4,
                   'qgate.output':m*12288*2,'error':4,'readonly.input':m*32780+c*2048+8}[buffer]
                rows.append(dict(context=c,rows=m,seed=seed,variant=v,control=control,buffer=buffer,
                                 bytes=n,equal=True,sha256='a'*64,expected_sha256='a'*64))
            def write(values):
                dump(root/'comparisons.jsonl',values)
                (root/'receipt.json').write_text(json.dumps(dict(passed=True,mode='exact',cpu_mock=False,
                    safe_to_exit=True,checks=len(values))))
            write(rows);self.assertEqual(s.exact(root)['comparisons'],316)
            mutations=[lambda r:r.pop(),lambda r:r.append(r[0]),lambda r:r[0].update(equal=False),
                       lambda r:r[0].update(sha256=''),lambda r:r[0].update(bytes=1),lambda r:r[0].update(expected_sha256='b'*64)]
            for mutate in mutations:
                data=copy.deepcopy(rows);mutate(data);write(data)
                with self.assertRaises(ValueError):s.exact(root)

    def test_timing_full_matrix_accounting_and_bar(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);rows=[]
            for c in s.CONTEXTS:
                for m in (1,2):
                    for i in range(210):
                        for v in s.VARIANTS:
                            durations={'qsa.attention':6000 if v=='current' else 1000,
                                       'qsa.select':200,'qsa.qgate':300}
                            events=[];start=1
                            counts={'qsa.attention':2*m if v=='current' else (5 if v=='ordered' else 3),'qsa.select':2,'qsa.qgate':1}
                            durations={cls:n*counts[cls] for cls,n in durations.items()}
                            for cls,n in durations.items():
                                for j in range(counts[cls]):
                                    span=n//counts[cls]
                                    events.append(dict(id=len(events)+1,**{'class':cls},start_ns=start,end_ns=start+span))
                                    start+=span
                            rows.append(dict(context=c,rows=m,iteration=i,variant=v,warmup=i<10,
                                exact=True,events=events,classes_ns=durations,submissions=len(events),gpu_ns=sum(durations.values())))
            (root/'receipt.json').write_text(json.dumps(dict(passed=True,mode='timing',cpu_mock=False,
                safe_to_exit=True,timing_pair_checks=2100)))
            def write(values):dump(root/'iterations.jsonl',values)
            write(rows);result=s.timing(root)
            self.assertEqual(len(result['shapes']),10)
            self.assertFalse(result['shapes']['c4096-m2']['variants']['ordered']['order_preference_passed'])
            def omit_and_retotal(r):
                row=r[0];event=row['events'].pop(0);n=event['end_ns']-event['start_ns'];row['classes_ns'][event['class']]-=n;row['gpu_ns']-=n;row['submissions']-=1
            mutations=[omit_and_retotal,lambda r:r.pop(),lambda r:r.append(r[0]),lambda r:r[0].update(exact=False),
                lambda r:r[0].update(gpu_ns=1),lambda r:r[0]['events'][0].update(end_ns=0),
                lambda r:r[0]['events'][0].update(id=2),lambda r:r[0].update(context=512),
                lambda r:r[0]['classes_ns'].update({'qsa.attention':99})]
            for mutate in mutations:
                data=copy.deepcopy(rows);mutate(data);write(data)
                with self.assertRaises(ValueError):s.timing(root)

if __name__=='__main__':unittest.main()
