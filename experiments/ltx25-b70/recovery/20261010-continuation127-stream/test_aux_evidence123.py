"""CPU receipt tests for actual sampled margins; no claim about unsampled peaks."""
import copy
import unittest

import residency123 as aux
import stream_contract as c
import stream_receipts as sr
from test_gate_receipts import passing, decide, reference_doc


def workspace(owner):
    return {key: dict(aux.check_aux_free(10*aux.GIB, before), owner=owner, device='xpu:2', mode='xpu2')
            for key, before in [('before', True), ('after', False)]}


def fixture(anchored=False):
    free = dict(zip(('xpu:0', 'xpu:1', 'xpu:2', 'xpu:3'), [10*aux.GIB, 10*aux.GIB, 10*aux.GIB, 13*aux.GIB]))
    r = {'run_name': 'chunk', 'prompt_id': 'prompt', 'anchor_in': {} if anchored else None,
         'server_options': {'aux_residency': 'xpu2'}, 'aux_upsampler_workspace': workspace('upsampler'),
         'memory': {'before': {'free': dict(free)}, 'after': {'free': dict(free)},
                    'conditioning': [{'stage': stage, 'free_before': dict(free), 'free_after': dict(free)}
                                     for stage in (['A', 'B'] if anchored else [])]}}
    d = {'run_name': 'chunk', 'prompt_id': 'prompt', 'aux_residency': 'xpu2', 'audio_device': 'xpu:2',
         'aux_audio_workspace': workspace('audio')}
    return r, d


def gate_fixture():
    rows, decodes, captures = passing(frames=145, anchor='frame', decoder_graph=0)
    for r in rows:
        sample, d = fixture(r.get('anchor_in') is not None)
        r['memory'] = sample['memory']
        r['aux_upsampler_workspace'] = sample['aux_upsampler_workspace']
        r['server_options'].update(aux_residency='xpu2', residency_qualification_id=c.residency_qualification_id(r['qualification_id'], 'xpu2'))
        decodes[r['run_name']].update({k: v for k, v in d.items() if k not in ('run_name', 'prompt_id')})
    return rows, decodes, captures


