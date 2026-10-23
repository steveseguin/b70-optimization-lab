"""Pure source/dependency checks, not a C++ compile or native execution gate."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

P = Path(__file__).resolve().parents[1]; ROOT = P.parents[3]
sys.path.insert(0, str(P))
import prepare_overlay as O
import build_engine as B


def section(text, first, last):
    start = text.index(first)
    return text[start:text.index(last, start)]


class OverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (O.NATIVE / 'main.cpp').read_text()
        cls.header = (O.NATIVE / 'checkpoint.hpp').read_text()
        cls.main, cls.checkpoint = O.transform(cls.original, cls.header)

    def test_exact_reset_step_save_restore_bodies(self):
        for first, last in [('static void p58_reset_request(', '\n#ifdef OWN_RT_HOST_ONLY'),
                            ('    auto step = [&]', '    int next=-1;')]:
            self.assertEqual(section(self.main, first, last), section(self.original, first, last))
        for first, last in [('static SavedCheckpoint checkpoint_save(', 'struct RestoredCheckpoint'),
                            ('static RestoredCheckpoint checkpoint_restore(', '// packet181: "prefill"'),
                            ('static int checkpoint_inspect_tool(', 'static int checkpoint_host_tool(')]:
            self.assertEqual(section(self.checkpoint, first, last), section(self.header, first, last))

    def test_retained_descriptor_precedes_scope_exit_and_reset(self):
        self.assertLess(self.main.index('struct FrontPending'), self.main.index('for(size_t request_number='))
        controls = section(self.main, '      if(request->kind!=', '      a=front_base;')
        self.assertIn('front_pending.processed.begin()', controls)
        self.assertIn('request->tokens.back()==front_pending.next_token', controls)
        self.assertIn('front_pending.prompt,front_pending.processed,front_pending.next_token', controls)
        self.assertLess(controls.index('pipeline::checkpoint_save('), controls.index('front->reader.complete_control('))
        self.assertIn('continue;', controls)
        self.assertIn('front_pending.processed=restored.tokens;front_pending.processed.push_back(restored.next_token)', self.main)
        self.assertIn('generated.begin(),generated.end()-1', O.DESCRIPTOR)
        self.assertIn('front_pending.parent.manifest_sha256=restored.manifest_sha256', O.DESCRIPTOR)
        self.assertLess(self.main.index(O.DESCRIPTOR), self.main.index('\\"event\\":\\"request-complete'))

    def test_postreply_restore_reserves_free_checkpoint_position(self):
        self.assertEqual(self.main.count('a.request_front||!a.checkpoint_save.empty()'), 2)
        self.assertIn('input,a.tokenizer_identity,a.tokens,front||!a.checkpoint_save.empty()', self.main)

    def test_explicit_new_identity_and_v2_wire(self):
        self.assertIn('experimental-postreply-front', self.checkpoint)
        self.assertIn('"v1.2+p198"', self.checkpoint)
        self.assertNotIn('"v1.2+p197"', self.checkpoint)
        self.assertIn('experimental-postreply-owner-v2', self.main)
        for value in ('ownrt.request-front.v2', 'max_control_ops', 'pending_request_id', 'completed_controls',
                      'discarded_pending', 'checkpoint-saved', 'request-released', 'startup-checkpoint-root'):
            self.assertIn(value, self.main)
        self.assertIn(r'\"device_gates\":[]', self.checkpoint)

    def test_parser_final_request_waits_for_disposition(self):
        header = (P / 'native/request_front.hpp').read_text()
        self.assertIn('count_==maximum_&&pending_.empty()', header)
        self.assertIn('pending_.empty(),"pending request needs SAVE or RELEASE"', header)
        self.assertIn('operation_ids_.insert(r.id).second', header)
        self.assertIn('controls_<maximum_', header)
        self.assertIn('check(f[4]=="-","v2 RUN saves only after reply")', header)
        self.assertIn('frame_limit=262144', header)
        self.assertIn('now>=deadline', header)

    def test_parent_and_generated_overlay_pins(self):
        pins = json.loads((P / 'parent-pins.json').read_text())
        for name, digest in pins['sources'].items():
            self.assertEqual(O.sha(ROOT / name), digest, name)
        self.assertEqual((P / 'build/native/main.cpp').read_text(), self.main)
        self.assertEqual((P / 'build/native/checkpoint.hpp').read_text(), self.checkpoint)

    def test_checked_inherited_build_recipe_stays_in_new_packet(self):
        pins = json.loads((P / 'parent-pins.json').read_text())
        for target in ('host', 'device', 'protocol'):
            recipe = B.plan(target)
            self.assertTrue(Path(recipe['binary']).is_relative_to(P / 'build'))
            for command in recipe['commands']:
                self.assertTrue(Path(command[command.index('-o') + 1]).is_relative_to(P / 'build'))
            expected = B.expected_dependencies(target, pins)
            with tempfile.TemporaryDirectory(prefix='p198-dependencies-') as temporary:
                dep = Path(temporary) / 'entry.d'
                def write(paths): dep.write_text('entry.o: ' + ' '.join(str(p) for p in sorted(paths)) + '\n')
                write(expected)
                self.assertEqual(set(B.verify_dependencies(target, dep, pins)), {str(p.relative_to(ROOT)) for p in expected})
                write(expected - {next(iter(expected))})
                with self.assertRaises(AssertionError): B.verify_dependencies(target, dep, pins)
        self.assertEqual(len(B.plan('device')['objects']), 41)
        self.assertEqual(len(B.plan('host')['objects']), 33)


if __name__ == '__main__': unittest.main()
