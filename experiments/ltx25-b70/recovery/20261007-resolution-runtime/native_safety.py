"""CPU-importable, explicitly bound safety for serial native reference requests.

No device imports, global activation, allocator changes, retries or eviction.
The trusted runtime supplies synchronized device/residence inspection.
"""
import ast
import copy
from contextlib import contextmanager
import hashlib
import re

SOURCE_SHA256 = '2917a7982d08640ebe297ebc5cb5ad873567099c2e66688dcaff3650464dc694'
ATTRIBUTE = '_ltx_native_reference_safety'
GIB = 2 ** 30
CARDS = ('xpu:0', 'xpu:1', 'xpu:2', 'xpu:3')
PRE_BYTES = dict(zip(CARDS, (6 * GIB, 6 * GIB, 2 * GIB, 7 * GIB)))
ROLES = {
    'sampler_primary': 'xpu:0', 'sampler_secondary': 'xpu:1',
    'upsampler': 'xpu:0', 'text_primary': 'xpu:2',
    'text_secondary': 'xpu:3', 'video_vae': 'xpu:3', 'audio_vae': 'xpu:3',
}


class SafetyRefusal(RuntimeError):
    pass


def digest(value):
    if not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{64}', value) is None:
        raise SafetyRefusal('Expected an explicit lowercase SHA256 identity')
    return value


def transform_sd(raw):
    """Return one exact, source-pinned delta; never write the source tree."""
    if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise SafetyRefusal('Native VAE source is not sealed99b comfy/sd.py')
    old = (b'            except Exception as e:\n'
           b'                model_management.raise_non_oom(e)\n'
           b'                logging.warning("Warning: Ran out of memory when regular VAE decoding, retrying with tiled VAE decoding.")')
    new = old.replace(
        b'                logging.warning(',
        b'                if getattr(self, "_ltx_native_reference_safety", None) is not None:\n'
        b'                    self._ltx_native_reference_safety.reject_oom(self, e)\n'
        b'                logging.warning(', 1)
    if raw.count(old) != 1:
        raise SafetyRefusal('Native decode exception insertion is not unique')
    result = raw.replace(old, new, 1)
    tree = ast.parse(result)
    vae = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'VAE')
    decode = next(n for n in vae.body if isinstance(n, ast.FunctionDef) and n.name == 'decode')
    if sum(isinstance(n, ast.Attribute) and n.attr == 'reject_oom' for n in ast.walk(decode)) != 1:
        raise SafetyRefusal('Refusal did not land exactly once inside VAE.decode')
    return result


