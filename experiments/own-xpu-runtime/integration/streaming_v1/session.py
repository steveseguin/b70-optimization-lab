"""Additive streaming composition for the unchanged bounded serving profile.

No launch, live admission, process signal or cleanup. The coordinator supplies
the separately sealed streaming source map in addition to the canonical profile.
source_closure() reports current new composition bytes; calling it is not an
independent review or permission to launch. Raw owner/store aliases stay unused
throughout the exclusive loan. Physical drain remains the coordinator's job.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import threading
import time

import bounded_serving_profile as profile_module
import bounded_serving_session as parent
from chat_codec import PinnedChatCodec
from native_checkpoint_store import NativeCheckpointStore
from request_front.client_v2 import NativeFront
from session_lifecycle import finite
from streaming_v1 import engine as E, service as S, lifecycle as L, http as H

HERE = Path(__file__).resolve().parent
ROOT = parent.ROOT
SessionRefusal = parent.SessionRefusal
require = parent.require
PARENT_PINS = (
    (parent, HERE.parent/'bounded_serving_session.py', '61fda8c8a83fb85287b172c50078842025bfcab4906b0ae06b0f34f803431153'),
    (profile_module, HERE.parent/'bounded_serving_profile.py', '8ed8a86c02630a5cfdd9704e5692f2252efe805bf9194b045048b9a625ae34f2'),
)
ROOT_GATE = HERE/'receipts/root-cpu-gate.json'
ROOT_GATE_SHA = '697eaf4d4fa34a316a385c166ba5a729e6ce1627f68b4f5cf940f170e5c1cd0f'
LIFECYCLE_REVIEW = HERE/'receipts/lifecycle-review.json'
LIFECYCLE_REVIEW_SHA = 'b3d240fcc787c7f8f2b73a0230a1275ac23a19656463c919d6d7daf603d18bff'


def _module_origins():
    parent._module_origins()
    for name in ('engine','decoder','service','delivery','http','lifecycle','session'):
        module = sys.modules.get('streaming_v1.' + name)
        require(module is not None and Path(getattr(module, '__file__', '')).resolve() == HERE/(name+'.py'),
                'streaming module origin differs from pinned repository: ' + name)


def source_closure():
    """Verify immutable CPU gates and return the additional source/evidence map.

    The new session/test hashes are explicit inputs for the caller's future seal.
    The reviewed 64-test stack and 27-test lifecycle receipts are hard pinned.
    Nothing in this read-only check upgrades their CPU-only admission status.
    """
    sources = {}
    def add(path, wanted=None):
        relative = path.relative_to(ROOT).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        require(wanted is None or digest == wanted, 'streaming source/review drift: ' + relative)
        require(sources.get(relative, digest) == digest, 'conflicting streaming source seal')
        sources[relative] = digest
    for module, path, digest in PARENT_PINS:
        require(Path(module.__file__).resolve() == path, 'composition module origin changed')
        add(path, digest)
    add(ROOT_GATE, ROOT_GATE_SHA)
    add(LIFECYCLE_REVIEW, LIFECYCLE_REVIEW_SHA)
    gate = json.loads(ROOT_GATE.read_text())
    review = json.loads(LIFECYCLE_REVIEW.read_text())
    require(gate['passed'] is True and gate['tests'] == 64 and
            gate['native_executed'] is False and gate['device_executed'] is False and
            gate['production_lifecycle_admitted'] is False, 'root CPU gate scope changed')
    require(review['passed'] is True and review['tests'] == 27 and
            review['native_execution'] is False and review['device_execution'] is False,
            'lifecycle CPU review scope changed')
    for mapping in (gate['source_sha256'], gate['independent_review_sha256'], review['source_sha256']):
        for relative, digest in mapping.items():
            path = Path(relative)
            require(not path.is_absolute() and '..' not in path.parts, 'non-repository source seal path')
            add(ROOT/path, digest)
    for row in (gate['log'], review['log'], review['author_receipt']):
        add(ROOT/row['path'], row['sha256'])
    for path in (HERE/'session.py', HERE/'test_session.py'):
        add(path)
    return sources


class StreamingServingSession(parent.BoundedServingSession):
    """Attach one existing owner, then use open_listener/serve/request_close.

    Parent session state/receipt locking and single-use behavior are unchanged.
    The only listener is the streaming successor; the old exact gate stays intact.
    """
    def open_listener(self, address=('127.0.0.1', 0)):
        require(self._server is None and self.lifecycle.state == 'attached', 'listener is single use')
        self._server = H.make_server(self.lifecycle.service, address)
        return self._server.server_address

    def _receipt(self):
        result = super()._receipt()
        result['schema'] = 'ownrt.streaming-serving-session.v1'
        result['streaming_source_sha256'] = dict(self._streaming_sources)
        result['streaming_closure_sha256'] = self._streaming_sha256
        result['peer_receipt_proven'] = False
        return result


def _compose(*, profile, front, store, codec, guard, launched_at,
             last_native_activity, clock, storage_available, scope, streaming_sources=None):
    """Synthetic component seam; use attach for validated production composition."""
    limits = profile['limits']
    admission = L.RunAdmission(front, guard=guard, request_limit=limits['requests'],
        idle_seconds=limits['idle_seconds'], absolute_deadline=launched_at+limits['absolute_seconds'],
        last_native_activity=last_native_activity, native_idle_seconds=limits['native_idle_seconds'],
        native_absolute_deadline=launched_at+limits['native_seconds'], clock=clock)
    guarded_store = parent._GuardedStore(store, admission)
    engine = E.StreamingCheckpointEngine(admission.front, guarded_store,
        root=Path(profile['paths']['checkpoint_root']), expected_identity=profile['identity'],
        admitted_contract='v1.2+p198', save_size_bound_bytes=limits['save_bound_bytes'],
        storage_available=storage_available, floor_bytes=limits['disk_floor_bytes'])
    parking = parent._parking_class()(engine, codec.render, codec.encode,
        budget_bytes=limits['parking_bytes'], accepted_contracts={('experimental-postreply-front','v1.2+p198')})
    service = S.StreamingChatService(engine, parking, codec, model=profile['model'],
        native_stop_token_ids=set(profile['native_stop_token_ids']))
    lifecycle = L.StreamingSessionLifecycle(service, admission)
    result = object.__new__(StreamingServingSession)
    result.admission, result.engine, result.parking, result.lifecycle = admission, engine, parking, lifecycle
    result._server = result._terminal = result._failure = None
    result._state_lock, result._running = threading.RLock(), False
    result._scope = scope
    result._profile_sha256 = hashlib.sha256(json.dumps(profile, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    result._streaming_sources = dict(source_closure() if streaming_sources is None else streaming_sources)
    result._streaming_sha256 = hashlib.sha256(json.dumps(result._streaming_sources, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()
    return result


def attach(profile, *, streaming_sources, front, store, admitted_argv, launched_at,
           last_native_activity, guard):
    """Same canonical owner checks, with a separate reviewed streaming closure.

    Caller supplies conservative coordinator launch/activity clocks and the
    externally sealed source map, never values inferred from readiness. Neither
    the profile nor the streaming CPU gates constitute live launch admission.
    """
    _module_origins()
    require(type(streaming_sources) is dict and streaming_sources == source_closure(),
            'streaming source closure differs from caller seal')
    profile_module.validate_profile(profile, check_fresh=False)
    require(type(front) is NativeFront and type(store) is NativeCheckpointStore,
            'exact admitted native front and store required')
    now = time.monotonic()
    require(all(finite(x) for x in (launched_at, last_native_activity)) and
            launched_at <= last_native_activity <= now and
            now < launched_at+profile['limits']['absolute_seconds'] and
            now < last_native_activity+profile['limits']['idle_seconds'],
            'conservative unexpired native launch/activity timestamps required')
    require(callable(guard), 'coordinator fault/admission guard required')
    require(type(admitted_argv) is list and admitted_argv == profile['native_argv'] and
            front.process.args == admitted_argv, 'owner argv differs from admitted profile')
    require(front.max_requests == profile['limits']['requests'] and
            front.completed == front.completed_controls == 0 and not front.operations and
            front.process.poll() is None, 'fresh live owner required')
    require(front.ready.get('max_requests') == front.max_requests and
            front.ready.get('max_control_ops') == front.max_requests, 'ready native limits mismatch')
    root = Path(profile['paths']['checkpoint_root'])
    require(store.root == root and str(store.binary) == profile['binary']['path'] and
            store.binary_sha256 == profile['binary']['sha256'], 'store root/binary differs from admitted owner')
    store._check_binary()
    info = root.stat(follow_symlinks=False)
    held = os.fstat(store._root_fd)
    require((held.st_dev, held.st_ino) == (info.st_dev, info.st_ino),
            'held checkpoint directory differs from admitted root')
    require(root.resolve(strict=True) == root and stat.S_ISDIR(info.st_mode) and
            stat.S_IMODE(info.st_mode) == 0o700 and info.st_uid == os.getuid() and
            not any(root.iterdir()), 'fresh empty private checkpoint directory required')
    guard()
    codec = PinnedChatCodec()
    require(codec.tokenizer_identity == profile['identity']['tokenizer_identity'] and
            codec.vocab == profile['limits']['vocab'] and
            codec.terminal_token_ids == set(profile['native_stop_token_ids']), 'codec identity differs from admitted profile')
    guard()
    return _compose(profile=copy.deepcopy(profile), streaming_sources=dict(streaming_sources),
        front=front, store=store, codec=codec, guard=guard, launched_at=launched_at,
        last_native_activity=last_native_activity, clock=time.monotonic,
        storage_available=lambda path:shutil.disk_usage(path).free,
        scope='experimental streaming production composition; caller owns live admission and physical drain')
