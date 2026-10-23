"""Tampered-result refusals only; no model, native, HTTP or qualified fixture."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

import audit_p199_result as A


class Codec:
    vocab = 248320
    def decode(self, ids):
        return repr(ids)


class AuditTests(unittest.TestCase):
    def test_finish_reason_and_usage_cannot_hide_terminal_token(self):
        response = dict(id='chatcmpl-r1', object='chat.completion', model='synthetic', created=0,
            choices=[dict(index=0, message=dict(role='assistant', content='[7]'), finish_reason='stop')],
            usage=dict(prompt_tokens=2, completion_tokens=2, total_tokens=4))
        A.check_http(response, 'r1', [1,2], [7,248046], 2, Codec(), 'synthetic')
        for key, value in [('finish_reason', 'length'), ('message', dict(role='assistant',content='[7, 248046]'))]:
            changed = copy.deepcopy(response);changed['choices'][0][key] = value
            with self.assertRaisesRegex(ValueError, 'finish-reason'):
                A.check_http(changed, 'r1', [1,2], [7,248046], 2, Codec(), 'synthetic')
        response['usage']['completion_tokens'] = 1
        with self.assertRaisesRegex(ValueError, 'usage'):
            A.check_http(response, 'r1', [1,2], [7,248046], 2, Codec(), 'synthetic')

    def test_final_control_identity_and_release_are_required(self):
        control = dict(operation_id='parking-6', request_id='r6', event='request-released',
                       request_disposed=True, request_quiesced=True, final_request=True)
        A.check_control(control, 5, 'r6')
        for key,value in [('request_id','r5'),('event','checkpoint-saved'),('final_request',False),('request_quiesced',False)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                A.check_control(control | {key:value}, 5, 'r6')

    def test_unfinished_and_discarded_results_refuse(self):
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            A.check_terminal({'passed':False})
        row = dict(passed=True, device_executed=True, native_process_count=1, model_loads=1,
            child_still_running=False, safe_to_exit=True, devices_drained=True, submission_eligible=False,
            save_count=5, release_count=1, stop_reasons=[], completed_requests=A.IDS,
            correctness=dict.fromkeys(A.CORRECTNESS, True), stopped=dict(event='stopped', reason='request-limit',
                safe_to_exit=True, completed_requests=6, completed_controls=6, discarded_pending=False, pending_request_id=''))
        A.check_terminal(row)
        row['stopped']['discarded_pending'] = True
        with self.assertRaisesRegex(ValueError, 'disposition'):
            A.check_terminal(row)

    def test_remaining_tensor_hash_and_extent_must_match(self):
        data = b'\x01\x00\x00\x00'
        checksum = hashlib.sha256(data).hexdigest()
        manifest = dict(token_state=dict(length=1,tokens_sha256=checksum),
                        blobs=[dict(name='small',bytes=4,sha256=checksum)])
        expected,_ = A.manifest_map(manifest)
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            for leaf in ('manifest.json','fields.tsv'):(folder/leaf).write_text('synthetic')
            for leaf in expected:(folder/leaf).write_bytes(data)
            self.assertEqual(A.hash_remaining(folder,manifest,expected),dict(files=2,bytes=8))
            (folder/'small.bin').write_bytes(b'\x02\x00\x00\x00')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):A.hash_remaining(folder,manifest,expected)
            (folder/'small.bin').write_bytes(data+b'x')
            with self.assertRaisesRegex(ValueError,'extent'):A.hash_remaining(folder,manifest,expected)


if __name__ == '__main__':
    unittest.main()
