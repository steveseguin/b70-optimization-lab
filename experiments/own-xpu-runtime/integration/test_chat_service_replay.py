"""Real pinned codec + chat facade over retained device replies; no native RUN.

This tests response assembly and exact prompt admission, not live serving. The
replay owner requires the original recorded prompt and returns recorded IDs.
"""
import hashlib
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools/ctxkeeper'))
from parking import Parking
from chat_codec import PinnedChatCodec
from chat_service import ChatService

PACKET = HERE.parent / 'stage2/packet198-postreply-checkpoint'


class ReplayOwner:
    def __init__(self, identity, recorded_input, recorded_tokens):
        self._identity = identity
        self.vocab, self.context = identity['geometry']['vocab'], identity['geometry']['context']
        self.recorded_input, self.recorded_tokens = recorded_input, recorded_tokens
        self.calls = 0

    def run_turn(self, parking, session, messages, *, request_id, max_new):
        self.calls += 1
        actual = parking.prefix(messages)
        if actual != self.recorded_input or max_new != len(self.recorded_tokens):
            raise RuntimeError('replay refuses input outside recorded device request')
        self.raw_history = actual + self.recorded_tokens
        return {'response': {'tokens': list(self.recorded_tokens)}}


class RecordedChatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec = PinnedChatCodec()
        cls.inventory = {row['path']: row for row in json.loads((PACKET / 'evidence/closeout-inventory.json').read_text())['files']}
        cls.identity = json.loads((HERE / 'checkpoint-fixtures-p198/admitted-engine-identity.json').read_text())
        cls.raw_prompts = {p['id']: p['prompt'] for p in json.loads((ROOT / 'repro/rapid-model-snapshots-b70/realistic-suite-v1.json').read_text())['prompts']}

    def retained(self, path):
        raw = path.read_bytes()
        evidence = self.inventory[str(path.relative_to(ROOT))]
        self.assertEqual(hashlib.sha256(raw).hexdigest(), evidence['sha256'])
        self.assertEqual(len(raw), evidence['bytes'])
        return raw

    def test_recorded_device_prompts_and_replies_through_chat_facade(self):
        for request, prompt_id in (('fresh-a', 'incident-retrospective'), ('fresh-b', 'decision-memo')):
            with self.subTest(request=request):
                base = PACKET / 'evidence/device-p198-lifecycle-A-a/owner/requests' / request
                recorded = json.loads(self.retained(base / 'result.json'))
                tokens = [int(i) for i in self.retained(base / 'input.tokens').split()]
                owner = ReplayOwner(self.identity, tokens, recorded['tokens'])
                parking = Parking(owner, self.codec.render, self.codec.encode, budget_bytes=0)
                service = ChatService(owner, parking, self.codec, model='qwen38-flash-next-ud-iq3-xxs-experimental',
                                      native_stop_token_ids={248044, 248046}, clock=lambda: 0)
                response = service.complete({'model': service.model, 'messages': [{'role': 'user', 'content': self.raw_prompts[prompt_id]}],
                                             'max_tokens': len(recorded['tokens'])}, session='replay', request_id=request)
                self.assertEqual(owner.calls, 1)
                self.assertEqual(owner.raw_history, tokens + recorded['tokens'])
                self.assertEqual(response['usage']['prompt_tokens'], recorded['prompt_tokens'])
                self.assertEqual(response['usage']['completion_tokens'], len(recorded['tokens']))
                self.assertEqual(response['choices'][0]['finish_reason'], 'length')
                self.assertEqual(self.codec.encode(response['choices'][0]['message']['content']), recorded['tokens'])


if __name__ == '__main__':
    unittest.main()