class NativeReferenceSafety:
    """One serial native-reference phase, with permanent failure/closed states.

    expected_residence is a trusted mapping role -> ownership_sha256, fixed
    after identity-checked loading. inspect(objects) returns a fresh snapshot:
      plan_sha256/runtime_sha256; phase='native-reference'; fault=False;
      text_graphs_captured=True; window_qualified=True;
      sampler_routes=0; decoder_replicas=0;
      physical_free_bytes={card:int}; residence={role:{object_id,device,dtype,
      fully_resident,ownership_sha256}}; peaks={card:{allocated,reserved,peak}}.
    Peak counters are observational and include preexisting resident memory.
    """
    def __init__(self, *, plan_sha256, runtime_sha256, objects,
                 expected_residence, synchronize, inspect, require_phase):
        self.plan_sha256 = digest(plan_sha256)
        self.runtime_sha256 = digest(runtime_sha256)
        if set(objects) != set(ROLES) or set(expected_residence) != set(ROLES):
            raise SafetyRefusal('Exact reference object/residence roles required')
        if len({id(o) for o in objects.values()}) != len(ROLES):
            raise SafetyRefusal('Reference wrapper/model owners must be distinct')
        if not all(callable(f) for f in (synchronize, inspect, require_phase)):
            raise SafetyRefusal('Explicit phase, synchronization and inspection required')
        self.objects = dict(objects)
        self.expected_residence = {r: digest(v) for r, v in expected_residence.items()}
        self.synchronize = synchronize
        self.inspect = inspect
        self.require_phase = require_phase
        self.failed = None
        self.closed = False
        self.active = None
        self.seen = set()
        self.receipts = []
        # Refuse existing attributes, including None, rather than overwriting
        # another owner's lifecycle. Roll back only our partial construction.
        attached = []
        try:
            for role in ('video_vae', 'audio_vae'):
                obj = self.objects[role]
                if hasattr(obj, ATTRIBUTE):
                    raise SafetyRefusal('Native VAE already has a safety owner')
                setattr(obj, ATTRIBUTE, self)
                attached.append(obj)
        except BaseException:
            for obj in attached:
                delattr(obj, ATTRIBUTE)
            raise

    def _fail(self, reason):
        if self.failed is None:
            self.failed = str(reason)
            self.receipts.append({'event': 'failure', 'request_id': self.active,
                                  'reason': self.failed,
                                  'plan_sha256': self.plan_sha256,
                                  'runtime_sha256': self.runtime_sha256})
        raise SafetyRefusal(self.failed)

    def _available(self):
        if self.failed is not None:
            raise SafetyRefusal(self.failed)
        if self.closed:
            self._fail('Native reference phase is closed')

    @staticmethod
    def _bytes(value):
        # No bools/floats/NaN coercions; device API byte counts are integers.
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0

    def _snapshot(self, event, required):
        # Runtime integration closes over the trusted process-local session,
        # never a phase string selected by the request body.
        self.require_phase()
        for card in CARDS:
            self.synchronize(card)
        snap = self.inspect(dict(self.objects))
        if not isinstance(snap, dict):
            self._fail('Missing native safety snapshot')
        receipt = {'event': event, 'request_id': self.active,
                   'required_physical_free_bytes': dict(required),
                   'snapshot': copy.deepcopy(snap), 'admitted': False,
                   'allowances_are_not_peak_bounds': True}
        self.receipts.append(receipt)
        if (snap.get('plan_sha256') != self.plan_sha256 or
                snap.get('runtime_sha256') != self.runtime_sha256 or
                snap.get('phase') != 'native-reference'):
            self._fail('Native plan/runtime/phase identity changed')
        if (snap.get('fault') is not False or
                snap.get('text_graphs_captured') is not True or
                snap.get('window_qualified') is not True or
                type(snap.get('sampler_routes')) is not int or snap['sampler_routes'] != 0 or
                type(snap.get('decoder_replicas')) is not int or snap['decoder_replicas'] != 0):
            self._fail('Fault or incompatible native reference execution state')
        residence = snap.get('residence')
        if not isinstance(residence, dict) or set(residence) != set(ROLES):
            self._fail('Missing or unexpected resident reference objects')
        for role, device in ROLES.items():
            row = residence[role]
            if not isinstance(row, dict) or row.get('fully_resident') is not True or row != {
                    'object_id': id(self.objects[role]), 'device': device,
                    'dtype': 'torch.bfloat16', 'fully_resident': True,
                    'ownership_sha256': self.expected_residence[role]}:
                self._fail('Native residence/ownership changed: ' + role)
        for role in ('video_vae', 'audio_vae'):
            if getattr(self.objects[role], ATTRIBUTE, None) is not self:
                self._fail('Native VAE safety binding was removed or replaced')
        free, peaks = snap.get('physical_free_bytes'), snap.get('peaks')
        if not isinstance(free, dict) or set(free) != set(CARDS):
            self._fail('Incomplete physical free-memory readings')
        if not isinstance(peaks, dict) or set(peaks) != set(CARDS):
            self._fail('Incomplete allocation/peak readings')
        for card in CARDS:
            if not self._bytes(free[card]) or free[card] < required[card]:
                self._fail('Physical free-memory admission refused: ' + card)
            row = peaks[card]
            if (not isinstance(row, dict) or set(row) != {'allocated', 'reserved', 'peak'} or
                    not all(self._bytes(v) for v in row.values()) or
                    row['reserved'] < row['allocated'] or row['peak'] < row['allocated']):
                self._fail('Invalid allocation/peak readings: ' + card)
        receipt['admitted'] = True
        return receipt

    def before(self, request_id):
        self._available()
        try:
            if self.active is not None:
                self._fail('Overlapping native reference requests are forbidden')
            if not isinstance(request_id, str) or not request_id or request_id in self.seen:
                self._fail('Request identity missing or repeated')
            self.active = request_id
            self.seen.add(request_id)
            return self._snapshot('before', PRE_BYTES)
        except BaseException as exc:
            self._fail('Native admission failed: ' + str(exc))

    def after(self):
        self._available()
        try:
            if self.active is None:
                self._fail('No admitted native request to finish')
            receipt = self._snapshot('after', {c: 2 * GIB for c in CARDS})
            self.active = None
            return receipt
        except BaseException as exc:
            self._fail('Native post-request admission failed: ' + str(exc))

    @contextmanager
    def request(self, request_id):
        self.before(request_id)
        try:
            yield self
        except BaseException as exc:
            self._fail('Native request failed: ' + str(exc))
        else:
            self.after()

    def reject_oom(self, obj, exc):
        # The transformed handler reaches here only after raise_non_oom has
        # confirmed OOM. Always raise, including misuse outside an active request.
        if not any(obj is self.objects[r] for r in ('video_vae', 'audio_vae')):
            self._fail('OOM callback came from an unbound VAE')
        self._fail('Native VAE OOM; tiled fallback forbidden: ' + str(exc))

    def close(self):
        """Close admission once; retain these VAEs' OOM refusal until process exit."""
        self._available()
        if self.active is not None or not self.seen:
            self._fail('Cannot close an active or unused reference phase')
        for role in ('video_vae', 'audio_vae'):
            if getattr(self.objects[role], ATTRIBUTE, None) is not self:
                self._fail('Cannot close a changed VAE safety binding')
        self.closed = True
