"""CPU proofs for C65 reconstruction, terminal actions and control gating."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import main_history_contract_probe as p


def response(name='write', arguments=None, finish='tool_calls'):
    if arguments is None:
        arguments = {'path': '/app/AUDIT.md', 'content': '6 | time_limited\n7 | numeric_range\n8 | classify_unique\n'}
    return {'choices': [{'finish_reason': finish, 'message': {'role': 'assistant', 'content': None,
        'tool_calls': [{'id': 'test-call', 'type': 'function', 'function': {
            'name': name, 'arguments': json.dumps(arguments)}}]}}],
        'usage': {'prompt_tokens': 6026, 'completion_tokens': 211}}


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='c65-test-')
        self.folder = Path(self.temp.name)
        self.body = {'model': 'test-model', 'stream': True, 'stream_options': {'include_usage': True},
            'max_completion_tokens': 16384, 'messages': [
                {'role': 'system', 'content': 'Original instructions'}, {'role': 'user', 'content': 'Original task'}]
                + [{'role': 'assistant', 'content': f'past fact {n}'} for n in range(3, 602)],
            'tools': [{'type': 'function', 'function': {'name': 'write', 'parameters': {'type': 'object'}}}]}
        root = self.folder / 'init'
        s = p.ck.Session(root, p.SESSION)
        self.state = s.state
        self.state.update(cut=583, boundary=p.ck.fingerprint(self.body['messages'][2:585]),
                          notes='RULES\n(none)\nSTATE\nold: remembered\nOPEN\n')
        self.archive = [{'n': n, 'role': 'assistant', 'message': self.body['messages'][n - 1],
                         'text': p.ck.text_of(self.body['messages'][n - 1])} for n in range(3, 586)]
        self.notes = [{'upto': 585, 'notes': self.state['notes']}]
        (self.folder / 'state').mkdir()
        p.dump(self.folder / 'state/state.json', self.state)
        (self.folder / 'state/archive.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in self.archive))
        (self.folder / 'state/notes-history.jsonl').write_text(json.dumps(self.notes[0]) + '\n')
        p.dump(self.folder / 'request-body.json', self.body)
        p.dump(self.folder / 'manifest.json', {'session_header': p.SESSION,
            'expected_lines': ['EXPECTED_ANSWER_SENTINEL_NOT_FOR_MODEL'],
            'original_control_content': 'ORIGINAL_ANSWER_SENTINEL_NOT_FOR_MODEL'})

    def tearDown(self):
        self.temp.cleanup()

    def test_cutoff_rejects_future_archive_notes_and_bad_boundary(self):
        p.validate_cutoff(self.state, self.archive, self.notes, self.body)
        future = copy.deepcopy(self.archive)
        future.append(dict(future[-1], n=586))
        with self.assertRaises(ValueError):
            p.validate_cutoff(self.state, future, self.notes, self.body)
        with self.assertRaises(ValueError):
            p.validate_cutoff(self.state, self.archive, self.notes + [{'upto': 603}], self.body)
        with self.assertRaises(ValueError):
            p.validate_cutoff(dict(self.state, boundary='wrong'), self.archive, self.notes, self.body)

    def test_production_capture_suffix_only_and_no_grader_answers(self):
        control = p.run_arm(self.folder, 'control', lambda _: p.fake_response())
        candidate = p.run_arm(self.folder, 'candidate', lambda _: p.fake_response())
        a, b = control['calls'][0]['request'], candidate['calls'][0]['request']
        expected = copy.deepcopy(a)
        expected['messages'][0]['content'] += p.CONTRACT
        self.assertEqual(expected, b)
        self.assertEqual(len(a['messages']), 19)
        self.assertFalse(a['stream'])
        self.assertNotIn('stream_options', a)
        self.assertEqual(a['max_completion_tokens'], 16384)
        self.assertNotIn('temperature', a)
        for row in (control, candidate):
            self.assertEqual(row['call_kinds'], ['main'])
            self.assertEqual(row['recalls_served'], 0)
            text = json.dumps(row['calls'][0]['request'])
            self.assertNotIn('EXPECTED_ANSWER_SENTINEL_NOT_FOR_MODEL', text)
            self.assertNotIn('ORIGINAL_ANSWER_SENTINEL_NOT_FOR_MODEL', text)

    def test_terminal_external_action_not_executed(self):
        target = self.folder / 'must-not-exist'
        row = p.run_arm(self.folder, 'control', lambda _: response('bash', {'command': f'touch {target}'}))
        self.assertEqual(len(row['calls']), 1)
        self.assertFalse(row['write']['supported'])
        self.assertEqual(row['task_tools_executed'], 0)
        self.assertFalse(target.exists())

    def test_recall_is_served_only_from_frozen_archive(self):
        replies = [response('recall', {'pattern': 'past fact 584', 'last': 1}), response()]
        row = p.run_arm(self.folder, 'candidate', lambda _: replies.pop(0))
        self.assertEqual(row['recalls_served'], 1)
        self.assertEqual(row['recalls_requested'], 1)
        self.assertEqual(len(row['calls']), 2)
        tool = row['calls'][1]['request']['messages'][-1]
        self.assertEqual(tool['role'], 'tool')
        self.assertIn('past fact 584', tool['content'])
        self.assertEqual(row['task_tools_executed'], 0)

    def test_control_gate_requires_original_payload_count_and_no_recall(self):
        row = p.run_arm(self.folder, 'control', lambda _: response())
        content = p.audit_write(response())['content']
        self.assertTrue(p.control_matches(row, content))
        changed = copy.deepcopy(row)
        changed['calls'][0]['response']['usage']['prompt_tokens'] = 6027
        self.assertFalse(p.control_matches(changed, content))
        self.assertFalse(p.control_matches(dict(row, recalls_requested=1), content))
        self.assertFalse(p.control_matches(row, content + 'extra\n'))

    def test_truncation_other_tools_and_multiple_calls_are_not_audit_writes(self):
        self.assertFalse(p.audit_write(response(finish='length'))['supported'])
        self.assertFalse(p.audit_write(response(finish='stop'))['supported'])
        self.assertFalse(p.audit_write(response('read', {'path': '/app/AUDIT.md'}))['supported'])
        multi = response()
        multi['choices'][0]['message']['tool_calls'].append(multi['choices'][0]['message']['tool_calls'][0])
        self.assertFalse(p.audit_write(multi)['supported'])

    def test_transport_error_retains_failed_request_and_restores_global_contract(self):
        old = p.ck.MEMORY_NOTE
        def failed(request):
            raise OSError('mock transport failure')
        with self.assertRaises(OSError) as caught:
            p.run_arm(self.folder, 'candidate', failed)
        self.assertEqual(p.ck.MEMORY_NOTE, old)
        self.assertEqual(len(caught.exception.probe_calls), 1)
        self.assertIsNone(caught.exception.probe_calls[0]['response'])


if __name__ == '__main__':
    unittest.main()
