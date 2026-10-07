import copy
import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('evidence',Path(__file__).with_name('evidence.py'))
e=importlib.util.module_from_spec(spec); spec.loader.exec_module(e)
audit_spec=importlib.util.spec_from_file_location('decision_reader_audit',Path(__file__).with_name('audit.py'))
a=importlib.util.module_from_spec(audit_spec)
with patch.dict(sys.modules,{'evidence':e}):audit_spec.loader.exec_module(a)

class CitationContract(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); (self.root/'sources').mkdir()
        data=b'Previous preference withdrawn.\nOwner exception applies.\n'
        (self.root/'sources/01.txt').write_bytes(data)
        (self.root/'manifest.json').write_text(json.dumps({'sources':[{'id':'s1','path':'sources/01.txt','sha256':hashlib.sha256(data).hexdigest()}]}))
        (self.root/'questions.json').write_text(json.dumps({'questions':[{'id':'q1'}]}))
        self.answer={'answers':[{'id':'q1','status':'unknown','answer':None,'explanation':'Not supplied in this corpus.','citations':[{'source_id':'s1','start_line':1,'end_line':2,'quote':data.decode().rstrip('\n')}]}]}
    def test_null_is_valid_without_claiming_correctness(self):
        result=e.validate_answers(self.root,self.answer)
        self.assertTrue(result['citations_exact']); self.assertIsNone(result['semantic_quality'])
    def test_text_null_is_not_null(self):
        self.answer['answers'][0]['answer']='null'
        with self.assertRaises(ValueError): e.validate_answers(self.root,self.answer)
    def test_real_quote_wrong_claim_still_requires_semantic_review(self):
        a=self.answer['answers'][0]; a.update(status='answered',answer='Everyone may run a server forever.')
        self.assertIsNone(e.validate_answers(self.root,self.answer)['semantic_quality'])
    def test_partial_line_quote_rejected(self):
        self.answer['answers'][0]['citations'][0]['quote']='Owner exception applies.'
        with self.assertRaises(ValueError): e.validate_answers(self.root,self.answer)
    def test_wrong_lines_rejected(self):
        self.answer['answers'][0]['citations'][0]['end_line']=3
        with self.assertRaises(ValueError): e.validate_answers(self.root,self.answer)
    def test_boolean_line_rejected(self):
        self.answer['answers'][0]['citations'][0]['start_line']=True
        with self.assertRaises(ValueError): e.validate_answers(self.root,self.answer)
    def test_source_tamper_rejected(self):
        (self.root/'sources/01.txt').write_text('invented\n')
        with self.assertRaises(ValueError): e.validate_answers(self.root,self.answer)
    def test_duplicate_or_missing_answers_rejected(self):
        original=copy.deepcopy(self.answer)
        for answers in [[],original['answers']*2]:
            self.answer['answers']=answers
            with self.assertRaises(ValueError): e.validate_answers(self.root,self.answer)
    def test_duplicate_json_key_rejected(self):
        path=self.root/'bad.json'; path.write_text('{"answer":null,"answer":"guessed"}')
        with self.assertRaises(ValueError): e.read_json(path)
    def test_unknown_requires_scope_citation(self):
        self.answer['answers'][0]['citations']=[]
        with self.assertRaises(ValueError): e.validate_answers(self.root,self.answer)