class AuxiliaryEvidenceTests(unittest.TestCase):
    def test_unanchored_two_sample_sites(self): self.assertEqual(aux.validate_aux_evidence(*fixture())['sample_sites'], 2)
    def test_anchored_six_sample_sites(self): self.assertEqual(aux.validate_aux_evidence(*fixture(True))['sample_sites'], 6)
    def test_standalone_receipt(self): self.assertTrue(aux.validate_aux_evidence(fixture()[0])['enabled'])
    def test_standalone_decode(self): self.assertTrue(aux.validate_aux_evidence(None, fixture()[1])['enabled'])
    def test_legacy_unchanged(self): self.assertFalse(aux.validate_aux_evidence({'server_options': {}})['enabled'])
    def test_missing_upsampler(self):
        r, d = fixture(); del r['aux_upsampler_workspace']
        with self.assertRaisesRegex(ValueError, 'upsampler workspace samples missing'): aux.validate_aux_evidence(r, d)
    def test_missing_audio(self):
        r, d = fixture(); del d['aux_audio_workspace']
        with self.assertRaisesRegex(ValueError, 'audio workspace samples missing'): aux.validate_aux_evidence(r, d)
    def test_missing_before(self):
        r, d = fixture(); del r['aux_upsampler_workspace']['before']
        with self.assertRaises(ValueError): aux.validate_aux_evidence(r, d)
    def test_missing_after(self):
        r, d = fixture(); del d['aux_audio_workspace']['after']
        with self.assertRaises(ValueError): aux.validate_aux_evidence(r, d)
    def test_wrong_workspace_owner(self):
        r, d = fixture(); d['aux_audio_workspace']['before']['owner'] = 'upsampler'
        with self.assertRaises(ValueError): aux.validate_aux_evidence(r, d)
    def test_wrong_workspace_device(self):
        r, d = fixture(); r['aux_upsampler_workspace']['after']['device'] = 'xpu:0'
        with self.assertRaises(ValueError): aux.validate_aux_evidence(r, d)
    def test_forged_passed(self):
        r, d = fixture(); r['aux_upsampler_workspace']['after']['passed'] = 1
        with self.assertRaises(ValueError): aux.validate_aux_evidence(r, d)
    def test_forged_before(self):
        r, d = fixture(); d['aux_audio_workspace']['before']['before'] = 1
        with self.assertRaises(ValueError): aux.validate_aux_evidence(r, d)
    def test_weakened_budget(self):
        r, d = fixture(); d['aux_audio_workspace']['before']['workspace_allowance_bytes'] = 0
        with self.assertRaises(ValueError): aux.validate_aux_evidence(r, d)
    def test_before_workspace_low(self):
        r, d = fixture(); r['aux_upsampler_workspace']['before']['free_bytes'] = int(4.75*aux.GIB)-1
        with self.assertRaises(ValueError): aux.validate_aux_evidence(r, d)
    def test_after_workspace_low(self):
        r, d = fixture(); d['aux_audio_workspace']['after']['free_bytes'] = int(2.75*aux.GIB)-1
        with self.assertRaises(ValueError): aux.validate_aux_evidence(r, d)
    def test_every_card_and_request_boundary(self):
        for phase in ('before', 'after'):
            for card, floor in zip(('xpu:0', 'xpu:1', 'xpu:2', 'xpu:3'), (8, 8, 2, 9)):
                with self.subTest(phase=phase, card=card):
                    r, d = fixture(); r['memory'][phase]['free'][card] = int((floor+.75)*aux.GIB)
                    aux.validate_aux_evidence(r, d)
                    r['memory'][phase]['free'][card] -= 1
                    with self.assertRaisesRegex(ValueError, 'misses floor plus 0.75'): aux.validate_aux_evidence(r, d)
    def test_conditioning_boundaries(self):
        for index in (0, 1):
            for phase in ('free_before', 'free_after'):
                with self.subTest(index=index, phase=phase):
                    r, d = fixture(True); r['memory']['conditioning'][index][phase]['xpu:3'] = int(9.75*aux.GIB)-1
                    with self.assertRaises(ValueError): aux.validate_aux_evidence(r, d)
    def test_incomplete_four_card_sample(self):
        r, d = fixture(); del r['memory']['before']['free']['xpu:3']
        with self.assertRaises(ValueError): aux.validate_aux_evidence(r, d)
    def test_missing_conditioning_stage(self):
        r, d = fixture(True); r['memory']['conditioning'].pop()
        with self.assertRaises(ValueError): aux.validate_aux_evidence(r, d)
    def test_swapped_conditioning_stages(self):
        r, d = fixture(True); r['memory']['conditioning'].reverse()
        with self.assertRaises(ValueError): aux.validate_aux_evidence(r, d)
    def test_wrong_decode_placement(self):
        r, d = fixture(); d['audio_device'] = 'xpu:3'
        with self.assertRaises(ValueError): aux.validate_aux_evidence(r, d)
    def test_wrong_decode_binding(self):
        r, d = fixture(); d['run_name'] = 'other'
        with self.assertRaises(ValueError): aux.validate_aux_evidence(r, d)
    def test_boolean_free_refused(self):
        r, d = fixture(); r['memory']['after']['free']['xpu:2'] = True
        with self.assertRaises(ValueError): aux.validate_aux_evidence(r, d)
    def test_production_receipt_accepts_evidence(self):
        rows, ds, _ = gate_fixture()
        for row in rows: sr.validate_receipt(row); sr.validate_decode_record(ds[row['run_name']], row)
    def test_production_receipt_rejects_missing_evidence(self):
        rows, _, _ = gate_fixture(); del rows[0]['aux_upsampler_workspace']
        with self.assertRaises(ValueError): sr.validate_receipt(rows[0])
    def test_qualification_rejects_missing_evidence(self):
        rows, ds, captures = gate_fixture(); refs = reference_doc(rows, ds, frames=145, packet=121)
        self.assertTrue(decide(rows, ds, captures, frames=145, decoder_graph=0, references=refs)['passed'])
        del rows[4]['aux_upsampler_workspace']
        verdict = decide(rows, ds, captures, frames=145, decoder_graph=0, references=refs)
        self.assertFalse(verdict['passed']); self.assertTrue(any('Auxiliary evidence:' in why for why in verdict['failures']))
    def test_qualification_rejects_low_actual_margin(self):
        rows, ds, captures = gate_fixture(); refs = reference_doc(rows, ds, frames=145, packet=121)
        rows[6]['memory']['after']['free']['xpu:3'] = int(9.75*aux.GIB)-1
        verdict = decide(rows, ds, captures, frames=145, decoder_graph=0, references=refs)
        self.assertFalse(verdict['passed']); self.assertTrue(any('misses floor plus 0.75' in why for why in verdict['failures']))


if __name__ == '__main__': unittest.main()
