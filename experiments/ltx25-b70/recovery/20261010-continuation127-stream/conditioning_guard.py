"""Packet112 stage guards for the two native conditioning calls (256x256, 49 or 97 frames).

Packet115: begin_request(first_stage='B') admits a request whose only native conditioning
call is stage B (the mixed anchor: stage A is the latent slot-0 copy, stage B the native
image conditioning on the decoded frame). Default 'A' is the packet112-114 behaviour.

Callbacks are trusted integration seams, not self-proving runtime attestations.
No Torch import, tensor arithmetic, submission, allocation reset or retry.
"""
import copy
import hashlib
import inspect
from pathlib import Path
import re
import threading

CONTROLLER_SHA256 = '188f6e1f3e42f06843b369906505bd85c7b501b35438c59de146a519bcc54c0b'
ENCODER_SHA256 = '42010d800e6e49bdc69ae24587910b55b2418e26a1140bec7159a873276c45c2'
CONDITION_NODE_SHA256 = '09ddb30d42244d64ae72e9c64261d1a6b4c512afe0570372222c43dbebd64243'
VAE_SOURCE_SHA256 = 'd1c63b66a6d0cf467ecb084d7ec5fb73d20b0fac43181668124a8ded06aa7604'
GIB = 2 ** 30
PRE = dict(zip(('xpu:0', 'xpu:1', 'xpu:2', 'xpu:3'), (8*GIB, 8*GIB, 2*GIB, 9*GIB)))
POST = {card: 2*GIB for card in PRE}
import stream_contract as _contract
_GEOMETRY = _contract.geometry(_contract.launch_frames())
SHAPES = _GEOMETRY['stage_shapes']
ANCHOR_SHAPE = list(_contract.ANCHOR_SHAPE)
MASK_SHAPE = _GEOMETRY['noise_mask_shape']
CANDIDATE_SHA256 = 'd0d5662bd07155de3464a05e7503d4ba982d056997ec00a0042f5869896fdd3b'


class ConditioningRefusal(RuntimeError):
    pass


def need(ok, reason):
    if not ok:
        raise ConditioningRefusal(reason)