class ReaderOperations(unittest.TestCase):
    """Run only against tiny temporary corpora, never the authored packet."""
    def setUp(self):
        CitationContract.setUp(self)
        manifest=e.read_json(self.root/'manifest.json')
        manifest['sources'][0].update(repository_path='fixture.txt',commit='fixture')
        (self.root/'manifest.json').write_text(json.dumps(manifest))
        (self.root/'protocol.json').write_text('{"fixture":true}\n')
        (self.root/'evidence.py').write_bytes(Path(e.__file__).read_bytes())
        self.submission=self.root/'submission.json'
        self.submission.write_text(json.dumps(self.answer))

    def args(self,command='read',arm='search',**changes):
        values={'root':self.root,'arm':arm,'command':command,'query':'owner',
                'source':'s1','start':1,'end':2,'file':self.submission}
        values.update(changes)
        return SimpleNamespace(**values)

    def run_reader(self,*args,**kwargs):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            e.run(self.args(*args,**kwargs))
        return json.loads(output.getvalue())

    def rows(self,arm='search'):
        path=self.root/'results'/arm/'reads.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_read_search_and_catalog_are_logged_with_exact_returned_payload(self):
        self.assertEqual(self.run_reader('search'),[{'source_id':'s1','line':2,'text':'Owner exception applies.'}])
        self.assertEqual(self.run_reader()['text'],'Previous preference withdrawn.\nOwner exception applies.')
        self.assertEqual(self.run_reader('catalog')['questions'],e.read_json(self.root/'questions.json'))
        rows=self.rows()
        self.assertEqual([r['sequence'] for r in rows],[1,2,3])
        for row in rows:
            data=json.dumps(row['response'],ensure_ascii=False,indent=2).encode()
            self.assertEqual(row['response_bytes'],len(data))
            self.assertEqual(row['response_sha256'],hashlib.sha256(data).hexdigest())

    def test_full_is_available_once_and_only_in_full_arm(self):
        self.assertEqual(self.run_reader('full','full')[0]['source_id'],'s1')
        for command,arm in [('full','full'),('read','full'),('search','full'),('full','search')]:
            with self.subTest(command=command,arm=arm),self.assertRaises(ValueError):
                self.run_reader(command,arm)
        self.assertEqual([r['command']for r in self.rows('full')],['full','rejected','rejected','rejected'])
        self.assertEqual(self.rows('search')[0]['attempted_command'],'full')

    def test_invalid_regex_range_and_missing_source_are_charged(self):
        for changes in ({'command':'search','query':'['},{'end':99},{'source':'absent'}):
            with self.assertRaises((ValueError,KeyError,e.re.error)):
                self.run_reader(**changes)
        rows=self.rows();self.assertEqual(len(rows),3)
        self.assertEqual([r['command']for r in rows],['rejected']*3)
        self.assertEqual([r['sequence']for r in rows],[1,2,3])

    def test_rejected_attempts_reach_operation_limit(self):
        for _ in range(64):
            with self.assertRaises(ValueError):self.run_reader(end=99)
        self.assertEqual(len(self.rows()),64)
        with self.assertRaisesRegex(ValueError,'limit'):self.run_reader()
        self.assertEqual(len(self.rows()),64)

    def test_source_manifest_questions_protocol_or_reader_drift_is_rejected(self):
        self.run_reader()
        for name in ('manifest.json','questions.json','protocol.json','evidence.py'):
            path=self.root/name;original=path.read_bytes();path.write_bytes(original+b' ')
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'identity changed'):
                self.run_reader()
            path.write_bytes(original)
        self.assertEqual(len(self.rows()),1)
        source=self.root/'sources/01.txt';source.write_text('Replacement source.\n')
        manifest=e.read_json(self.root/'manifest.json');manifest['sources'][0]['sha256']=e.digest(source.read_bytes())
        (self.root/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'identity changed'):self.run_reader()

    def test_first_invalid_submission_is_preserved_and_closes_trial(self):
        raw=b'not valid JSON\n';self.submission.write_bytes(raw)
        result=self.run_reader('submit')
        self.assertFalse(result['mechanical_pass']);self.assertIsNone(result['semantic_quality'])
        self.assertEqual((self.root/'results/search/answers.json').read_bytes(),raw)
        self.submission.write_text(json.dumps(self.answer))
        for command in ('submit','read'):
            with self.assertRaisesRegex(ValueError,'closed'):self.run_reader(command)
        self.assertEqual((self.root/'results/search/answers.json').read_bytes(),raw)
        self.assertEqual(len(self.rows()),1)
        self.assertEqual(self.rows()[0]['submission_sha256'],e.digest(raw))

    def test_last_slot_can_hold_first_submission(self):
        for _ in range(63):self.run_reader()
        self.run_reader('submit')
        self.assertEqual(len(self.rows()),64);self.assertEqual(self.rows()[-1]['command'],'submit')

    def test_overbyte_response_is_not_delivered_and_rejection_is_logged(self):
        data=b'x'*160000+b'\n';(self.root/'sources/01.txt').write_bytes(data)
        manifest=e.read_json(self.root/'manifest.json');manifest['sources'][0]['sha256']=e.digest(data)
        (self.root/'manifest.json').write_text(json.dumps(manifest))
        with contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(ValueError,'300000'):e.run(self.args(end=1))
        self.assertNotIn('x'*100,output.getvalue())
        self.assertEqual(self.rows()[0]['command'],'rejected')

    def test_error_control_bytes_do_not_reduce_successful_evidence_allowance(self):
        # Fit one large passage plus one tiny passage at the evidence cap; an
        # intervening refusal is charged as an operation, not source bytes.
        small={'source_id':'s1','start_line':2,'end_line':2,'text':'z','numbered_text':'2: z'}
        small_size=len(json.dumps(small,ensure_ascii=False,indent=2).encode())
        def large_size(n):
            passage={'source_id':'s1','start_line':1,'end_line':1,'text':'x'*n,'numbered_text':'1: '+'x'*n}
            return len(json.dumps(passage,ensure_ascii=False,indent=2).encode())
        n=(300000-small_size-large_size(0))//2
        data=('x'*n+'\nz\n').encode();(self.root/'sources/01.txt').write_bytes(data)
        manifest=e.read_json(self.root/'manifest.json');manifest['sources'][0]['sha256']=e.digest(data)
        (self.root/'manifest.json').write_text(json.dumps(manifest))
        self.run_reader(end=1)
        with self.assertRaises(ValueError):self.run_reader(end=99)
        self.run_reader(start=2,end=2)
        rows=self.rows();self.assertEqual([r['command']for r in rows],['read','rejected','read'])
        self.assertLessEqual(sum(r['response_bytes']for r in rows if r['command']!='rejected'),300000)
        self.assertGreater(sum(r['response_bytes']for r in rows),300000)

    def test_concurrent_submissions_keep_only_the_first(self):
        self.submission.write_bytes(b'{"first":1}')
        second=self.root/'second.json';second.write_bytes(b'{"second":2}')
        entered=threading.Event();release=threading.Event();errors=[];original=e._run
        def held(args):
            if threading.current_thread().name=='first':
                entered.set()
                if not release.wait(5):raise RuntimeError('test synchronization timeout')
            return original(args)
        def submit(file):
            try:e.run(self.args('submit',file=file))
            except Exception as error:errors.append(error)
        with patch.object(e,'_run',side_effect=held),contextlib.redirect_stdout(io.StringIO()):
            first=threading.Thread(target=submit,args=(self.submission,),name='first')
            later=threading.Thread(target=submit,args=(second,),name='second')
            first.start();self.assertTrue(entered.wait(5));later.start();release.set()
            first.join(5);later.join(5)
        self.assertFalse(first.is_alive());self.assertFalse(later.is_alive())
        self.assertEqual((self.root/'results/search/answers.json').read_bytes(),b'{"first":1}')
        self.assertEqual(len(errors),1);self.assertIsInstance(errors[0],ValueError)
        self.assertEqual(len(self.rows()),1)

    def test_concurrent_reads_cannot_both_take_last_slot(self):
        for _ in range(63):self.run_reader()
        barrier=threading.Barrier(2);errors=[]
        def read():
            try:barrier.wait(5);e.run(self.args())
            except Exception as error:errors.append(error)
        with contextlib.redirect_stdout(io.StringIO()):
            threads=[threading.Thread(target=read) for _ in range(2)]
            for thread in threads:thread.start()
            for thread in threads:thread.join(5)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(len(errors),1);self.assertEqual(len(self.rows()),64)
        self.assertEqual([r['sequence']for r in self.rows()],list(range(1,65)))


