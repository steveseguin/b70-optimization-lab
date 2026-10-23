"""CPU-only subprocess tests for postreply disposition; no native imports."""
import subprocess
import sys
import tempfile
import unittest

from client_v2 import NativeFront, encode_request


MOCK = r'''
import json, sys, time
mode, maximum = sys.argv[1], int(sys.argv[2])
def event(**row): print(json.dumps(row), flush=True)
event(event='ready', protocol='ownrt.request-front.v2', model_loads=1, experimental=True,
      context=4096, vocab=248320, max_requests=maximum,
      max_control_ops=maximum+1 if mode=='bad-ready' else maximum)
completed = controls = 0
pending = None
def stopped(reason):
    event(event='stopped', reason=reason, safe_to_exit=True, completed_requests=completed,
          completed_controls=controls, discarded_pending=pending is not None,
          pending_request_id=pending['id'] if pending else '')
for line in sys.stdin:
    fields = line.rstrip('\n').split('\t')
    if fields == ['QUIT']:
        stopped('quit'); sys.exit(0)
    if fields[0] == 'RUN':
        assert pending is None and completed < maximum
        _, rid, cap, restore, save, ids = fields
        assert save == '-'
        tokens = list(map(int, ids.split())) + [17]
        pending = dict(id=rid, tokens=tokens)
        event(event='request-start', id=rid)
        event(event='token', id=rid, index=0, token_id=17)
        event(event='request-complete', id=rid, result='requests/'+rid+'/result.json',
              generated_tokens=1, owner_resident=True, request_quiesced=True,
              save_pending=True, pending_request_id='foreign' if mode=='bad-pending' else rid,
              processed_tokens=0 if mode=='short-restored' else len(tokens)-1,
              visible_tokens=1 if mode=='short-restored' else len(tokens), pending_token=17)
        completed += 1
        continue
    assert pending is not None
    command, oid, rid = fields[:3]
    assert rid == pending['id']
    if mode == 'stall-control': time.sleep(20)
    if mode == 'fatal-control':
        event(event='fatal', error='injected save failure'); sys.exit(1)
    row = dict(operation_id=oid, request_id=rid, request_disposed=True,
               request_quiesced=True, final_request=completed==maximum)
    if command == 'SAVE':
        _, _, _, sid, ids = fields
        assert list(map(int, ids.split())) == pending['tokens']
        row.update(event='checkpoint-saved', checkpoint_id=sid, checkpoint_path=sid,
                   path_scope='startup-checkpoint-root', receipt='operations/'+oid+'/save.json',
                   manifest_sha256='a'*64, processed_tokens=len(pending['tokens'])-1,
                   visible_tokens=len(pending['tokens']), pending_token=17)
        if mode.startswith('bad-save-'):
            key=mode.removeprefix('bad-save-')
            row[key] = {'receipt':'../foreign', 'checkpoint_path':'../foreign',
                        'manifest_sha256':'not-a-hash', 'pending_token':18,
                        'request_quiesced':False, 'final_request':1}[key]
    else:
        assert command == 'RELEASE'
        row['event']='request-released'
    event(**row)
    controls += 1
    pending = None
    if completed == maximum:
        stopped('request-limit'); sys.exit(0)
stopped('eof')
'''


