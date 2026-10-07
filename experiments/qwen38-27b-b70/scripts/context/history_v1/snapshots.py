"""Immutable, fresh-only snapshots of actual accepted states. No task/oracle access."""
import copy
import hashlib
import json
import os
from pathlib import Path

MAX_COUNTERS = 256
MAX_COUNTER_BYTES = 128
MAX_SELECTION_BYTES = 4096


class SnapshotStorageError(RuntimeError):
    """A persistence/integrity fault, never a recoverable model refusal."""


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def selection(batch_id, counters=None):
    if type(batch_id) is not int or batch_id <= 0:
        raise ValueError('state_at needs one positive integer batch_id')
    if counters is None:
        return None
    if (not isinstance(counters, list) or not 1 <= len(counters) <= MAX_COUNTERS
            or any(not isinstance(name, str) or not name or len(name.encode()) > MAX_COUNTER_BYTES
                   for name in counters)):
        raise ValueError('counters must be 1..256 nonempty names of at most 128 UTF-8 bytes')
    if len(set(counters)) != len(counters) or len(encoded(counters)) > MAX_SELECTION_BYTES:
        raise ValueError('counter selection must be unique and at most 4096 UTF-8 bytes')
    return sorted(counters)


class SnapshotStore:
    """One trusted writer, immutable files, live in-memory hash anchors; no resume.

    The API deliberately accepts neither a task, oracle, diagnostic metrics nor
    a grader result. Hashes identify evidence, not mathematical correctness.
    """
    def __init__(self, directory, arm):
        if arm not in ('archive', 'quoted'):
            raise ValueError('historical states support archive and quoted only')
        self.directory = Path(directory)
        self.arm = arm
        self._anchors = {}
        try:
            self.directory.mkdir(exist_ok=False)
        except OSError as error:
            raise SnapshotStorageError('snapshot directory must be new') from error

    def save(self, batch_id, state, source_text, raw_response):
        """Call exactly once after admission, before publishing batch completion."""
        # Bad internal inputs are infrastructure errors, not model retry signals.
        if (type(batch_id) is not int or batch_id != len(self._anchors)+1
                or not isinstance(state, dict)
                or any(not isinstance(k, str) or type(v) is not int for k,v in state.items())
                or not isinstance(source_text, str) or not isinstance(raw_response, str)):
            raise SnapshotStorageError('invalid or repeated accepted-state snapshot')
        try:
            safe_state = copy.deepcopy(state)
            receipt = {'schema':'history-state-receipt.v1', 'batch_id':batch_id, 'arm':self.arm,
                       'source_text_sha256':digest(source_text.encode()),
                       'raw_response_sha256':digest(raw_response.encode()),
                       'state_sha256':digest(encoded(safe_state)),
                       'previous_snapshot_sha256':self._anchors.get(batch_id-1)}
            record = {'schema':'history-state-snapshot.v1', 'state':safe_state, 'receipt':receipt}
            raw = encoded(record)
        except (ValueError, TypeError) as error:
            raise SnapshotStorageError('accepted-state snapshot serialization failed') from error
        path = self.directory / f'batch-{batch_id}.json'
        try:
            with path.open('xb') as handle:
                handle.write(raw); handle.flush(); os.fsync(handle.fileno())
            # Persist the directory entry too before marking acceptance.
            fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(fd)
            finally: os.close(fd)
        except OSError as error:
            raise SnapshotStorageError('failed to persist accepted-state snapshot') from error
        self._anchors[batch_id] = digest(raw)
        return {**receipt, 'snapshot_sha256':self._anchors[batch_id]}

    def state_at(self, batch_id, counters=None):
        selected = selection(batch_id, counters)
        if batch_id not in self._anchors:
            return {'error':f'No accepted state snapshot for batch {batch_id}'}
        try:
            raw = (self.directory / f'batch-{batch_id}.json').read_bytes()
            if digest(raw) != self._anchors[batch_id]:
                raise SnapshotStorageError('snapshot integrity mismatch')
            record = json.loads(raw); state = record['state']; receipt = record['receipt']
            if (receipt['batch_id'] != batch_id or receipt['arm'] != self.arm
                    or receipt['state_sha256'] != digest(encoded(state))
                    or receipt['previous_snapshot_sha256'] != self._anchors.get(batch_id-1)):
                raise SnapshotStorageError('snapshot receipt mismatch')
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise SnapshotStorageError('snapshot read or receipt failure') from error
        names = sorted(state) if selected is None else selected
        return {'action':'state_at', 'batch_id':batch_id,
                'state':{name:state[name] for name in names if name in state},
                'missing_counters':[name for name in names if name not in state],
                'receipt':{**receipt, 'snapshot_sha256':self._anchors[batch_id]},
                'scope':'Actual accepted state at the end of this batch; may contain model errors.'}

    def validate_all(self):
        """Final evidence validation also covers snapshots never queried by the model."""
        expected = {f'batch-{batch_id}.json' for batch_id in self._anchors}
        try:
            actual = {path.name for path in self.directory.iterdir()}
        except OSError as error:
            raise SnapshotStorageError('snapshot final inventory unreadable') from error
        if actual != expected:
            raise SnapshotStorageError('snapshot final inventory differs from accepted snapshots')
        for batch_id in sorted(self._anchors):
            self.state_at(batch_id)