class ReplayAudit(unittest.TestCase):
    def setUp(self):
        ReaderOperations.setUp(self)
        questions=[{'id':f'q{i}'} for i in range(12)]
        (self.root/'questions.json').write_text(json.dumps({'questions':questions}))
        citation=self.answer['answers'][0]['citations'][0]
        refs=[{'id':q['id'],'status':'unknown' if i<2 else 'answered',
               'reference_answer':None if i<2 else 'fixture decision',
               'criteria':[{'citations':[citation]}]} for i,q in enumerate(questions)]
        (self.root/'reference.json').write_text(json.dumps({'questions':refs}))
        manifest=e.read_json(self.root/'manifest.json')
        manifest['artifacts']={name:{'sha256':e.digest((self.root/name).read_bytes())}
                               for name in ('questions.json','reference.json','protocol.json','evidence.py')}
        (self.root/'manifest.json').write_text(json.dumps(manifest))
        valid={'answers':[{**copy.deepcopy(self.answer['answers'][0]),'id':q['id']}for q in questions]}
        self.submission.write_text(json.dumps(valid))
        self.mock_git=patch.object(a.subprocess,'check_output',return_value=(self.root/'sources/01.txt').read_bytes())
        self.mock_git.start();self.addCleanup(self.mock_git.stop)

    args=ReaderOperations.args
    run_reader=ReaderOperations.run_reader
    rows=ReaderOperations.rows

    def complete(self,invalid=False):
        for arm in ('full','search'):
            self.run_reader('catalog',arm)
            self.run_reader('full' if arm=='full' else 'read',arm)
            file=self.submission
            if invalid and arm=='full':
                file=self.root/'invalid.json';file.write_bytes(b'not json\n')
            self.run_reader('submit',arm,file=file)

    def test_invalid_first_submission_remains_auditable_failure(self):
        self.complete(invalid=True)
        report=a.audit(self.root,True)
        self.assertFalse(report['arms']['full']['mechanical']['mechanical_pass'])
        self.assertIsNone(report['arms']['full']['all_cited_lines_delivered'])
        self.assertTrue(report['arms']['search']['mechanical']['citations_exact'])
        self.assertIsNone(report['arms']['search']['semantic_quality'])

    def test_submission_hash_binds_even_mechanically_invalid_bytes(self):
        self.complete(invalid=True)
        (self.root/'results/full/answers.json').write_bytes(b'also not json\n')
        with self.assertRaisesRegex(ValueError,'submission receipt'):a.audit(self.root,True)

    def test_catalog_replay_rejects_rehashed_wrong_questions(self):
        self.complete()
        path=self.root/'results/search/reads.jsonl';rows=self.rows()
        rows[0]['response']['questions']={'questions':[]}
        encoded=json.dumps(rows[0]['response'],ensure_ascii=False,indent=2).encode()
        rows[0].update(response_bytes=len(encoded),response_sha256=e.digest(encoded))
        path.write_text(''.join(json.dumps(row)+'\n'for row in rows))
        with self.assertRaisesRegex(ValueError,'catalog questions'):a.audit(self.root,True)

    def test_replay_rejects_duplicate_terminal_submission(self):
        self.complete()
        path=self.root/'results/search/reads.jsonl';rows=self.rows()
        rows.append(copy.deepcopy(rows[-1]));rows[-1]['sequence']=len(rows)
        path.write_text(''.join(json.dumps(row)+'\n'for row in rows))
        with self.assertRaisesRegex(ValueError,'submission receipt'):a.audit(self.root,True)

if __name__=='__main__': unittest.main()
