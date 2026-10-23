"""Actual loopback HTTP + real facade/codec with retained device token replies.

No native owner, RUN, checkpoint mutation or live-serving qualification. A
sequence replay owner accepts exactly the retained fresh-A then fresh-B inputs.
"""
import hashlib
import http.client
import json
from pathlib import Path
import sys
import threading
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools/ctxkeeper'))
from parking import Parking
from chat_codec import PinnedChatCodec
from chat_http import make_server
from chat_service import ChatService
from test_chat_service_replay import PACKET, ReplayOwner


class SequentialReplayOwner(ReplayOwner):
    def __init__(self, identity, rows):
        self.rows = rows
        self.histories = []
        super().__init__(identity, rows[0][0], rows[0][1]['tokens'])

    def run_turn(self, parking, session, messages, *, request_id, max_new):
        if self.calls >= len(self.rows):
            raise RuntimeError('replay exhausted; never repeat or generate')
        prompt, result = self.rows[self.calls]
        self.recorded_input, self.recorded_tokens = prompt, result['tokens']
        response = super().run_turn(parking, session, messages,
                                    request_id=request_id, max_new=max_new)
        self.histories.append(list(self.raw_history))
        return response


class HTTPRecordedChatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec = PinnedChatCodec()
        cls.inventory = {row['path']: row for row in json.loads(
            (PACKET / 'evidence/closeout-inventory.json').read_text())['files']}
        cls.identity = json.loads((HERE / 'checkpoint-fixtures-p198/admitted-engine-identity.json').read_text())
        cls.raw_prompts = {p['id']: p['prompt'] for p in json.loads(
            (ROOT / 'repro/rapid-model-snapshots-b70/realistic-suite-v1.json').read_text())['prompts']}

    def retained(self, path):
        raw = path.read_bytes()
        admitted = self.inventory[str(path.relative_to(ROOT))]
        self.assertEqual(hashlib.sha256(raw).hexdigest(), admitted['sha256'])
        self.assertEqual(len(raw), admitted['bytes'])
        return raw

    def setUp(self):
        self.rows, self.payloads = [], []
        model = 'qwen38-flash-next-ud-iq3-xxs-experimental'
        for request, prompt in (('fresh-a', 'incident-retrospective'), ('fresh-b', 'decision-memo')):
            base = PACKET / 'evidence/device-p198-lifecycle-A-a/owner/requests' / request
            recorded = json.loads(self.retained(base / 'result.json'))
            tokens = [int(x) for x in self.retained(base / 'input.tokens').split()]
            self.rows.append((tokens, recorded))
            self.payloads.append(dict(model=model, messages=[{'role': 'user', 'content': self.raw_prompts[prompt]}],
                                      max_tokens=len(recorded['tokens'])))
        self.owner = SequentialReplayOwner(self.identity, self.rows)
        parking = Parking(self.owner, self.codec.render, self.codec.encode, budget_bytes=0)
        self.service = ChatService(self.owner, parking, self.codec, model=model,
                                   native_stop_token_ids={248044, 248046}, clock=lambda: 0)
        self.server = make_server(self.service)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval': .01}, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.assertFalse(self.thread.is_alive())

    def post(self, payload):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=2)
        try:
            connection.request('POST', '/v1/chat/completions', body=json.dumps(payload, ensure_ascii=False).encode(),
                               headers={'Content-Type': 'application/json', 'X-Ownrt-Session': 'retained-replay'})
            response = connection.getresponse()
            self.assertEqual(response.version, 10)
            self.assertEqual(response.getheader('Connection'), 'close')
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def assert_two_exact_replies(self):
        ids = []
        for payload, (prompt, recorded) in zip(self.payloads, self.rows):
            status, response = self.post(payload)
            self.assertEqual(status, 200)
            self.assertRegex(response['id'], r'^chatcmpl-h[0-9a-f]{32}-[0-9a-f]{16}$')
            ids.append(response['id'])
            expected_text = self.codec.decode(recorded['tokens'])
            self.assertEqual(response, {
                'id': response['id'], 'object': 'chat.completion', 'created': 0,
                'model': self.service.model,
                'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': expected_text},
                             'finish_reason': 'length'}],
                'usage': {'prompt_tokens': recorded['prompt_tokens'],
                          'completion_tokens': len(recorded['tokens']),
                          'total_tokens': recorded['prompt_tokens'] + len(recorded['tokens'])}})
            self.assertEqual(self.codec.encode(response['choices'][0]['message']['content']), recorded['tokens'])
            self.assertEqual(self.owner.histories[-1], prompt + recorded['tokens'])
        self.assertEqual(len(set(ids)), 2)
        self.assertEqual(self.owner.calls, 2)
        self.assertIsNone(self.service.halted_reason)
        self.assertEqual([len(row[1]['tokens']) for row in self.rows], [256, 128])
        self.assertEqual([len(row[0]) for row in self.rows], [87, 60])

    def test_fresh_a_then_b_through_real_http_facade_codec(self):
        self.assert_two_exact_replies()

    def test_invalid_sampling_never_reaches_replay_owner(self):
        for field, value in (('temperature', .7), ('top_p', .5), ('n', 2), ('stream', True)):
            status, response = self.post(self.payloads[0] | {field: value})
            self.assertEqual(status, 400)
            self.assertEqual(response, {'error': {'message': 'chat request refused'}})
            self.assertEqual(self.owner.calls, 0)
        self.assert_two_exact_replies()


if __name__ == '__main__':
    unittest.main(verbosity=2)