class ConditioningStageGuard:
    """One candidate controller, serial conditioned requests without a count bound.

    begin_request and finish_request run INSIDE the existing native request.
    tensor_metadata(tensor) returns object_id/storage_id/shape/dtype/device/
    contiguous; inspect_anchor(image) returns sha256/finite after fresh checks.
    inspect_encoder_cache(encoder, thread_ident) returns source_sha256,
    encoder_id, thread_ident, entry_count and foreign_entry_count.
    unwrap_output(result) returns the one LATENT dict from native NodeOutput.
    It must inspect without altering the original result, which is returned.
    """
    def __init__(self, *, controller, tensor_metadata, inspect_anchor,
                 inspect_encoder_cache, unwrap_output):
        cls = type(controller)
        path = inspect.getsourcefile(cls)
        base = cls.__mro__[1] if len(cls.__mro__) > 1 else None
        base_path = inspect.getsourcefile(base) if base is not None else None
        need(cls.__name__ == 'CandidateSafety' and path is not None and base is not None and
             base.__name__ == 'NativeReferenceSafety' and base_path is not None and
             hashlib.sha256(Path(path).read_bytes()).hexdigest() == CANDIDATE_SHA256 and
             hashlib.sha256(Path(base_path).read_bytes()).hexdigest() == CONTROLLER_SHA256,
             'Exact packet112 CandidateSafety over sealed NativeReferenceSafety required')
        need(all(callable(f) for f in (tensor_metadata, inspect_anchor,
                                      inspect_encoder_cache, unwrap_output)),
             'Trusted inspection callbacks required')
        self.controller = controller
        self.tensor_metadata = tensor_metadata
        self.inspect_anchor = inspect_anchor
        self.inspect_encoder_cache = inspect_encoder_cache
        self.unwrap_output = unwrap_output
        self.video_vae = controller.objects['video_vae']
        self.encoder = self.video_vae.first_stage_model.encoder
        self.failed = None
        self.active = None
        self.seen = set()
        self.receipts = []
        self.anchor = None
        self.thread_ident = None
        self.next_stage = None
        self.in_call = False

    def _latch(self, exc, stage=None):
        if self.failed is None:
            self.failed = str(exc)[:512]
            self.receipts.append({'event': 'failure', 'request_id': self.active,
                                  'stage': stage if type(stage) is str and stage in SHAPES else None,
                                  'exception': type(exc).__name__,
                                  'reason': self.failed})
            # _fail raises; preserve the triggering exception, including OOM.
            try:
                self.controller._fail('Continuation conditioning: ' + self.failed)
            except BaseException:
                pass

    def _available(self):
        need(self.failed is None, self.failed or 'Conditioning guard failed')
        self.controller._available()

    def _enter_public(self):
        self._available()
        need(not self.in_call, 'Reentrant conditioning guard call')
        # Covers metadata/cache callbacks and synchronized snapshots too.
        # Only the public invocation that acquired this flag may clear it.
        self.in_call = True

    def _identity(self, request_id):
        self._available()
        need(type(request_id) is str and request_id and
             self.active == request_id == self.controller.active,
             'Active native request identity changed')
        need(threading.get_ident() == self.thread_ident, 'Conditioning thread changed')
        need(self.controller.objects['video_vae'] is self.video_vae and
             self.video_vae.first_stage_model.encoder is self.encoder and
             getattr(self.video_vae, '_ltx_native_reference_safety', None) is self.controller,
             'Bound video VAE/encoder/safety owner changed')

    def _tensor(self, obj, shape):
        m = self.tensor_metadata(obj)
        need(type(m) is dict and set(m) == {'object_id', 'storage_id', 'shape',
             'dtype', 'device', 'contiguous'}, 'Incomplete tensor metadata')
        need(type(m['object_id']) is int and m['object_id'] == id(obj) and
             type(m['storage_id']) is int and m['storage_id'] > 0,
             'Tensor ownership metadata invalid')
        need(type(m['shape']) is list and all(type(x) is int for x in m['shape']) and
             m['shape'] == shape and m['dtype'] == 'torch.float32' and
             m['device'] == 'cpu' and m['contiguous'] is True,
             'Unexpected native conditioning tensor geometry/dtype/device/layout')
        return copy.deepcopy(m)

    def _anchor(self):
        meta = self._tensor(self.anchor, ANCHOR_SHAPE)
        need(meta == self.anchor_metadata, 'Anchor object/storage changed')
        checked = self.inspect_anchor(self.anchor)
        need(type(checked) is dict and set(checked) == {'sha256', 'finite'} and
             checked['sha256'] == self.anchor_sha256 and checked['finite'] is True,
             'Anchor bytes/hash/finite binding lost')
        return meta

    def _cache(self):
        row = self.inspect_encoder_cache(self.encoder, self.thread_ident)
        need(type(row) is dict and set(row) == {'source_sha256', 'encoder_id',
             'thread_ident', 'entry_count', 'foreign_entry_count'},
             'Incomplete encoder cache inspection')
        need(row['source_sha256'] == ENCODER_SHA256 and
             type(row['encoder_id']) is int and row['encoder_id'] == id(self.encoder) and
             type(row['thread_ident']) is int and row['thread_ident'] == self.thread_ident and
             type(row['entry_count']) is int and row['entry_count'] == 0 and
             type(row['foreign_entry_count']) is int and row['foreign_entry_count'] == 0,
             'Encoder cache source/owner/thread mismatch or residual cache')
        return copy.deepcopy(row)

    def begin_request(self, request_id, *, anchor, expected_anchor_sha256, first_stage='A'):
        acquired = False
        try:
            self._enter_public()
            acquired = True
            need(self.active is None, 'Conditioned request already active')
            need(type(request_id) is str and re.fullmatch('[a-z0-9][a-z0-9_-]{0,127}', request_id)
                 and request_id not in self.seen and
                 request_id == self.controller.active,
                 'New active conditioned request required')
            need(type(expected_anchor_sha256) is str and
                 re.fullmatch('[0-9a-f]{64}', expected_anchor_sha256), 'Invalid anchor SHA256')
            need(first_stage in ('A', 'B'), 'First conditioning stage is A or B')
            self.active = request_id
            self.seen.add(request_id)
            self.thread_ident = threading.get_ident()
            self.anchor = anchor
            self.anchor_sha256 = expected_anchor_sha256
            self.anchor_metadata = self._tensor(anchor, ANCHOR_SHAPE)
            self.next_stage = first_stage
            self._identity(request_id)
            self._anchor()
            self._cache()
            self._identity(request_id)
            self.receipts.append({'event': 'begin', 'request_id': request_id,
                                  'anchor_sha256': expected_anchor_sha256,
                                  'first_stage': first_stage,
                                  'thread_ident': self.thread_ident,
                                  'plan_sha256': self.controller.plan_sha256,
                                  'runtime_sha256': self.controller.runtime_sha256})
        except BaseException as exc:
            self._latch(exc)
            raise
        finally:
            if acquired:
                self.in_call = False

    def run_stage(self, stage, *, request_id, vae, latent, native_call):
        row = None
        acquired = False
        try:
            self._enter_public()
            acquired = True
            self._identity(request_id)
            need(type(stage) is str and stage == self.next_stage and stage in SHAPES,
                 'Expected stage A then B (or B alone) exactly once')
            need(vae is self.video_vae and callable(native_call), 'Unbound VAE/native call')
            need(type(latent) is dict and 'samples' in latent and 'noise_mask' not in latent,
                 'Expected native unconditioned latent without existing mask')
            self._anchor()
            original = self._tensor(latent['samples'], SHAPES[stage])
            need(original['storage_id'] != self.anchor_metadata['storage_id'],
                 'Latent aliases anchor')
            cache_before = self._cache()
            height, width = SHAPES[stage][-2] * 32, SHAPES[stage][-1] * 32
            row = {'event': 'stage', 'request_id': request_id, 'stage': stage,
                   'anchor_sha256': self.anchor_sha256, 'input': original,
                   'cache_before': cache_before, 'completed': False,
                   'controller_receipt_start': len(self.controller.receipts)}
            row['source_derived_encode_expectation'] = {
                'conditioning_node_sha256': CONDITION_NODE_SHA256,
                'vae_source_before_encode_safety_delta_sha256': VAE_SOURCE_SHA256,
                'expected_input_shape': [1, 3, 1, height, width],
                'workspace_estimate_bytes': 80 * 7 * height * width * 2,
                'estimate_formula': '80 * max(T,7) * H * W * BF16_bytes',
                'internal_pixels_observed': False,
                'measured_peak': False,
                'loader_checks_required_unchanged': True}
            self.receipts.append(row)
            self._identity(request_id)
            row['before'] = copy.deepcopy(self.controller._snapshot('conditioning-' + stage + '-before', PRE))
            self._identity(request_id)
            self._anchor()
            row['cache_after_before_snapshot'] = self._cache()
            self._identity(request_id)
            result = native_call(vae=vae, image=self.anchor, latent=latent,
                                 strength=1.0, bypass=False)
            self._identity(request_id)
            self._anchor()
            need(self._tensor(latent['samples'], SHAPES[stage]) == original,
                 'Input latent ownership changed')
            output = self.unwrap_output(result)
            need(type(output) is dict and set(output) == {'samples', 'noise_mask'},
                 'Native conditioning output fields changed')
            samples = self._tensor(output['samples'], SHAPES[stage])
            mask = self._tensor(output['noise_mask'], MASK_SHAPE)
            need(len({original['storage_id'], self.anchor_metadata['storage_id'],
                      samples['storage_id'], mask['storage_id']}) == 4,
                 'Conditioning output aliases an input or mask')
            row['cache_after'] = self._cache()
            row['after'] = copy.deepcopy(self.controller._snapshot('conditioning-' + stage + '-after', POST))
            self._identity(request_id)
            self._anchor()
            row['cache_after_after_snapshot'] = self._cache()
            self._identity(request_id)
            row.update(output=samples, noise_mask=mask, completed=True)
            row['controller_receipt_end'] = len(self.controller.receipts)
            self.next_stage = 'B' if stage == 'A' else 'done'
            return result
        except BaseException as exc:
            if row is not None:
                row['exception'] = type(exc).__name__
                # CPU-only inspection on failure; never synchronize or retry here.
                try:
                    row['cache_on_failure'] = self._cache()
                except BaseException as cache_exc:
                    row['cache_failure'] = str(cache_exc)[:512]
            self._latch(exc, stage)
            if row is not None:
                row['controller_receipt_end'] = len(self.controller.receipts)
            raise
        finally:
            if acquired:
                self.in_call = False

    def finish_request(self, request_id):
        acquired = False
        try:
            self._enter_public()
            acquired = True
            self._identity(request_id)
            need(self.next_stage == 'done', 'Every admitted conditioning stage must complete')
            self._anchor()
            self._cache()
            self._identity(request_id)
            self.receipts.append({'event': 'finish', 'request_id': request_id})
            self.active = self.anchor = self.thread_ident = self.next_stage = None
        except BaseException as exc:
            self._latch(exc)
            raise
        finally:
            if acquired:
                self.in_call = False
