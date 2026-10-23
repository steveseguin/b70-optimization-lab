"""Actual pinned codec with synthetic native/store seams; no model execution."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chat_codec as C
import chat_service as canonical
import test_checkpoint_engine as F
from streaming_v1 import engine as E, decoder as D, service as S
from streaming_v1.test_engine import Front


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec = C.PinnedChatCodec()
        cls.byte_ids = {}
        for token in range(cls.codec.vocab):
            raw = D.token_bytes(cls.codec, token)
            if len(raw) == 1:
                cls.byte_ids.setdefault(raw[0], token)
            if len(cls.byte_ids) == 256:
                break

    def make(self, *, budget=524288):
        trusted = F.identity()
        trusted['tokenizer_identity'] = dict(self.codec.tokenizer_identity)
        trusted['geometry'].update(vocab=self.codec.vocab, eos=248044)
        store = F.Store()
        front = Front(store, trusted)
        front.ready['vocab'] = self.codec.vocab
        engine = E.StreamingCheckpointEngine(front, store, root=store.root,
            expected_identity=trusted, admitted_contract='v1.2+p198',
            save_size_bound_bytes=65536, storage_available=lambda root:1000000, floor_bytes=1000)
        parking = F.parking.Parking(engine, self.codec.render, self.codec.encode,
            budget_bytes=budget, accepted_contracts={('experimental-postreply-front','v1.2+p198')})
        service = S.StreamingChatService(engine, parking, self.codec, model='synthetic-owner-real-codec',
            native_stop_token_ids={248044,248046}, clock=lambda:123)
        return service, engine, front, store

    def payload(self, maximum, **changes):
        return dict(model='synthetic-owner-real-codec', messages=[{'role':'user','content':'Say hello.'}],
                    max_tokens=maximum, stream=True) | changes

    def call(self, service, payload, callback=lambda delta:None):
        return service.stream(payload, session='conversation', request_id='r1', on_delta=callback)

    def test_live_delta_before_save_and_canonical_result_usage_parity(self):
        service, engine, front, _ = self.make()
        front.generated = self.codec.encode('  café 🙂\n') + [248046]
        payload = self.payload(len(front.generated)+2)
        emitted = []
        def delta(text):
            self.assertEqual(front.state, 'running')
            self.assertFalse(front.saved_tokens)
            emitted.append(text)
        service.clock = lambda: self.assertEqual(front.completed,0) or 123
        result = self.call(service, payload, delta)
        self.assertTrue(result['stream_passed'])
        self.assertEqual(''.join(emitted), '  café 🙂\n')
        self.assertEqual([x[0] for x in front.calls], ['RUN','SAVE'])
        self.assertEqual(front.saved_tokens[-1][-len(front.generated):], front.generated)
        other, _, native, _ = self.make()
        native.generated = front.generated
        expected = other.complete(payload | {'stream':False}, session='conversation', request_id='r1')
        self.assertEqual(result['completion'], expected)

    def test_all_six_recorded_p199_outputs_match_actual_codec_text(self):
        path=C.HERE.parent/'stage2/packet199-chat-parking/evidence/device-p199-chat-A-a/http-requests.json'
        for row in json.loads(path.read_text()):
            with self.subTest(name=row['name']):
                service, _, front, _ = self.make(budget=0)
                front.generated = row['tokens']; emitted=[]
                result = self.call(service,self.payload(len(front.generated)),emitted.append)
                self.assertTrue(result['stream_passed'])
                self.assertEqual(''.join(emitted),row['response']['choices'][0]['message']['content'])

    def test_no_save_and_same_id_hit_release_even_when_observer_fails(self):
        for same_id in (False,True):
            service, engine, front, _ = self.make(budget=0)
            front.generated = self.codec.encode('abc') + [248046]
            front.max_requests = 1
            if same_id:
                service.parking.park = lambda *args:object()
            failure = BrokenPipeError('client gone'); calls=[]
            def delta(text):
                calls.append(text)
                raise failure
            result=self.call(service,self.payload(len(front.generated)),delta)
            self.assertFalse(result['stream_passed']);self.assertEqual(len(calls),1)
            self.assertIs(service.last_stream_error,failure)
            self.assertIsNone(service.halted_reason);self.assertIsNone(engine.halted_reason)
            self.assertEqual([x[0] for x in front.calls],['RUN','RELEASE'])
            self.assertEqual(front.state,'draining')

    def test_observer_failure_keeps_save_and_remaining_decode_and_next_turn(self):
        service, engine, front, _ = self.make()
        front.generated=[self.byte_ids[b] for b in b'a\xf0\x9f\x99\x82']+[248046]
        failure=KeyboardInterrupt('observer only');calls=[]
        def delta(text):calls.append(text);raise failure
        result=self.call(service,self.payload(len(front.generated)),delta)
        self.assertFalse(result['stream_passed']);self.assertEqual(calls,['a'])
        self.assertEqual(result['completion']['choices'][0]['message']['content'],'a🙂')
        self.assertEqual([x[0] for x in front.calls],['RUN','SAVE'])
        self.assertIs(service.last_stream_error,failure)
        result=service.stream(self.payload(len(front.generated)),session='next',request_id='r2',on_delta=lambda text:None)
        self.assertTrue(result['stream_passed']);self.assertIsNone(service.last_stream_error)

    def test_tail_flush_after_disposition_and_tail_error_no_false_success(self):
        for fails in (False,True):
            service, _, front, _ = self.make(budget=0)
            front.generated=[self.byte_ids[0xf0],self.byte_ids[0x9f]]
            failure=OSError('tail sink');seen=[]
            def delta(text):
                self.assertEqual(front.state,'ready');seen.append(text)
                if fails:raise failure
            result=self.call(service,self.payload(2),delta)
            self.assertEqual(seen,['�']);self.assertEqual(result['stream_passed'],not fails)
            self.assertIsNone(service.halted_reason)
            if fails:self.assertIs(service.last_stream_error,failure)

    def test_observer_false_return_not_claimed_as_wire_receipt(self):
        service, _, front, _ = self.make(budget=0)
        front.generated=self.codec.encode('a')+[248046]
        result=self.call(service,self.payload(len(front.generated)),lambda text:False)
        self.assertTrue(result['stream_passed'])
        self.assertNotIn('delivered',result['observation'])

    def test_decode_error_halts_after_disposition_and_keeps_original(self):
        for phase in ('feed','finish'):
            service, _, front, _ = self.make(budget=0)
            front.generated=self.codec.encode('a')+[248046]
            original=D.DecodeRefusal('decoder original')
            with patch.object(D.TokenDecoder,phase,side_effect=original):
                with self.assertRaises(D.DecodeRefusal) as raised:
                    self.call(service,self.payload(len(front.generated)))
            self.assertIs(raised.exception,original)
            self.assertEqual([x[0] for x in front.calls],['RUN','RELEASE'])
            self.assertIs(service.last_stream_error,original)
            with self.assertRaisesRegex(RuntimeError,'halted'):
                self.call(service,self.payload(len(front.generated)))

    def test_native_save_failure_primary_even_after_sink_failure(self):
        service, engine, front, _ = self.make()
        front.generated=self.codec.encode('a')+[248046];front.ambiguous_save=True
        def delta(text):raise BrokenPipeError('sink first')
        with self.assertRaisesRegex(OSError,'lost SAVE acknowledgement') as raised:
            self.call(service,self.payload(len(front.generated)),delta)
        self.assertIs(service.last_stream_error,raised.exception)
        self.assertIsNotNone(service.halted_reason);self.assertIsNotNone(engine.halted_reason)
        self.assertEqual([x[0] for x in front.calls],['RUN','SAVE'])

    def test_invalid_native_stop_halts_after_normal_disposition(self):
        for generated,maximum in (([248046,1],2),([1],2)):
            service, _, front, _ = self.make(budget=0);front.generated=generated
            with self.assertRaisesRegex(RuntimeError,'stop behavior'):
                self.call(service,self.payload(maximum))
            self.assertIsNotNone(service.halted_reason)
            self.assertEqual([x[0] for x in front.calls],['RUN','RELEASE'])

    def test_validation_is_once_per_stream_and_preowner_refusals_recover(self):
        service, _, front, _ = self.make(budget=0)
        payload=self.payload(2);original=copy.deepcopy(payload)
        for change in ({'temperature':1},{'tools':[]},{'stream':1},{'stream':False},
                       {'max_tokens':True},{'model':'wrong'}):
            with self.assertRaises(canonical.ChatRequestError):self.call(service,payload|change)
        self.assertFalse(front.calls);self.assertIsNone(service.halted_reason)
        self.assertEqual(payload,original)
        front.generated=[1,2]
        with patch.object(service,'validate',wraps=service.validate) as validate:
            self.call(service,payload)
            self.assertEqual(validate.call_count,1)

    def test_nonstream_remains_strict_and_reentrant_observer_cannot_run_owner(self):
        service, _, front, _ = self.make(budget=0)
        with self.assertRaises(canonical.ChatRequestError):
            service.complete(self.payload(2),session='s',request_id='x')
        front.generated=self.codec.encode('a')+[248046]
        def delta(text):
            service.complete(self.payload(2,stream=False),session='s',request_id='nested')
        result=self.call(service,self.payload(len(front.generated)),delta)
        self.assertFalse(result['stream_passed'])
        self.assertEqual([x[0] for x in front.calls],['RUN','RELEASE'])
        self.assertIsNone(service.halted_reason)

    def test_unprintable_observer_error_is_preserved(self):
        class Unprintable(Exception):
            def __str__(self):raise RuntimeError('cannot format')
        service, _, front, _ = self.make(budget=0)
        front.generated=self.codec.encode('a')+[248046];failure=Unprintable()
        def delta(text):raise failure
        result=self.call(service,self.payload(len(front.generated)),delta)
        self.assertFalse(result['stream_passed'])
        self.assertEqual(result['error']['message'],'<exception message unavailable>')
        self.assertIs(service.last_stream_error,failure)

    def test_dependency_pin_and_exact_engine_refusal(self):
        with patch.object(S,'PINS',((canonical,S.HERE.parent/'chat_service.py','0'*64),)):
            with self.assertRaisesRegex(canonical.ChatRequestError,'dependency changed'):self.make()
        service, engine, _, _=self.make()
        with self.assertRaisesRegex(canonical.ChatRequestError,'exact streaming'):
            S.StreamingChatService(object(),service.parking,self.codec,model='x',native_stop_token_ids={248044,248046})


if __name__=='__main__':unittest.main()
