"""CPU contract and source-closure regressions for exact scheduled prefetch."""
import ast
import copy
from pathlib import Path
import unittest

import stream_contract as contract
import runtime_packet as packet
import stream_receipts as receipts


class ScheduledContract138(unittest.TestCase):
    def params(self):
        return contract.stream_params(145, 7, contract.QUALIFICATION_PROMPTS[0], 107, 'a'*64, 'kittens')

    def test_absent_schedule_retains_parent_parameter_keys(self):
        self.assertEqual(set(self.params()), set(contract.FIELDS))

    def test_schedule_roundtrips_exact_graph(self):
        params = dict(self.params(), schedule_position=7, schedule_sha256=contract.SCHEDULE_SHA256)
        graph = contract.build_chunk_graph(params)
        self.assertEqual(contract.parse_chunk_graph(graph, 145), params)

    def test_half_schedule_refused(self):
        for metadata in ({'schedule_position': 7}, {'schedule_sha256': contract.SCHEDULE_SHA256}):
            with self.assertRaises(ValueError):
                contract.validate_params(dict(self.params(), **metadata))

    def test_schedule_position_bad_types_and_bounds_refused(self):
        for position in (-1, 40, True, 2.5, '7', None):
            with self.assertRaises(ValueError):
                contract.validate_params(dict(self.params(), schedule_position=position, schedule_sha256=contract.SCHEDULE_SHA256))

    def test_schedule_wrong_file_refused(self):
        with self.assertRaises(ValueError):
            contract.validate_params(dict(self.params(), schedule_position=7, schedule_sha256='b'*64))

    def test_stream_params_optional_schedule(self):
        params = contract.stream_params(145, 7, contract.QUALIFICATION_PROMPTS[0], 107, 'a'*64, 'kittens',
            schedule_position=7, schedule_sha256=contract.SCHEDULE_SHA256)
        self.assertEqual(params['schedule_position'], 7)

    def test_schedule_cannot_alter_qualification_graph(self):
        params = contract.qualification_params(145, 1)[0]
        with self.assertRaises(ValueError):
            contract.validate_params(dict(params, schedule_position=0, schedule_sha256=contract.SCHEDULE_SHA256))

    def test_consumer_hook_keeps_native_prechecks_and_fingerprint(self):
        raw = (packet.PARENT/'source/scripts/pipeline_node.py').read_bytes()
        transformed = packet.pipeline_source(raw).decode()
        ast.parse(transformed)
        self.assertIn('text_prefetch138.consume_prefetch(clip, text, mode, clip_index, run_name)', transformed)
        self.assertLess(transformed.index('window.precheck(clip, text'), transformed.index('text_prefetch138.consume_prefetch('))
        self.assertLess(transformed.index('text_prefetch138.consume_prefetch('), transformed.index("pipeline.cond_fingerprint(conditioning)"))
        self.assertIn("detail['window_encode'] = window.info_for((tag, clip_index))", transformed)
        self.assertIn("server['extension_sha256s'][name] == actual", transformed)
        self.assertIn('torch.are_deterministic_algorithms_enabled()', transformed)

    def test_consumer_transform_refuses_changed_anchor(self):
        raw = (packet.PARENT/'source/scripts/pipeline_node.py').read_bytes()
        with self.assertRaises(RuntimeError):
            packet.pipeline_source(raw.replace(b'conditioning, detail = pipeline.run_ahead(', b'conditioning, altered = pipeline.run_ahead('))

    def test_hook_is_identical_in_both_native_module_copies(self):
        self.assertEqual(packet.pipeline_source((packet.PARENT/'source/scripts/pipeline_node.py').read_bytes()),
                         packet.pipeline_source((packet.PARENT/'source/custom_nodes/ltx_pipeline_lab/__init__.py').read_bytes()))

    def test_mode_record_rejects_invalid_values(self):
        for value in (None, True, 'guess', 0):
            with self.assertRaises(ValueError):
                receipts.validate_f32_scan_record({'server_options': {'text_prefetch': value}})

    def test_companion_mode_must_agree(self):
        with self.assertRaises(ValueError):
            receipts.validate_f32_scan_record({'server_options': {'text_prefetch': 'off'}},
                                             {'server_options': {'text_prefetch': 'scheduled'}})

    def test_qualification_cut_requires_prefetch_hit(self):
        for kind in ('qualify-graph', 'qualify-repeat'):
            with self.assertRaises(ValueError):
                receipts.validate_text_prefetch_record({'server_options': {'text_prefetch': 'scheduled'},
                    'kind': kind, 'chunk_index': 2, 'text': {'reused': False}})

    def test_off_has_no_new_required_text_evidence(self):
        self.assertIsNone(receipts.validate_text_prefetch_record({'server_options': {'text_prefetch': 'off'},
            'kind': 'qualify-graph', 'chunk_index': 2, 'text': {'reused': False}}))

    def test_mode_suffix_separates_candidate_run(self):
        env = dict(LTX_STREAM_FRAMES='145', LTX_SAMPLER_PLACEMENT='two-way20-28', LTX_ANCHOR='frame',
            LTX_DECODER_GRAPH='1', LTX_ANCHOR_DECODE='cone', LTX_BENCODE_OVERLAP='1', LTX_PREP_AHEAD='1', LTX_SNAPSHOT_MODE='fingerprint')
        self.assertEqual(packet.expected_run_name(dict(env, LTX_TEXT_PREFETCH='scheduled')),
                         packet.expected_run_name(env) + '-tpscheduled')

    def test_pipeline_done_is_published_after_running_count(self):
        raw = (packet.PARENT/'source/scripts/ltx_pipeline.py').read_bytes()
        value = packet.pipeline_completion_source(raw).decode()
        self.assertLess(value.index('_RUNNING[0] -= 1'), value.index('job.done.set()'))
        self.assertEqual(value.replace("                with _LOCK:\n                    _RUNNING[0] -= 1\n                job.done.set()",
                                      "                job.done.set()\n                with _LOCK:\n                    _RUNNING[0] -= 1"), raw.decode())
