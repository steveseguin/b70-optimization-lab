"""Synthetic byte-only tests; no service, engine, model or device imports."""
import json
import unittest
from stream_parser import ConfirmedTokens, StreamError


def wire(row):
    return (json.dumps(row, separators=(',', ':')) + '\n').encode()


BEGIN = dict(type='begin', schema='sc117.confirmed-tokens.v1', request_sequence=7, limit=3, vocab=100)
TOKEN = dict(type='token', index=1, token_id=42, target_completed_monotonic=12.25)
END = dict(type='end', count=1)
RESULT = dict(tokens=[42], timing_rows=[dict(generated_index=1, token_id=42, completed_monotonic=12.25)])


class Parsing(unittest.TestCase):
    def parser(self):
        return ConfirmedTokens(7, 3, 100)

    def reject(self, data):
        p = self.parser()
        with self.assertRaises(StreamError):
            p.feed(data)
        with self.assertRaises(StreamError):
            p.feed(b'')

    def test_all_bytes_split_at_every_boundary(self):
        data = wire(BEGIN) + wire(TOKEN) + wire(END)
        for split in range(len(data) + 1):
            with self.subTest(split=split):
                p = self.parser()
                rows = p.feed(data[:split]) + p.feed(data[split:])
                self.assertEqual(rows, [TOKEN])
                self.assertEqual(p.finish(RESULT), [42])

    def test_one_byte_reads_and_temporary_eof(self):
        p = self.parser(); rows = []
        for byte in wire(BEGIN) + wire(TOKEN) + wire(END):
            rows += p.feed(bytes([byte]))
            self.assertEqual(p.feed(b''), [])
        self.assertEqual(rows, [TOKEN]); p.finish(RESULT)

    def test_nothing_before_complete_line(self):
        p = self.parser(); p.feed(wire(BEGIN))
        self.assertEqual(p.feed(wire(TOKEN)[:-1]), [])
        self.assertEqual(p.feed(b'\n'), [TOKEN])

    def test_multiple_tokens_cap_and_eos_are_ordinary_ids(self):
        p = self.parser()
        rows = [dict(TOKEN, index=i+1, token_id=t, target_completed_monotonic=12.25+i)
                for i, t in enumerate((0, 42, 99))]
        self.assertEqual(p.feed(wire(BEGIN) + b''.join(map(wire, rows)) + wire(dict(END, count=3))), rows)
        p.finish(dict(tokens=[0,42,99], timing_rows=[dict(generated_index=r['index'], token_id=r['token_id'],
                      completed_monotonic=r['target_completed_monotonic']) for r in rows]))

    def test_identity_and_schema(self):
        for key, value in [('request_sequence',8), ('request_sequence',True), ('limit',4), ('vocab',99), ('schema','v2')]:
            with self.subTest(key=key, value=value): self.reject(wire(dict(BEGIN, **{key:value})))

    def test_invalid_token_ids(self):
        for value in (-1, 100, True, 1.0, '42', None):
            with self.subTest(value=value): self.reject(wire(BEGIN) + wire(dict(TOKEN, token_id=value)))

    def test_missing_duplicate_out_of_order_indices(self):
        for value in (0, 2, True, 1.0):
            with self.subTest(value=value): self.reject(wire(BEGIN) + wire(dict(TOKEN, index=value)))
        self.reject(wire(BEGIN) + wire(TOKEN) * 2)

    def test_over_cap(self):
        self.reject(wire(BEGIN) + b''.join(wire(dict(TOKEN, index=i)) for i in range(1,5)))

    def test_bad_timestamps(self):
        for value in (-1, float('nan'), float('inf'), True, '12'):
            with self.subTest(value=value): self.reject(wire(BEGIN) + wire(dict(TOKEN, target_completed_monotonic=value)))
        self.reject(wire(BEGIN)+wire(TOKEN)+wire(dict(TOKEN,index=2,target_completed_monotonic=12)))

    def test_bad_json_schema_and_duplicates(self):
        for data in (b'{\n', b'\xff\n', b'[]\n', b'null\n', b'\n', b'{"type":"begin","type":"begin"}\n',
                     wire(TOKEN), wire(dict(BEGIN, extra=1)), wire(BEGIN)+wire(BEGIN), wire(BEGIN)+wire(dict(TOKEN,type='guess'))):
            with self.subTest(data=data): self.reject(data)

    def test_line_limit(self):
        self.reject(b'x' * 1025)

    def test_missing_terminal_and_truncated_line(self):
        for data in (b'', wire(BEGIN), wire(BEGIN)+wire(TOKEN), wire(BEGIN)+wire(TOKEN)+wire(END)[:-1]):
            p = self.parser(); p.feed(data)
            with self.assertRaises(StreamError): p.finish(RESULT)

    def test_terminal_counts(self):
        for value in (0,2,True,1.0):
            self.reject(wire(BEGIN)+wire(TOKEN)+wire(dict(END,count=value)))

    def test_records_after_terminal(self):
        for extra in (wire(END),wire(TOKEN),wire(BEGIN),b'\n'):
            self.reject(wire(BEGIN)+wire(TOKEN)+wire(END)+extra)

    def test_final_reconciliation(self):
        for result in ({}, dict(RESULT,tokens=[43]), dict(RESULT,tokens=[42.0]),
                       dict(RESULT,timing_rows=[]), dict(RESULT,timing_rows=[dict(RESULT['timing_rows'][0],completed_monotonic=12.5)])):
            p = self.parser(); p.feed(wire(BEGIN)+wire(TOKEN)+wire(END))
            with self.assertRaises(StreamError): p.finish(result)

    def test_reuse_after_success_rejected(self):
        p = self.parser(); p.feed(wire(BEGIN)+wire(TOKEN)+wire(END)); p.finish(RESULT)
        with self.assertRaises(StreamError): p.feed(b'')
        with self.assertRaises(StreamError): p.finish(RESULT)


if __name__ == '__main__':
    unittest.main()
