"""Streaming composition CPU fixtures; no native/model process or live profile.

Public attach tests use actual held root/binary FDs and exact uninitialized front
type, mocking only canonical profile validation and codec construction (returns
the actual pinned codec). This does not bypass any production admission gate.
"""
import copy
import http.client
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import chat_codec as C
import bounded_serving_profile as P
import test_bounded_serving_session as F
from streaming_v1 import session as S, engine as E, service as CS, lifecycle as L, http as H
from streaming_v1.test_lifecycle import Front


class SessionTests(F.SessionTests):
    @classmethod
    def setUpClass(cls):cls.shared_codec=C.PinnedChatCodec()

    def setUp(self):
        super().setUp()
        self.codec=copy.copy(self.shared_codec)
        self.identity['tokenizer_identity']=dict(self.codec.tokenizer_identity)
        self.identity['geometry'].update(vocab=self.codec.vocab,eos=248044)
        self.front=Front(self.store,self.identity);self.front.ready['vocab']=self.codec.vocab
        self.front.generated=self.codec.encode('reply')+[248046]
        self.assertEqual(len(self.front.generated),2)
        self.spec['native_stop_token_ids']=[248044,248046]

    def compose(self,guard=None):
        self.session=S._compose(profile=self.spec,front=self.front,store=self.store,codec=self.codec,
            guard=guard or (lambda:self.guards.append(True)),launched_at=100,last_native_activity=100,
            clock=self.clock,storage_available=lambda root:20000,scope='synthetic streaming component test only')
        return self.session

    def test_late_codec_expiry_prevents_run_and_preserves_incident(self):
        self.compose();render=self.codec.render;calls=0
        def delayed(messages):
            nonlocal calls
            calls+=1
            if calls==2:self.clock.value=121
            return render(messages)
        self.codec.render=delayed;self.session.parking.render=delayed
        self.start();self.assertEqual(self.request()[0],503)
        self.assertIn('late pre-RUN',str(self.finish()['error']))
        self.assertEqual(self.front.calls,[]);self.assertEqual(self.front.close_calls,0)

    def test_production_attach_does_not_accept_synthetic_profile(self):
        with self.assertRaises((RuntimeError,ValueError,KeyError)):
            S.attach(self.spec,streaming_sources=S.source_closure(),front=self.front,store=self.store,
                admitted_argv=[],launched_at=100,last_native_activity=100,guard=lambda:None)
        self.assertEqual(self.front.calls,[]);self.assertEqual(self.store.calls,[])

    def stream_request(self,session='alpha'):
        body=dict(model='synthetic',messages=[dict(role='user',content='hi')],
                  max_tokens=2,stream=True)
        c=http.client.HTTPConnection(*self.address,timeout=2)
        try:
            c.request('POST','/v1/chat/completions',json.dumps(body),
                      {'Content-Type':'application/json','X-Ownrt-Session':session})
            response=c.getresponse();return response.status,response.read()
        finally:c.close()

    def test_stream_and_nonstream_share_exact_composition_and_one_close(self):
        self.compose()
        self.assertIs(type(self.session),S.StreamingServingSession)
        self.assertIs(type(self.session.engine),E.StreamingCheckpointEngine)
        self.assertIs(type(self.session.lifecycle),L.StreamingSessionLifecycle)
        self.assertIs(type(self.session.lifecycle._service),CS.StreamingChatService)
        self.assertIs(self.session.engine.store._store,self.store)
        self.start();self.assertIs(type(self.session._server),H.StreamingServer)
        status,raw=self.stream_request();self.assertEqual(status,200)
        self.assertTrue(raw.endswith(b'data: [DONE]\n\n'))
        chunks=[json.loads(line[6:]) for line in raw.splitlines()
                if line.startswith(b'data: ') and line!=b'data: [DONE]']
        self.assertEqual(''.join(c['choices'][0]['delta'].get('content','') for c in chunks),'reply')
        status,normal=self.request('beta');self.assertEqual(status,200)
        self.assertEqual(chunks[-1]['usage'],normal['usage'])
        receipt=self.finish()['receipt']
        self.assertTrue(receipt['passed']);self.assertFalse(receipt['live_admission_claimed'])
        self.assertFalse(receipt['peer_receipt_proven'])
        self.assertEqual(receipt['schema'],'ownrt.streaming-serving-session.v1')
        self.assertEqual(receipt['streaming_source_sha256'],S.source_closure())
        self.assertEqual(len(receipt['streaming_closure_sha256']),64)
        self.assertEqual(receipt['native_controls'],2);self.assertEqual(self.front.close_calls,1)

    def test_stream_metadata_error_keeps_original_and_no_close(self):
        self.compose();failure=OSError('stream snapshot refused')
        def refused(cid):raise failure
        self.store.snapshot=refused;self.start()
        status,raw=self.stream_request();self.assertEqual(status,200);self.assertNotIn(b'[DONE]',raw)
        self.assertIs(self.finish()['error'],failure)
        self.assertIs(self.session.admission.failure,failure)
        self.assertEqual([c[0] for c in self.front.calls],['RUN'])
        self.assertEqual(self.front.close_calls,0)
        self.assertFalse(self.session.receipt()['passed'])


