"""Serialized policy adapter for an already admitted protocol-v2 owner.

No process launch, signal, restart, HTTP route or checkpoint serialization lives
here. The caller supplies trusted launch identity/root and a conservative SAVE
peak bound; the protocol readiness event cannot attest those launch arguments.
Native RUN still performs full checkpoint validation before device upload.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
from dataclasses import dataclass
from pathlib import Path
import re
import threading
from typing import Any, Callable, Mapping, Sequence

from checkpoint_bridge import IDENTITY_FIELDS, CheckpointView, validate_snapshot


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z", re.ASCII)
_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


class EngineRefusal(RuntimeError):
    """An exceptional adapter operation halts further intake; never retry it."""


def require(condition, message):
    if not condition:
        raise EngineRefusal(message)


def valid_id(value):
    require(type(value) is str and _ID.fullmatch(value) is not None and not value.endswith('.lock'),
            'invalid native identifier')


@dataclass(frozen=True)
class PendingAppend:
    checkpoint_id: str
    manifest_sha256: str
    tokens: tuple[int, ...]


class CheckpointEngine:
    """One exclusive owner, one mutex spanning reply plus policy disposition.

    save_size_bound_bytes is an admitted NEW-checkpoint peak, covering blobs,
    token/control/metadata files and staging. It is not inferred from a previous
    smaller checkpoint. Its native geometry/context proof remains caller-owned.
    storage_available(root) returns current free bytes; floor_bytes is preserved
    before every SAVE. This is additional to Parking's old+new peak reservation.
    """
    def __init__(self, front, store, *, root: Path, expected_identity: Mapping[str, Any],
                 admitted_contract: str, save_size_bound_bytes: int,
                 storage_available: Callable[[Path], int], floor_bytes: int):
        require(admitted_contract == 'v1.2+p198', 'explicit experimental p198 admission required')
        require(type(save_size_bound_bytes) is int and save_size_bound_bytes > 0, 'positive trusted SAVE bound required')
        require(type(floor_bytes) is int and floor_bytes >= 0 and callable(storage_available), 'storage admission required')
        require(all(key in expected_identity for key in IDENTITY_FIELDS), 'complete trusted engine identity required')
        self._identity = copy.deepcopy(dict(expected_identity))
        require(self._identity['label'] == 'experimental-postreply-front' and
                self._identity['contract'] == admitted_contract, 'trusted label/contract mismatch')
        for section, key in (('model', 'identity_tsv_sha256'), ('engine', 'binary_sha256')):
            value = self._identity[section].get(key)
            require(type(value) is str and _SHA.fullmatch(value) is not None, 'trusted model/binary digest required')
        require(self._identity['engine'].get('profile') == 'tp1-full512', 'trusted TP1 profile required')
        self.root = Path(root)
        require(self.root.is_absolute() and '..' not in self.root.parts and self.root == Path(store.root),
                'store differs from admitted checkpoint root')
        require(store.binary_sha256 == self._identity['engine']['binary_sha256'], 'store binary differs from admitted owner')
        self.context, self.vocab = (self._identity['geometry'][key] for key in ('context', 'vocab'))
        require(type(self.context) is int and 1 < self.context <= 1 << 20 and
                type(self.vocab) is int and 1 < self.vocab <= 1 << 31, 'invalid admitted geometry')
        ready = front.ready
        require(ready.get('protocol') == 'ownrt.request-front.v2' and ready.get('experimental') is True,
                'postreply front protocol required')
        require(type(ready.get('model_loads')) is int and ready['model_loads'] == 1 and
                type(ready.get('context')) is int and ready['context'] == self.context and
                type(ready.get('vocab')) is int and ready['vocab'] == self.vocab, 'front geometry/model-load admission mismatch')
        require(front.state == 'ready' and front.pending is None, 'front must be ready with no pending reply')
        self.front, self.store = front, store
        self.admitted_contract = admitted_contract
        self._save_bound, self._storage_available, self._floor = save_size_bound_bytes, storage_available, floor_bytes
        self._lock = threading.RLock()
        self.halted_reason: str | None = None
        self._append: PendingAppend | None = None
        self._visible: tuple[int, ...] | None = None
        self._request_id: str | None = None
        self._operation = 0

    @contextmanager
    def _operation_guard(self):
        with self._lock:
            require(self.halted_reason is None, 'adapter intake halted: ' + str(self.halted_reason))
            try:
                yield
            except BaseException as error:
                if self.halted_reason is None:
                    self.halted_reason = str(error) or type(error).__name__
                raise  # No automatic RELEASE, retry, close, signal or owner restart.

    def _tokens(self, tokens: Sequence[int]) -> tuple[int, ...]:
        require(isinstance(tokens, (tuple, list)) and 0 < len(tokens) <= self.context, 'bounded token vector required')
        require(all(type(token) is int and 0 <= token < self.vocab for token in tokens), 'token outside admitted vocabulary')
        return tuple(tokens)

    def _snapshot(self, checkpoint_id) -> tuple[CheckpointView, int] | None:
        valid_id(checkpoint_id)
        snapshot = self.store.snapshot(checkpoint_id)
        if snapshot is None:
            return None
        arguments = snapshot.bridge_arguments()
        require(arguments.get('checkpoint_id') == checkpoint_id, 'snapshot checkpoint ID mismatch')
        view = validate_snapshot(**arguments, expected_identity=self._identity, admitted_contract=self.admitted_contract)
        size = snapshot.storage_bytes
        require(type(size) is int and size >= len(view.manifest_bytes) + len(snapshot.tokens_bytes) + len(snapshot.next_token_bytes),
                'invalid exact checkpoint storage bytes')
        return view, size

    @staticmethod
    def _metadata(view, size):
        result = view.parking_metadata()
        result['storage_bytes'] = size
        return result

    def identity(self) -> dict[str, str]:
        with self._operation_guard():
            return dict(model=self._identity['model']['identity_tsv_sha256'], engine=self._identity['engine']['binary_sha256'])

    def inspect(self, checkpoint_id):
        with self._operation_guard():
            found = self._snapshot(checkpoint_id)
            return None if found is None else self._metadata(*found)

    def delete(self, checkpoint_id):
        with self._operation_guard():
            valid_id(checkpoint_id)
            require(self._append is None or self._append.checkpoint_id != checkpoint_id, 'cannot delete pending append checkpoint')
            status = self.store.delete(checkpoint_id)
            require(status in ('ok', 'in_use', 'missing'), 'unknown native delete outcome')
            return status

    def save_size_bound(self, checkpoint_id, tokens):
        with self._operation_guard():
            valid_id(checkpoint_id)
            self._tokens(tokens)
            return self._save_bound

    def _next_operation(self):
        self._operation += 1
        operation = 'parking-' + str(self._operation)
        require(operation not in self.front.operations, 'operation namespace collision')
        return operation

    def _pending(self):
        require(self._visible is not None and self.front.state == 'awaiting-disposition' and
                self.front.pending is not None and self.front.pending['request_id'] == self._request_id,
                'adapter has no matching pending reply')

    def save(self, checkpoint_id, tokens):
        with self._operation_guard():
            valid_id(checkpoint_id)
            visible = self._tokens(tokens)
            self._pending()
            require(visible == self._visible, 'SAVE requires exact full visible reply tokens')
            require(self._snapshot(checkpoint_id) is None, 'checkpoint already exists; never overwrite')
            available = self._storage_available(self.root)
            require(type(available) is int and available - self._save_bound >= self._floor,
                    'root headroom cannot preserve floor after SAVE reservation')
            event = self.front.save(self._next_operation(), checkpoint_id, list(visible))
            found = self._snapshot(checkpoint_id)
            require(found is not None, 'acknowledged checkpoint is missing')
            view, size = found
            require(event.get('event') == 'checkpoint-saved' and event.get('request_id') == self._request_id and
                    event.get('checkpoint_id') == checkpoint_id and event.get('manifest_sha256') == view.manifest_sha256,
                    'SAVE acknowledgement/snapshot binding mismatch')
            require(view.saved_history == visible, 'saved full visible history differs from completed reply')
            require(size <= self._save_bound, 'checkpoint exceeded admitted peak bound')
            require(self.front.state in ('ready', 'draining') and self.front.pending is None,
                    'SAVE did not dispose the pending reply')
            self._visible = self._request_id = None
            return self._metadata(view, size)

    def restore(self, checkpoint_id, tokens):
        """Record append-only intent; never decode or accept same-generation resume."""
        with self._operation_guard():
            require(self.front.state == 'ready' and self._visible is None and self._append is None,
                    'owner not ready for a new append plan')
            request = self._tokens(tokens)
            found = self._snapshot(checkpoint_id)
            require(found is not None, 'restore checkpoint missing')
            view, _ = found
            plan = view.plan_append(request, max_new=1)  # Actual cap is validated again by generate.
            self._append = PendingAppend(checkpoint_id, view.manifest_sha256, request)
            return dict(pending=True, checkpoint_id=checkpoint_id, manifest_sha256=view.manifest_sha256,
                        restored=plan.saved_history_tokens, appended=plan.delta_tokens)

    def generate(self, tokens, max_new, *, request_id):
        with self._operation_guard():
            valid_id(request_id)
            request = self._tokens(tokens)
            require(type(max_new) is int and 1 <= max_new <= 512 and len(request)+max_new <= self.context,
                    'generation cap/context admission failed')
            require(self.front.state == 'ready' and self._visible is None, 'pending reply must be disposed before RUN')
            checkpoint = None
            if self._append is not None:
                plan = self._append
                require(plan.tokens == request, 'RUN tokens differ from pending append plan')
                found = self._snapshot(plan.checkpoint_id)
                require(found is not None and found[0].manifest_sha256 == plan.manifest_sha256,
                        'pending append checkpoint changed or disappeared')
                found[0].plan_append(request, max_new=max_new)
                checkpoint = plan.checkpoint_id
            self._append = None  # Consume once, including ambiguous native failure.
            response = self.front.request(request_id, list(request), max_new, restore=checkpoint)
            generated = self._tokens(response['tokens'])
            require(len(generated) <= max_new, 'native response exceeds cap')
            self._visible, self._request_id = request + generated, request_id
            self._pending()
            require(self.front.pending['visible_tokens'] == len(self._visible) and
                    self.front.pending['pending_token'] == generated[-1], 'native pending descriptor differs')
            return response

    def release(self):
        with self._operation_guard():
            self._pending()
            event = self.front.release(self._next_operation())
            require(event.get('event') == 'request-released' and event.get('request_id') == self._request_id and
                    self.front.state in ('ready', 'draining') and self.front.pending is None,
                    'RELEASE did not dispose the pending reply')
            self._visible = self._request_id = None
            return event

    def run_turn(self, parking, session, messages, *, request_id, max_new):
        """Serialize policy lookup, one RUN and postreply policy SAVE/RELEASE."""
        with self._operation_guard():
            require(parking.engine is self, 'parking policy belongs to another engine')
            require(self._append is None, 'unconsumed explicit restore plan before run_turn')
            require(self.front.state == 'ready' and self._visible is None,
                    'previous pending reply must be disposed before policy lookup')
            view = copy.deepcopy(messages)
            decision = parking.before_request(session, view)
            tokens = parking.prefix(view)
            if decision.action == 'restore':
                self.restore(decision.checkpoint_id, tokens)
            else:
                require(decision.action == 'prefill', 'unknown parking decision')
            response = self.generate(tokens, max_new, request_id=request_id)
            parked = parking.park(session, view, response['tokens'])
            disposition = None
            if self._visible is not None:
                # Includes successful same-ID cache hits, which never called save.
                disposition = self.release()
            require(self.front.state in ('ready', 'draining') and self.front.pending is None,
                    'turn finished without disposition')
            return dict(response=response, decision=decision, parked=parked, release=disposition)
