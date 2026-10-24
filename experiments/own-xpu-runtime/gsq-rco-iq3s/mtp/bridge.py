"""Synthetic transport around exact inherited Python controller/state mock.

No weights, owner, subprocess or network is constructed. Proposal tokens are
injected controls, never a simulated claim about neural draft acceptance.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import time
from types import SimpleNamespace

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
PARENT = ROOT / 'experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet'


def load(name, path):
    pins = json.loads((P / 'source-audit.json').read_text())['source_sha256']
    key = str(path.relative_to(ROOT))
    if hashlib.sha256(path.read_bytes()).hexdigest() != pins[key]:
        raise ValueError('inherited source changed: ' + key)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = load('_gsq_mtp_controller', PARENT / 'pipeline.py')
# The frozen test imports the name pipeline; temporarily supply the exact
# admitted module, restoring the ambient namespace even if its import fails.
old = sys.modules.get('pipeline')
try:
    sys.modules['pipeline'] = C
    M = load('_gsq_mtp_state_mock', PARENT / 'test_state_machine.py')
finally:
    if old is None:
        sys.modules.pop('pipeline', None)
    else:
        sys.modules['pipeline'] = old


class SyntheticTransport(M.Mock):
    """Inherited target state transitions plus injected provider publication.

The parent Transport.draft_result validates actual publication bytes. Only the
provider producer and rank arithmetic are synthetic. No real timeout/drain or
DraftRuntime kernel correctness is inferred from these tests.
"""
    draft_result = C.Transport.draft_result

    def __init__(self, confirmed, mode='hit'):
        super().__init__()
        self.confirmed = list(confirmed)
        self.mode = mode
        self.a = SimpleNamespace(draft_rank=1, mini=False, draft_fault=mode)
        self.seq = [0, 0]
        self.started = [0., 0.]
        self.mapping = bytearray(2 * C.SLOT + C.PUBLICATION.size)
        self.provider_inputs = []
        self.draft_cache_inputs = []
        self.disabled = False
        self.rollbacks = 0

    def start(self, rank, op, token=0, position=0, fixture=0, speculative=0):
        super().start(rank, op, token, position, fixture, speculative)
        self.seq[rank] += 1
        self.started[rank] = time.monotonic()

    def wait(self, rank):
        op, token, pos, fixture, spec = self.pending[rank]
        if op != C.DRAFT:
            if op == C.ROLLBACK:
                self.rollbacks += 1
            return super().wait(rank)
        self.pending[rank] = None
        assert rank == 1 and self.candidate[rank] is None
        assert pos == len(self.state[1]['history'])
        assert token == self.confirmed[pos]
        self.provider_inputs.append(dict(confirmed_position=pos, token=token,
                                        hidden_position=pos-1,
                                        hidden=self.state[1]['recurrence'],
                                        draft_position=pos-1))
        if self.mode == 'transport-error':
            raise RuntimeError('synthetic transport error')
        error = int(self.disabled or self.mode in ('pre-error', 'late-error'))
        if not self.disabled:
            if self.mode != 'pre-error':
                self.draft_cache_inputs.append((pos-1, token))
            if error:
                self.disabled = True
        guess = self.confirmed[pos+1] if pos+1 < len(self.confirmed) else 0
        if self.mode == 'miss':
            guess = (guess + 1) % 31
        elif self.mode == 'mixed' and pos % 2:
            guess = (guess + 1) % 31
        elif self.mode == 'garbage':
            guess = 248320
        valid = int(self.mode != 'missing')
        position = pos + 1 - int(self.mode == 'stale-position')
        sequence = self.seq[rank] - int(self.mode == 'stale-sequence')
        self.mapping[2*C.SLOT:] = C.PUBLICATION.pack(valid, position, guess,
                                                   error, 0, sequence, 0, 0.)
        return dict(token=-1)


def reference(prompt, count, eos=()):
    backend = M.Mock()
    result = C.Controller(backend, C.Draft(), False).run(prompt, count, eos)
    return backend, result


def exercise(prompt, count, mode, eos=()):
    base, expected = reference(prompt, count, eos)
    backend = SyntheticTransport(list(prompt) + expected['tokens'], mode)
    result = C.Controller(backend, C.Draft('mtp')).run(prompt, count, eos)
    if (result['tokens'] != expected['tokens'] or backend.state != base.state
            or backend.fixtures != base.fixtures):
        raise AssertionError('target-only token/state/commit equivalence failed')
    if any(x is not None for x in backend.pending + backend.candidate):
        raise AssertionError('unresolved synthetic target command')
    # Deliberately omit inherited timing/acceptance fields: injected proposals
    # are correctness controls, not model measurements.
    return dict(mode=mode, tokens=result['tokens'], state=backend.state,
                provider_inputs=backend.provider_inputs,
                draft_cache_inputs=backend.draft_cache_inputs,
                disabled=backend.disabled, rollbacks=backend.rollbacks,
                stats={k:result['stats'][k] for k in ('guesses','hits','misses','no_guess')})
