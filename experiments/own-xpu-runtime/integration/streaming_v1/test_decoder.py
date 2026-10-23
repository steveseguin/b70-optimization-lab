"""Actual pinned codec and retained token replay; no native/model owner."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import chat_codec as C
from streaming_v1 import decoder as D

class DecoderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec=C.PinnedChatCodec()
        # Single-byte vocabulary pieces force arbitrary UTF-8 split positions.
        cls.byte_ids={};cls.maximum_token_bytes=0
        for token_id in range(cls.codec.vocab):
            raw=D.token_bytes(cls.codec,token_id)
            cls.maximum_token_bytes=max(cls.maximum_token_bytes,len(raw))
            if len(raw)==1:cls.byte_ids.setdefault(raw[0],token_id)
        assert len(cls.byte_ids)==256

    def test_actual_vocabulary_byte_bound(self):
        self.assertEqual(self.maximum_token_bytes,D.MAX_TOKEN_BYTES)

    def check(self,ids):
        decoder=D.TokenDecoder(self.codec,maximum_tokens=max(1,len(ids)))
        target=self.codec.decode(ids[:-1] if ids and ids[-1] in self.codec.terminal_token_ids else ids)
        text=''
        for token in ids:
            text+=decoder.feed(token)
            self.assertTrue(target.startswith(text),'emitted text would need retraction')
        text+=decoder.finish(ids)
        self.assertEqual(text,target);self.assertEqual(decoder.text,target)
        return text

    def test_actual_recorded_p199_output_tokens_and_http_text(self):
        path=C.HERE.parent/'stage2/packet199-chat-parking/evidence/device-p199-chat-A-a/http-requests.json'
        rows=json.loads(path.read_text());self.assertEqual(len(rows),6)
        for row in rows:
            with self.subTest(name=row['name']):
                self.assertEqual(self.check(row['tokens']),row['response']['choices'][0]['message']['content'])

    def test_arbitrary_unicode_and_subword_boundaries(self):
        for text in ['  café 中文 🙂\n\t','e\u0301\nمرحبا','𐀀\u200d👩🏽‍💻','\x00\x01\n\r','a'*31+'🙂'+'b'*19]:
            with self.subTest(text=text):
                self.assertEqual(self.check(self.codec.encode(text)),text)
                self.assertEqual(self.check([self.byte_ids[b] for b in text.encode()]),text)

    def test_incomplete_multibyte_is_held_until_more_bytes_or_final(self):
        decoder=D.TokenDecoder(self.codec);ids=[self.byte_ids[b] for b in '🙂'.encode()]
        self.assertEqual([decoder.feed(t) for t in ids],['','','','🙂'])
        self.assertEqual(decoder.finish(ids),'')
        short=ids[:2];decoder=D.TokenDecoder(self.codec)
        self.assertEqual([decoder.feed(t) for t in short],['',''])
        self.assertEqual(decoder.finish(short),'�')

    def test_malformed_bytes_match_full_replace_decode(self):
        for raw in (b'\x80abc',b'\xc0\xaf',b'\xe2\x28\xa1',b'\xed\xa0\x80',b'\xf0\x9f',bytes(range(256))):
            with self.subTest(raw=raw):self.assertEqual(self.check([self.byte_ids[b] for b in raw]),raw.decode('utf-8',errors='replace'))

    def test_display_suppresses_only_final_terminal_id_and_preserves_history(self):
        for terminal in (248044,248046):
            ids=self.codec.encode(' text \n')+[terminal]
            self.assertEqual(self.check(ids),' text \n')
            decoder=D.TokenDecoder(self.codec);decoder.feed(terminal)
            with self.assertRaisesRegex(D.DecodeRefusal,'after terminal'):decoder.feed(1)
            self.assertEqual(decoder.tokens,[terminal])

    def test_nonterminal_special_token_bytes_are_preserved(self):
        token=next(i for i,t in enumerate(self.codec._tokenizer.tokens)
                   if t in self.codec._tokenizer.special and i not in self.codec.terminal_token_ids)
        self.assertEqual(self.check([token]),self.codec.decode([token]))

    def test_invalid_tokens_caps_completion_mismatch_and_reuse_refuse(self):
        for token in (-1,True,self.codec.vocab,1.0):
            decoder=D.TokenDecoder(self.codec)
            with self.assertRaises(D.DecodeRefusal):decoder.feed(token)
        decoder=D.TokenDecoder(self.codec,maximum_tokens=1);decoder.feed(1)
        with self.assertRaisesRegex(D.DecodeRefusal,'cap'):decoder.feed(2)
        decoder=D.TokenDecoder(self.codec);decoder.feed(1)
        with self.assertRaisesRegex(D.DecodeRefusal,'mismatch'):decoder.finish([2])
        decoder=D.TokenDecoder(self.codec);decoder.feed(1);decoder.finish([1])
        with self.assertRaisesRegex(D.DecodeRefusal,'already finished'):decoder.feed(2)

    def test_pinned_codec_identity_required(self):
        with patch.object(D,'CODEC_SHA','0'*64):
            with self.assertRaisesRegex(D.DecodeRefusal,'source changed'):D.TokenDecoder(self.codec)
        with self.assertRaisesRegex(D.DecodeRefusal,'exact canonical'):D.TokenDecoder(object())

if __name__=='__main__':unittest.main()
