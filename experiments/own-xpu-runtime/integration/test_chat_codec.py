"""CPU-only pinned GGUF codec checks; no model/native/device execution."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import chat_codec as C


class CodecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec = C.PinnedChatCodec()

    def test_all_twelve_sealed_prompts_and_tokens(self):
        records = C.HERE.parent / 'stage2/packet179-session-swap/one-card/lineage/input-metadata'
        suite = json.loads((C.LAB / 'repro/rapid-model-snapshots-b70/realistic-suite-v1.json').read_text())
        prompts = {p['id']: p['prompt'] for p in suite['prompts']}
        rows = list(records.glob('*/input.json'))
        self.assertEqual(len(rows), 12)
        for path in rows:
            row = json.loads(path.read_text())
            sealed = (C.ORACLE / 'prompts' / Path(row['prompt']).name).read_bytes()
            with self.subTest(prompt=path.parent.name):
                self.assertEqual(hashlib.sha256(sealed).hexdigest(), row['prompt_sha256'])
                rendered = self.codec.render([{'role': 'user', 'content': prompts[path.parent.name]}])
                self.assertEqual(rendered.encode(), sealed)
                self.assertEqual(self.codec.encode(rendered), row['tokens'])
                self.assertEqual(self.codec.decode(row['tokens']), rendered)

    def test_four_retained_message_shapes(self):
        prior = json.loads((C.HERE / 'receipts/template-parity-20261023.json').read_text())
        self.assertEqual(len(prior['shapes']), 4)
        for name, shape in prior['shapes'].items():
            with self.subTest(shape=name):
                actual = self.codec.render(shape['messages'])
                self.assertEqual(actual, shape['rendered'])
                self.assertEqual(hashlib.sha256(actual.encode()).hexdigest(), shape['rendered_sha256'])
                self.assertEqual(self.codec.decode(self.codec.encode(actual)), actual)

    def test_exact_native_identity_and_terminal_roles(self):
        identity = json.loads((C.HERE / 'checkpoint-fixtures-p198/admitted-engine-identity.json').read_text())
        self.assertEqual(dict(self.codec.tokenizer_identity), identity['tokenizer_identity'])
        self.assertEqual(self.codec.vocab, identity['geometry']['vocab'])
        self.assertEqual(self.codec.terminal_token_ids, {248044, 248046})
        self.assertEqual(self.codec.terminal_metadata['gguf_eos_id'], 248046)
        self.assertEqual(self.codec.decode([248044]), '<|endoftext|>')
        self.assertEqual(self.codec.decode([248046]), '<|im_end|>')
        with self.assertRaises(TypeError):
            self.codec.tokenizer_identity['vocab_bin_sha256'] = 'changed'

    def test_unicode_whitespace_and_no_terminal_stripping(self):
        for text in ['  café 中文 🙂\n\t', 'e\u0301\nمرحبا', '\n\n', '', 'end<|im_end|>']:
            with self.subTest(text=text):
                self.assertEqual(self.codec.decode(self.codec.encode(text)), text)
        ids = self.codec.encode(' yes \n') + [248046]
        self.assertEqual(self.codec.decode(ids), ' yes \n<|im_end|>')

    def test_strict_messages(self):
        bad = [[], (), [{}], [{'role': 'tool', 'content': 'x'}],
               [{'role': 'user', 'content': []}], [{'role': 'user', 'content': 'x', 'name': 'z'}],
               [{'role': 'user', 'content': '\ud800'}], [{'role': [], 'content': 'x'}],
               [{'role': 'user', 'content': 'x'}] * 65,
               [{'role': 'user', 'content': 'x' * 65537}]]
        for messages in bad:
            with self.subTest(messages=str(messages)[:60]), self.assertRaises(C.CodecRefusal):
                self.codec.render(messages)
        for value in (None, b'text', '\ud800', 'x' * 65537):
            with self.assertRaises(C.CodecRefusal):
                self.codec.encode(value)

    def test_invalid_decode_ids(self):
        for ids in ([True], [-1], [248320], [1.0], ['1'], iter([1]), [1] * 32769):
            with self.assertRaises(C.CodecRefusal):
                self.codec.decode(ids)

    def test_wrong_header_and_source_pins_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / 'bad.gguf'
            bad.write_bytes(b'GGUF altered')
            with self.assertRaisesRegex(C.CodecRefusal, 'header pin'):
                C.PinnedChatCodec(gguf_path=bad)
            with patch.object(C, 'TOKENIZER', bad):
                with self.assertRaisesRegex(C.CodecRefusal, 'source pin'):
                    C.PinnedChatCodec()
            with patch.object(C, 'IDENTITY', bad):
                with self.assertRaisesRegex(C.CodecRefusal, 'source pin'):
                    C.PinnedChatCodec()
            with patch.object(C, 'VOCAB_SHA', '0' * 64):
                with self.assertRaisesRegex(C.CodecRefusal, 'decoded vocabulary'):
                    C.PinnedChatCodec()


if __name__ == '__main__':
    unittest.main(verbosity=2)