class AttachBoundaryTests(F.AttachBoundaryTests):
    @classmethod
    def setUpClass(cls):cls.shared_codec=C.PinnedChatCodec()

    def setUp(self):
        super().setUp()
        self.codec=copy.copy(self.shared_codec)
        self.profile['identity']['tokenizer_identity']=dict(self.codec.tokenizer_identity)
        self.profile['identity']['geometry'].update(vocab=self.codec.vocab,eos=248044)
        self.profile['native_stop_token_ids']=[248044,248046]
        # Exact production resource limits; no save/space-dependent work runs.
        self.profile['limits']=dict(P.LIMITS)
        self.front.ready['vocab']=self.codec.vocab
        self.sources=S.source_closure()

    def attach(self,**overrides):
        args=dict(front=self.front,store=self.store,admitted_argv=['synthetic-fixed-argv'],
            launched_at=self.now,last_native_activity=self.now,guard=lambda:self.guards.append(True),
            streaming_sources=self.sources)
        args.update(overrides)
        with patch.object(S,'PinnedChatCodec',return_value=self.codec):
            return S.attach(self.profile,**args)

    def test_separate_closure_missing_extra_or_changed_refuses_before_claim(self):
        for change in ('missing','extra','changed'):
            sources=dict(self.sources);key=next(iter(sources))
            if change=='missing':sources.pop(key)
            elif change=='extra':sources['foreign.py']='0'*64
            else:sources[key]='0'*64
            with self.subTest(change=change),self.assertRaisesRegex(S.SessionRefusal,'caller seal'):
                self.attach(streaming_sources=sources)
        self.assertFalse(hasattr(self.front,'_session_lifecycle_claim'))
        self.assertFalse(self.guards)

    def test_review_pin_or_source_drift_refuses_before_claim(self):
        with patch.object(S,'ROOT_GATE_SHA','0'*64):
            with self.assertRaisesRegex(S.SessionRefusal,'source/review drift'):self.attach()
        with patch.object(S,'LIFECYCLE_REVIEW_SHA','0'*64):
            with self.assertRaisesRegex(S.SessionRefusal,'source/review drift'):self.attach()
        target=S.HERE/'engine.py';read=Path.read_bytes
        def changed(path):return b'changed' if path==target else read(path)
        with patch.object(Path,'read_bytes',changed):
            with self.assertRaisesRegex(S.SessionRefusal,'source/review drift'):self.attach()
        self.assertFalse(hasattr(self.front,'_session_lifecycle_claim'))

    def test_streaming_origin_mismatch_refuses_before_claim(self):
        with patch.object(E,'__file__','/tmp/foreign-engine.py'):
            with self.assertRaisesRegex(S.SessionRefusal,'streaming module origin'):self.attach()
        self.assertFalse(hasattr(self.front,'_session_lifecycle_claim'))

    def test_exact_raw_types_and_ready_limits_retained(self):
        with self.assertRaisesRegex(S.SessionRefusal,'exact admitted'):
            self.attach(front=object())
        self.front.ready['max_control_ops']=15
        with self.assertRaisesRegex(S.SessionRefusal,'ready native limits'):self.attach()
        self.assertFalse(hasattr(self.front,'_session_lifecycle_claim'))

    def test_canonical_profile_validator_and_limits_unchanged(self):
        self.profile['limits']['requests']=17
        failure=ValueError('canonical changed profile refused')
        with patch.object(P,'validate_profile',side_effect=failure) as validate:
            with self.assertRaises(ValueError) as raised:self.attach()
        self.assertIs(raised.exception,failure)
        validate.assert_called_once_with(self.profile,check_fresh=False)
        self.assertFalse(hasattr(self.front,'_session_lifecycle_claim'))
        self.assertEqual(P.LIMITS['requests'],16)
        self.assertEqual(P.LIMITS['parking_bytes'],512*1024**2)
        self.assertEqual(P.LIMITS['planned_write_bytes'],768*1024**2)
        self.assertEqual(P.LIMITS['disk_floor_bytes'],27_000_000_000)

    def test_public_attach_retains_full_limits_and_additional_receipt_seal(self):
        session=self.attach();receipt=session.receipt()
        self.assertEqual(session.admission.request_limit,16)
        self.assertEqual(session.parking.budget_bytes,512*1024**2)
        self.assertEqual(session.engine.save_size_bound('valid',[1,2]),256*1024**2)
        self.assertEqual(receipt['streaming_source_sha256'],self.sources)
        self.assertFalse(receipt['live_admission_claimed'])
        self.assertFalse(receipt['passed']);self.assertIsNotNone(self.store._root_fd)
        self.assertIs(session.admission._raw,self.front)
        self.assertIs(session.engine.store._store,self.store)


if __name__=='__main__':unittest.main(verbosity=2)
