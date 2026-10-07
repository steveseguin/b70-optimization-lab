import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from campaign import verify_cache_log
from pilot import summarize_cache_usage

class CacheUsageTests(unittest.TestCase):
    def row(self,cached=0,prompt=100):
        return {'usage':{'prompt_tokens':prompt,'completion_tokens':12,'prompt_tokens_details':{'cached_tokens':cached}}}

    def test_all_calls_counted(self):
        self.assertEqual(summarize_cache_usage([self.row(),self.row()]),{'complete':True,'cached_tokens':0,'calls':2})
        self.assertEqual(summarize_cache_usage([self.row(),self.row(34)]),{'complete':True,'cached_tokens':34,'calls':2})

    def test_missing_invalid_or_failed_call_fails_closed(self):
        for bad in ({},{'usage':{}},{'usage':None},self.row(True),self.row(-1),self.row(101),self.row(0,True),
                    self.row('0'),self.row(0.0),{**self.row(),'error':'connection lost'}):
            with self.subTest(bad=bad):
                self.assertEqual(summarize_cache_usage([self.row(),bad]),{'complete':False,'cached_tokens':None,'calls':2})
        self.assertEqual(summarize_cache_usage([]),{'complete':False,'cached_tokens':None,'calls':0})

    def test_completion_or_created_tokens_not_mistaken_for_cache_hits(self):
        row=self.row();row['usage']['prompt_tokens_details']['created_cache_tokens']=99
        self.assertEqual(summarize_cache_usage([row])['cached_tokens'],0)

    def test_answer_and_ingestion_cache_hits_are_both_counted(self):
        calls=[{'phase':'quoted',**self.row()}, {'phase':'answer',**self.row(12)},
               {'phase':'answer',**self.row()}]
        self.assertEqual(summarize_cache_usage(calls),{'complete':True,'cached_tokens':12,'calls':3})

    def test_metadata_or_requested_policy_cannot_replace_missing_usage(self):
        call={'phase':'answer','model_response':{'usage':self.row()['usage']},
              'generation':{'enable_prefix_caching':False}}
        self.assertEqual(summarize_cache_usage([self.row(),call]),
                         {'complete':False,'cached_tokens':None,'calls':2})

    def test_unknown_does_not_hide_a_recorded_hit_as_zero(self):
        for calls in ([self.row(9),{}],[{},self.row(9)]):
            self.assertEqual(summarize_cache_usage(calls),
                             {'complete':False,'cached_tokens':None,'calls':2})


class RawCacheVerificationTests(unittest.TestCase):
    def row(self,cached=0):
        return {'phase':'answer','usage':{'prompt_tokens':100,'completion_tokens':20,
                                        'prompt_tokens_details':{'cached_tokens':cached}}}

    def verify(self,calls,aggregate,claimed_calls=None):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'calls.jsonl'
            payload=''.join(json.dumps(call)+'\n' for call in calls).encode()
            path.write_bytes(payload)
            result={'calls':len(calls) if claimed_calls is None else claimed_calls,
                    'cache_usage':aggregate}
            record=verify_cache_log(result,path)
            self.assertEqual(record['sha256'],hashlib.sha256(payload).hexdigest())
            return record

    def test_verified_zero_uses_every_raw_record(self):
        calls=[self.row(),self.row()]
        self.verify(calls,{'complete':True,'cached_tokens':0,'calls':2})

    def test_forged_zero_cannot_hide_cache_hit_or_missing_call_usage(self):
        for bad in (self.row(7),{},self.row(True),self.row('0')):
            with self.subTest(bad=bad),self.assertRaisesRegex(ValueError,'disagrees with raw'):
                self.verify([self.row(),bad],{'complete':True,'cached_tokens':0,'calls':2})

    def test_omitted_call_and_boolean_summary_count_are_rejected(self):
        calls=[self.row(),self.row()]
        for aggregate,count in [({'complete':True,'cached_tokens':0,'calls':1},1),
                                ({'complete':True,'cached_tokens':False,'calls':2},2)]:
            with self.subTest(aggregate=aggregate),self.assertRaisesRegex(ValueError,'disagrees with raw'):
                self.verify(calls,aggregate,count)

if __name__=='__main__':unittest.main()
