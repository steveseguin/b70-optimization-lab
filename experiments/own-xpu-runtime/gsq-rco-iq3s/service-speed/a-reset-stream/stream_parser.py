"""Strict incremental decoder for the proposed native confirmed-token JSONL.

No service imports, process control, device access or tokenizer. Feed bytes from
one fresh request's file; finish only after BOTH native replies and result read.
"""
import json
import math


class StreamError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise StreamError(message)


def _integer(value):
    return type(value) is int


def _object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


class ConfirmedTokens:
    MAX_LINE = 1024

    def __init__(self, request_sequence, limit, vocab):
        _require(all(_integer(x) and x > 0 for x in (request_sequence, limit, vocab)),
                 'invalid expected request identity')
        self.expected = (request_sequence, limit, vocab)
        self.buffer = bytearray()
        self.begun = self.ended = self.failed = self.finished = False
        self.tokens = []
        self.stamps = []

    def _record(self, line):
        _require(not self.ended, 'record after end')
        row = json.loads(line, object_pairs_hook=_object)
        _require(type(row) is dict, 'record must be an object')
        kind = row.get('type')
        if not self.begun:
            _require(set(row) == {'type', 'schema', 'request_sequence', 'limit', 'vocab'},
                     'begin fields')
            identity = tuple(row[k] for k in ('request_sequence', 'limit', 'vocab'))
            _require(kind == 'begin' and row['schema'] == 'sc117.confirmed-tokens.v1'
                     and all(_integer(x) for x in identity) and identity == self.expected,
                     'wrong schema or stale request')
            self.begun = True
            return None
        if kind == 'token':
            _require(set(row) == {'type', 'index', 'token_id', 'target_completed_monotonic'},
                     'token fields')
            index, token, stamp = (row[k] for k in ('index', 'token_id', 'target_completed_monotonic'))
            _require(_integer(index) and index == len(self.tokens) + 1 and index <= self.expected[1],
                     'noncontiguous or over-cap token')
            _require(_integer(token) and 0 <= token < self.expected[2], 'token bounds/type')
            _require(type(stamp) in (int, float) and math.isfinite(stamp) and stamp >= 0
                     and (not self.stamps or stamp >= self.stamps[-1]), 'timestamp')
            self.tokens.append(token)
            self.stamps.append(stamp)
            return row
        _require(kind == 'end' and set(row) == {'type', 'count'}, 'unknown record')
        _require(_integer(row['count']) and row['count'] == len(self.tokens) and row['count'] > 0,
                 'end count')
        self.ended = True
        return None

    def feed(self, data):
        """Return new confirmed token records; retain an incomplete final line.

        A malformed stream permanently poisons this parser. No skipping, retries,
        stale-file fallback or invented tokens. Empty reads mean temporary EOF.
        """
        _require(not self.failed and not self.finished, 'parser is closed/failed')
        records = []
        try:
            _require(isinstance(data, bytes), 'feed requires bytes')
            # Split incrementally so even an oversized read cannot grow the tail unboundedly.
            parts = data.split(b'\n')
            for i, part in enumerate(parts):
                _require(len(self.buffer) + len(part) <= self.MAX_LINE, 'line too long')
                self.buffer.extend(part)
                if i < len(parts) - 1:
                    row = self._record(bytes(self.buffer))
                    self.buffer.clear()
                    if row is not None:
                        records.append(row)
            return records
        except (ValueError, TypeError, OverflowError) as error:
            self.failed = True
            raise StreamError(str(error)) from error

    def finish(self, native_result):
        """Require complete framing and exact equality to the successful result.

        The end record alone is not success. The caller must first validate both
        native command replies, then supply their native-result.json contents.
        """
        _require(not self.failed and not self.finished, 'parser is closed/failed')
        try:
            _require(self.begun and self.ended and not self.buffer, 'missing end or partial line')
            _require(type(native_result) is dict, 'result object')
            tokens = native_result.get('tokens')
            _require(type(tokens) is list and all(_integer(x) for x in tokens)
                     and tokens == self.tokens, 'final token mismatch')
            rows = native_result.get('timing_rows')
            _require(type(rows) is list and len(rows) == len(tokens), 'final timing rows')
            for i, row in enumerate(rows):
                _require(type(row) is dict and _integer(row.get('generated_index'))
                         and row['generated_index'] == i + 1
                         and _integer(row.get('token_id')) and row['token_id'] == tokens[i]
                         and type(row.get('completed_monotonic')) in (int, float)
                         and row['completed_monotonic'] == self.stamps[i], 'final timing mismatch')
            self.finished = True
            return list(self.tokens)
        except (ValueError, TypeError) as error:
            self.failed = True
            raise StreamError(str(error)) from error