class ClientV2Tests(unittest.TestCase):
    def owner(self, mode='ok', maximum=3, timeout=2):
        log = tempfile.TemporaryFile()
        proc = subprocess.Popen([sys.executable, '-u', '-c', MOCK, mode, str(maximum)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
        def cleanup():
            # Only the Python CPU mock is ever terminated by this test fixture.
            if proc.poll() is None:
                proc.terminate()
            proc.wait(timeout=3)
            proc.stdin.close(); proc.stdout.close(); log.close()
        self.addCleanup(cleanup)
        front = NativeFront(proc, context=4096, vocab=248320, max_requests=maximum,
                            request_timeout=timeout)
        self.addCleanup(front.selector.close)
        return front

    def test_postreply_save_release_and_final_save_share_one_owner(self):
        front = self.owner()
        pid = front.process.pid
        for i in range(3):
            tokens = [1, i]
            response = front.request('r'+str(i), tokens, 8)
            self.assertEqual(response['tokens'], [17])
            self.assertEqual(front.state, 'awaiting-disposition')
            if i == 1:
                front.release('op1')
            else:
                row = front.save('op'+str(i), 'state'+str(i), tokens + response['tokens'])
                self.assertEqual(row['checkpoint_id'], 'state'+str(i))
            self.assertEqual(front.process.pid, pid)
        self.assertEqual(front.state, 'draining')
        row = front.close()
        self.assertEqual(row['completed_controls'], 3)
        self.assertFalse(row['discarded_pending'])

    def test_next_request_requires_disposition(self):
        front = self.owner()
        front.request('a', [1], 1)
        with self.assertRaisesRegex(RuntimeError, 'not ready'):
            front.request('b', [1], 1)
        self.assertEqual(front.state, 'awaiting-disposition')
        front.release('release-a')
        front.request('b', [2], 1)
        with self.assertRaisesRegex(ValueError, 'duplicate operation'):
            front.release('release-a')
        front.release('release-b')
        front.close()

    def test_pending_final_request_can_be_explicitly_discarded(self):
        front = self.owner(maximum=1)
        front.request('a', [1], 1)
        self.assertIsNone(front.process.poll())
        row = front.close()
        self.assertTrue(row['discarded_pending'])
        self.assertEqual(row['pending_request_id'], 'a')
        self.assertEqual(row['completed_controls'], 0)

    def test_bad_save_input_does_not_consume_pending_state(self):
        front = self.owner(maximum=1)
        front.request('a', [1], 1)
        for checkpoint, tokens in ((None,[1,17]),('../x',[1,17]),('x',[1]),
                                   ('x',[1,18]),('x',[True,17]),('x',[-1,17])):
            with self.subTest(checkpoint=checkpoint,tokens=tokens), self.assertRaises(ValueError):
                front.save('save-a', checkpoint, tokens)
            self.assertEqual(front.state, 'awaiting-disposition')
        front.save('save-a', 'x', [1,17]); front.close()
        with self.assertRaises(RuntimeError):
            front.release('already-finished')

    def test_immediate_save_is_refused_before_write(self):
        with self.assertRaisesRegex(ValueError, 'postreply'):
            encode_request('a',[1],1,context=16,vocab=20,save='x')

    def test_foreign_descriptor_and_control_budget_refuse(self):
        with self.assertRaisesRegex(RuntimeError, 'admission mismatch'):
            self.owner('bad-ready')
        front = self.owner('bad-pending')
        with self.assertRaisesRegex(RuntimeError, 'descriptor mismatch'):
            front.request('a',[1],1)
        self.assertEqual(front.state,'halted')

    def test_restored_descriptor_cannot_omit_input_or_generated_tokens(self):
        front = self.owner('short-restored')
        with self.assertRaisesRegex(RuntimeError, 'descriptor mismatch'):
            front.request('a',[1,2],1,restore='saved')
        self.assertEqual(front.state,'halted')

    def test_bad_or_failed_save_acknowledgement_halts_channel(self):
        modes = ['fatal-control'] + ['bad-save-'+key for key in
            ('receipt','checkpoint_path','manifest_sha256','pending_token','request_quiesced','final_request')]
        for mode in modes:
            with self.subTest(mode=mode):
                front = self.owner(mode)
                front.request('a',[1],1)
                with self.assertRaises(RuntimeError): front.save('op','x',[1,17])
                self.assertEqual(front.state,'halted')
                with self.assertRaises(RuntimeError): front.request('b',[1],1)

    def test_control_timeout_retains_owner_for_coordinator(self):
        front = self.owner('stall-control', timeout=.05)
        front.request('a',[1],1)
        with self.assertRaises(TimeoutError): front.save('op','x',[1,17])
        self.assertIsNone(front.process.poll())
        self.assertEqual(front.state,'halted')
        with self.assertRaisesRegex(RuntimeError,'coordinator'): front.close()


if __name__ == '__main__': unittest.main()
