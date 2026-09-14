"""Inactive single-request continuation coordinator; no HTTP or GPU operations.

This owns graph/capture lineage and sink acknowledgements, not playback or model
qualification. A future transport must persist reservations before external
effects and supply authenticated endpoint identity/history. Uncertain effects
halt; there is no automatic retry or resume of an interrupted request.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile

from continuation_delivery import verify_capture, iter_delivery_frames

SCRIPTS = Path(__file__).resolve().parent
BINDER_SHA256 = '30ea22b753cd33110ebd533f4487a71175dca14bc1e6bf2f36d32ca0c986e47a'
MAX_CHECKPOINT_BYTES = 512 * 1024
MAX_RETAINED = 3
FAULT_ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def is_hash(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def graph_builder():
    path = SCRIPTS / 'bind-continuation-anchor.py'
    require(hashlib.sha256(path.read_bytes()).hexdigest() == BINDER_SHA256, 'graph binder changed')
    spec = importlib.util.spec_from_file_location('stream_bound_graph', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_bound_chunk


class ContinuationStream:
    def __init__(self, stream_id, runtime_identity_sha256, model_verification_sha256):
        require(isinstance(stream_id, str) and re.fullmatch(r'[a-z0-9_-]{1,48}', stream_id),
                'stream id must be a bounded lowercase identifier')
        require(is_hash(runtime_identity_sha256) and is_hash(model_verification_sha256),
                'runtime and model verification hashes are required')
        identity = {'stream_id': stream_id, 'runtime_identity_sha256': runtime_identity_sha256,
                    'model_verification_sha256': model_verification_sha256,
                    'binder_sha256': BINDER_SHA256, 'fps': 24, 'shape': [25, 256, 256, 3],
                    'stage_steps': [8, 3], 'precision': 'native BF16'}
        self._state = {'schema': 'ltx25.continuation-stream-state.v1', 'identity': identity,
                       'phase': 'idle', 'next_chunk': 0, 'pending': None, 'retained': [],
                       'acknowledged_frames': 0, 'chain_sha256': digest(identity),
                       'last_retirement': None, 'fault': None,
                       'runtime_qualified': False, 'playback_verified': False}

    def snapshot(self):
        return copy.deepcopy(self._state)

    def _phase(self, required):
        require(self._state['phase'] == required, f'expected {required}; state is {self._state["phase"]}')

    def halt(self, reason):
        previous = self._state['phase']
        if previous != 'halted':
            self._state['fault'] = {'previous_phase': previous, 'reason': str(reason)[:2048],
                                    'automatic_retry': False}
            self._state['phase'] = 'halted'

    def _healthy(self):
        if self._state['phase'] == 'halted':
            raise RuntimeError('Stream is halted; no automatic retry or resume')
        if (FAULT_ROOT / 'FAULT.json').exists():
            self.halt('host fault latch is present')
            raise RuntimeError('Host fault recorded; halt stream actions')

    def reserve(self, prompt, seed):
        """Reserve one graph; this deliberately does not submit it."""
        self._phase('idle')
        self._healthy()
        require(isinstance(prompt, str) and prompt.strip() and len(canonical(prompt)) <= 65536,
                'prompt must be nonempty and at most 65536 JSON-encoded bytes; never truncated')
        require(type(seed) is int and 0 <= seed < 2**64, 'seed must be uint64')
        require(len(self._state['retained']) < MAX_RETAINED,
                'retention limit reached; retire verified old footage before another request')
        index = self._state['next_chunk']
        require(index == 0 or self._state['retained'], 'predecessor capture is missing')
        predecessor = self._state['retained'][-1] if index else None
        run = f'continuation-{self._state["identity"]["stream_id"]}-{index:08d}'
        envelope = graph_builder()(index, run, seed=seed, prompt=prompt,
                        predecessor_run=predecessor['run_name'] if predecessor else None,
                        anchor_sha256=predecessor['anchor_sha256'] if predecessor else None)
        self._state['pending'] = {'index': index, 'run_name': run, 'prompt': prompt, 'seed': seed,
                                 'graph_sha256': digest(envelope['graph']),
                                 'predecessor': None if predecessor is None else {
                                     'run_name': predecessor['run_name'],
                                     'anchor_sha256': predecessor['anchor_sha256'],
                                     'chunk_sha256': predecessor['chunk_sha256']},
                                 'prompt_id': None, 'verification': None,
                                 'acknowledged': 0, 'outstanding': None}
        self._state['phase'] = 'reserved'
        envelope['stream_reservation'] = {'identity': copy.deepcopy(self._state['identity']),
                                         'graph_sha256': self._state['pending']['graph_sha256'],
                                         'chain_sha256': self._state['chain_sha256'],
                                         'transport_implemented': False}
        return envelope

    def submitted(self, prompt_id):
        self._phase('reserved')
        self._healthy()
        require(isinstance(prompt_id, str) and re.fullmatch(r'[a-zA-Z0-9_-]{1,128}', prompt_id),
                'invalid server prompt id')
        self._state['pending']['prompt_id'] = prompt_id
        self._state['phase'] = 'submitted'

    def completed(self, history_entry, output_root, runtime_identity_sha256):
        """Bind successful endpoint history to this graph, then verify raw capture.

        History and runtime identity must come from the future owning transport;
        these arguments alone are not proof of an actual GPU execution.
        """
        self._phase('submitted')
        try:
            self._healthy()
            pending = self._state['pending']
            require(runtime_identity_sha256 == self._state['identity']['runtime_identity_sha256'],
                    'runtime identity changed')
            status = history_entry['status']
            require(status['status_str'] == 'success' and status['completed'] is True,
                    'generation did not complete successfully')
            prompt = history_entry['prompt']
            require(prompt[1] == pending['prompt_id'], 'history belongs to another prompt')
            require(digest(prompt[2]) == pending['graph_sha256'], 'history graph differs from reservation')
            folder = Path(output_root).resolve() / 'validation' / pending['run_name']
            require(folder.resolve() == folder and (folder / 'tensors.safetensors').resolve() ==
                    folder / 'tensors.safetensors', 'capture resolves through a symlink')
            verification = verify_capture(folder / 'tensors.safetensors', folder / 'summary.json')
            require(verification['run_name'] == pending['run_name'], 'capture belongs to another run')
            pending['verification'] = verification
            pending['history_sha256'] = digest(history_entry)
            pending['capture_path'] = str(folder / 'tensors.safetensors')
            self._state['phase'] = 'ready'
        except BaseException as error:
            self.halt(error)
            raise

    def frames(self):
        """Offer one frame at a time; caller must acknowledge before advancing.

        An acknowledgement reports sink acceptance, not measured playback. Early
        close, read failure or missing ack halts and preserves ambiguous state.
        """
        self._phase('ready')
        self._healthy()
        self._state['phase'] = 'delivering'
        pending = self._state['pending']
        frames = iter_delivery_frames(pending['capture_path'], pending['verification'], pending['index'])
        try:
            start = 0 if pending['index'] == 0 else 1
            for frame_index, payload in enumerate(frames, start):
                self._healthy()
                require(type(payload) is bytes and len(payload) == 786432,
                        'delivery must provide one exact 256x256 RGB F32 frame')
                require(pending['outstanding'] is None, 'previous frame acknowledgement missing')
                token = digest({'stream': self._state['identity']['stream_id'],
                                'chunk': pending['index'], 'frame': frame_index,
                                'sha256': hashlib.sha256(payload).hexdigest()})
                pending['outstanding'] = token
                yield {'frame_index': frame_index, 'token': token, 'payload': payload}
                self._phase('delivering')
                require(pending['outstanding'] is None, 'frame acknowledgement missing')
            require(pending['acknowledged'] == (25 if pending['index'] == 0 else 24),
                    'wrong acknowledged frame count')
            self._state['phase'] = 'awaiting_finish'
        except BaseException as error:
            self.halt(f'delivery interrupted: {type(error).__name__}: {error}')
            raise
        finally:
            frames.close()

    def acknowledge(self, token):
        self._phase('delivering')
        pending = self._state['pending']
        if pending['outstanding'] is None or token != pending['outstanding']:
            self.halt('unexpected or duplicate frame acknowledgement')
            raise ValueError('unexpected or duplicate frame acknowledgement')
        pending['outstanding'] = None
        pending['acknowledged'] += 1
        self._state['acknowledged_frames'] += 1

    def finish(self):
        self._phase('awaiting_finish')
        self._healthy()
        pending = self._state['pending']
        verification = pending['verification']
        record = {key: pending[key] for key in ('index', 'run_name', 'prompt', 'seed', 'graph_sha256',
                                               'predecessor', 'prompt_id', 'history_sha256')}
        record.update({'anchor_sha256': verification['anchor_sha256'],
                       'tensor_sha256': {name: value['sha256'] for name, value in verification['tensors'].items()},
                       'capture_path': pending['capture_path'],
                       'summary_file_sha256': verification['summary_file_sha256'],
                       'acknowledged_frames': pending['acknowledged'],
                       'previous_chain_sha256': self._state['chain_sha256']})
        record['chunk_sha256'] = digest(record)
        self._state['chain_sha256'] = record['chunk_sha256']
        self._state['retained'].append(record)
        self._state['next_chunk'] += 1
        self._state['pending'] = None
        self._state['phase'] = 'idle'
        return copy.deepcopy(record)

    def confirm_retired(self, run_name, deletion_receipt_sha256):
        """Release oldest metadata only after external verified retention cleanup.

        This never deletes footage. The future cleanup owner must preserve the
        required review/replay evidence and remove previews as well as captures.
        """
        self._phase('idle')
        retained = self._state['retained']
        require(len(retained) >= 2 and retained[0]['run_name'] == run_name,
                'only oldest non-predecessor capture can be retired')
        require(is_hash(deletion_receipt_sha256), 'deletion receipt hash required')
        require(not Path(retained[0]['capture_path']).parent.exists(),
                'capture directory still exists; retirement is unconfirmed')
        old = retained.pop(0)
        self._state['last_retirement'] = {'run_name': run_name, 'chunk_sha256': old['chunk_sha256'],
                                         'index': old['index'],
                                         'anchor_sha256': old['anchor_sha256'],
                                         'deletion_receipt_sha256': deletion_receipt_sha256}

    def checkpoint_bytes(self):
        state = self.snapshot()
        data = canonical({'state': state, 'state_sha256': digest(state)})
        require(len(data) <= MAX_CHECKPOINT_BYTES, 'checkpoint exceeds bounded metadata budget')
        return data

    def save_checkpoint(self, path):
        """Atomic bounded metadata checkpoint; no media write or network effect."""
        data = self.checkpoint_bytes()
        path = Path(path)
        fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @classmethod
    def restore(cls, data, runtime_identity_sha256, model_verification_sha256):
        require(type(data) is bytes and len(data) <= MAX_CHECKPOINT_BYTES, 'invalid checkpoint size/type')
        value = json.loads(data)
        state = value['state']
        require(digest(state) == value['state_sha256'], 'checkpoint checksum mismatch')
        identity = state['identity']
        result = cls(identity['stream_id'], runtime_identity_sha256, model_verification_sha256)
        require(identity == result._state['identity'], 'checkpoint runtime/model/policy changed')
        require(set(state) == set(result._state), 'checkpoint schema changed')
        require(state['schema'] == result._state['schema'], 'checkpoint schema version changed')
        require(type(state['next_chunk']) is int and state['next_chunk'] >= 0, 'invalid chunk counter')
        require(isinstance(state['retained'], list) and len(state['retained']) <= MAX_RETAINED,
                'invalid retained count')
        require(state['phase'] in ('idle', 'reserved', 'submitted', 'ready', 'delivering', 'awaiting_finish', 'halted'),
                'invalid checkpoint phase')
        require(state['phase'] != 'idle' or state['pending'] is None, 'idle checkpoint has a pending request')
        require(state['runtime_qualified'] is False and state['playback_verified'] is False,
                'offline state cannot claim runtime or playback qualification')
        count = state['next_chunk']
        retained = state['retained']
        require((count == 0 and not retained) or (count > 0 and 1 <= len(retained) <= count),
                'checkpoint is missing its committed predecessor')
        previous = digest(identity)
        predecessor = None
        if count > len(retained):
            retired = state['last_retirement']
            require(isinstance(retired, dict) and retired['index'] == count - len(retained) - 1,
                    'retirement boundary disagrees with retained chunks')
            require(is_hash(retired['chunk_sha256']) and is_hash(retired['deletion_receipt_sha256']),
                    'invalid retirement receipt hashes')
            previous = retired['chunk_sha256']
            predecessor = {key: retired[key] for key in ('run_name', 'anchor_sha256', 'chunk_sha256')}
        for index, record in enumerate(retained, count - len(retained)):
            require(type(record['index']) is int and record['index'] == index, 'retained order changed')
            require(record['run_name'] == f'continuation-{identity["stream_id"]}-{index:08d}',
                    'retained capture name changed')
            require(record['previous_chain_sha256'] == previous, 'retained chain boundary changed')
            require(record['predecessor'] == predecessor, 'retained predecessor link changed')
            require(isinstance(record['prompt'], str) and record['prompt'].strip()
                    and len(canonical(record['prompt'])) <= 65536, 'invalid retained prompt')
            require(type(record['seed']) is int and 0 <= record['seed'] < 2**64, 'invalid retained seed')
            require(is_hash(record['graph_sha256']) and is_hash(record['history_sha256']),
                    'invalid graph/history evidence hashes')
            require(record['acknowledged_frames'] == (25 if index == 0 else 24),
                    'retained delivery count changed')
            require(is_hash(record['anchor_sha256']) and is_hash(record['summary_file_sha256']),
                    'invalid retained capture hashes')
            require(set(record['tensor_sha256']) == {'images', 'video_latent', 'audio_latent', 'waveform'}
                    and all(is_hash(x) for x in record['tensor_sha256'].values()), 'invalid raw-output hashes')
            body = {key: value for key, value in record.items() if key != 'chunk_sha256'}
            require(digest(body) == record['chunk_sha256'], 'retained chunk hash mismatch')
            previous = record['chunk_sha256']
            predecessor = {key: record[key] for key in ('run_name', 'anchor_sha256', 'chunk_sha256')}
        require(state['chain_sha256'] == previous, 'checkpoint chain head mismatch')
        pending = state['pending']
        in_flight_acks = 0
        if pending is not None:
            require(pending['index'] == count and type(pending['acknowledged']) is int,
                    'pending chunk/counter changed')
            in_flight_acks = pending['acknowledged']
            require(0 <= in_flight_acks <= (25 if count == 0 else 24), 'invalid pending acknowledgement count')
        expected_acks = (25 + 24 * (count - 1) if count else 0) + in_flight_acks
        require(type(state['acknowledged_frames']) is int and state['acknowledged_frames'] == expected_acks,
                'cumulative frame count disagrees with chunk history')
        result._state = state
        if state['phase'] not in ('idle', 'halted'):
            result.halt('interrupted request/delivery; reconcile external effects before any new stream')
        return result
