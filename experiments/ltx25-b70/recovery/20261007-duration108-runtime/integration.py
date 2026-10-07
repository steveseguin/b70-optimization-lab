"""Sealed experiment integration; activated once by launcher, never at import.

Finite loopback-only actions use fixed evidence paths and pinned requests. No
action starts/stops/restarts a process or changes host/device settings.
"""
import asyncio
import copy
import json
import os
from pathlib import Path
import shutil
import threading
import time

_CTX = None


class Runtime:
    def __init__(self, packet, manifest, manifest_sha, run):
        import ltx_resolution_session as session
        import schedule
        import reference_gate
        import candidate_gate
        self.session = session
        self.packet, self.run, self.manifest = Path(packet), Path(run), manifest
        self.root = self.run.parent
        self.manifest_sha = manifest_sha
        self.identity_sha = session.digest(session.read_regular(self.run / 'server-identity.json'))
        self.plan_path = self.packet / 'resolution/candidate-plan.json'
        self.schedule = schedule.build_schedule(plan_path=self.plan_path)['schedule']
        self.setup = {r['name']: r for r in self.schedule['rows']}
        self.lock = threading.RLock()
        self.action_busy = False
        self.actions_done = set()
        self.first_native_binding = None
        self.adapter = None
        self.reference_receipt = self.run / 'same-size-native-references.json'
        self.candidate_receipt = self.run / 'same-size-candidate-check.json'
        self.fast_timed_receipt = self.run / 'same-size-timed-fast.json'
        self.authority = session.configure(self.plan_path, manifest_sha, self.identity_sha,
            self.run, self.inspect_state,
            {'reference_verified': reference_gate.verify_receipt,
             'candidate_verified': candidate_gate.verify_candidate_receipt}, self.schedule['rows'])
        import ltx_duration_guard as duration_guard
        self.session.require(self.session.digest(Path(duration_guard.__file__).read_bytes()) ==
            self.manifest['files']['source/scripts/ltx_duration_guard.py'],
            'Duration capture guard source differs from sealed manifest')
        capture_rows = []
        ordered = [r for r in self.authority.plan['requests']
                   if r['phase'] in ('native-reference', 'native-repeat')]
        ordered += self.schedule['rows']
        ordered += [r for r in self.authority.plan['requests']
                    if r['phase'] in ('candidate-check', 'timed-fast')]
        for row in ordered:
            if not any(node['class_type'] == 'LTXBaselineCapture' for node in row['graph'].values()):
                continue
            role = ('setup' if row.get('kind') in ('capture0', 'capture1') else
                    'full' if row['phase'] in ('native-reference', 'native-repeat') or
                              row.get('expected_emitted_index') is not None else 'fill')
            capture_rows.append({'name': row['name'], 'graph_sha256': row['graph_sha256'], 'role': role})
        self.capture_guard = duration_guard.configure(self.session.PLAN_SHA256, capture_rows,
                                                       self.active_capture_request)
        self.initial_free = shutil.disk_usage(self.root).free
        self.previous_free = self.initial_free
        self.consumed = 0
        self.storage_check()

    def fault(self):
        return (self.root / 'FAULT.json').exists() or (self.run / 'resolution-halt.json').exists()

    def active_capture_request(self):
        with self.authority.lock:
            self.authority.healthy()
            active = self.authority.active
            self.session.require(active is not None, 'Capture has no active registered request')
            row = self.authority.requests[active['name']]
            return {'name': active['name'], 'prompt_id': active['prompt_id'],
                    'plan_sha256': self.session.PLAN_SHA256, 'graph_sha256': row['graph_sha256']}

    def verify_first_native_binding(self):
        import reference_gate
        self.session.require(isinstance(self.first_native_binding, dict) and
                             len(self.first_native_binding) == 4,
                             'First-native evidence binding missing')
        for path, expected in self.first_native_binding.items():
            self.session.require(reference_gate.sha(reference_gate.read_file(Path(path))) == expected,
                                 'First-native admission evidence changed: ' + path)

    def capture_checkpoint(self, label, expected_count):
        receipt = self.capture_guard.receipt()
        self.session.require(receipt['failed'] is None and
            receipt['plan_sha256'] == self.session.PLAN_SHA256 and
            receipt['captures_reserved'] == expected_count and receipt['capture_cap'] == 22 and
            [r['name'] for r in receipt['captures']] ==
                [r['name'] for r in self.capture_guard.rows[:expected_count]] and
            all(r['name'] in self.authority.completed for r in receipt['captures']) and
            receipt['reserved_bytes'] == sum(r['charged_bytes'] for r in receipt['captures']) and
            receipt['reserved_bytes'] <= receipt['raw_budget_bytes'], 'Duration capture reservation evidence differs')
        self.write('duration-capture-' + label + '.json', {
            'runtime_manifest_sha256': self.manifest_sha, 'server_identity_sha256': self.identity_sha,
            'prewrite': receipt})

    def inspect_state(self):
        import runtime_observer
        return runtime_observer.actual_state(fault=self.fault())

    def storage_check(self):
        free = shutil.disk_usage(self.root).free
        self.consumed += max(0, self.previous_free-free)
        self.previous_free = free
        self.session.require(self.consumed <= 4*2**30 and free >= 50*2**30 + (4*2**30-self.consumed),
                             'Resolution experiment storage allowance exhausted')

    def write(self, name, value):
        self.session.write_exclusive(self.run / name, value)

    def receipt(self, prefix, name):
        return self.session.strict_json(self.session.read_regular(self.run / (prefix + name + '.json')))

    def require_dependencies(self, row):
        dependencies = list(row.get('depends_on', []))
        dependencies += self.schedule['boundary_dependencies'].get(row['name'], [])
        for dep in dependencies:
            if dep.startswith('barrier:'):
                self.session.require((self.run / ('resolution-phase-' + dep.split(':')[1] + '.json')).is_file(),
                                     'Required phase barrier missing')
            else:
                self.session.require(dep in self.authority.completed, 'Required setup request incomplete: ' + dep)

    def before_request(self, row, prompt_id):
        self.storage_check()
        self.session.require(not self.action_busy, 'Phase barrier active')
        self.require_dependencies(row)
        if row.get('kind') in ('capture0', 'capture1', 'decode-probe'):
            needed = row.get('admission_action', 'admit-decode')
            self.session.require(needed in self.actions_done, 'Fresh optimized memory admission required')
        if row['phase'] in ('native-reference', 'native-repeat'):
            self.session.require('before-native' in self.actions_done and self.adapter is not None,
                                 'Native phase observation/preparation missing')
            if row['name'] != self.authority.plan['requests'][0]['name']:
                self.session.require('verify-first-native' in self.actions_done,
                                     'First49-frame shape and memory admission required')
                self.verify_first_native_binding()
            value = self.adapter.before_request(row['name'])
            self.write('native-memory-before-' + row['name'] + '.json', value)
        self.session.require(row['phase'] != 'timed', 'Control requests are not admitted')
        if row['phase'] in ('candidate-check', 'timed-fast'):
            name = 'resolution-duration108-20261007-freeze'
            self.session.require(name in self.authority.completed, 'Passed freeze required before candidate/timing')
            state = self.inspect_state()
            self.session.require(state['captures_frozen'] is True and state['loads_frozen'] is True,
                                 'Actual optimized runtime is not frozen')

    def after_request(self, row, prompt_id):
        import setup_gates
        if row['phase'] in ('native-reference', 'native-repeat'):
            value = self.adapter.after_request(row['name'])
            self.write('native-memory-after-' + row['name'] + '.json', value)
        kind, name = row.get('kind'), row['name']
        gates = {'window-probe': ('text-window-probe-', setup_gates.validate_window),
                 'coverage': ('sampler-capture-coverage-', setup_gates.validate_coverage),
                 'decode-probe': ('decode-probe-', setup_gates.validate_decode),
                 'freeze': ('sampler-capture-freeze-', setup_gates.validate_freeze)}
        if kind in gates:
            prefix, gate = gates[kind]
            checked = gate(self.receipt(prefix, name), name, self.identity_sha)
            self.write('resolution-setup-accepted-' + name + '.json', checked)
        elif kind == 'prepare-native':
            self.session.require(self.adapter is not None and self.adapter.ready and self.adapter.failed is None,
                                 'Native residence preparation did not pass')
        elif kind in ('pin0', 'pin1'):
            worker = row['graph']['483']['inputs']['worker']
            receipt = self.receipt('sampler-pin-', name)
            self.session.require(receipt['server_identity_sha256'] == self.identity_sha and
                receipt['outcome'] == 'pinned' and receipt['worker'] == worker and
                receipt['worker_name'] == 'ltx-sample-%d' % worker and receipt['sampler_workers'] == 2 and
                receipt['sampler_batch'] == 1 and receipt['output_size'] == '640x384',
                'Worker pin did not pass')
        self.storage_check()

    def on_failure(self, row, prompt_id, error):
        if row['phase'] in ('native-reference', 'native-repeat') and self.adapter is not None:
            try:
                self.adapter.abort_request(error)
            finally:
                self.write('native-failure-' + row['name'] + '.json', {'error': str(error),
                    'adapter_receipts': self.adapter.receipts,
                    'controller_receipts': self.adapter.controller.receipts if self.adapter.controller else []})

    def prepare_native(self, name):
        import torch
        import nodes
        import comfy.model_management as mm
        from native_adapter import NativeAdapter
        self.session.require(name == 'resolution-duration108-20261007-prepare-native' and self.adapter is None,
                             'Unexpected/repeated native preparation')
        self.session.require_phase('native', self.authority.plan['qualification_id'], name)
        hashes = {str(self.packet / path): sha for path, sha in self.manifest['files'].items()
                  if path.startswith('source/')}
        hashes.update(self.manifest['runtime']['files'])
        self.adapter = NativeAdapter(torch=torch, nodes=nodes, model_management=mm,
            session=self.session, qualification_id=self.authority.plan['qualification_id'], run_name=name,
            plan_sha256=self.session.PLAN_SHA256, runtime_sha256=self.manifest_sha,
            source_hashes=hashes, fault_check=self.fault)
        snapshot = self.adapter.prepare()
        self.write('native-preparation.json', {'snapshot': snapshot, 'receipts': self.adapter.receipts})
        return snapshot

    def quiescent(self, no_tails=True):
        self.authority.healthy()
        self.session.require(self.authority.active is None, 'Active prompt at phase barrier')
        state = self.inspect_state()
        self.session.require(state['fault'] is False, 'Fault at phase barrier')
        self.session.require_quiescent(state, no_tails=no_tails)
        return state

    def native_observation(self, name):
        state = self.quiescent()
        snapshot = self.adapter.native_state()
        controller = self.adapter.controller
        self.session.require(controller.failed is None and self.adapter.failed is None,
                             'Native safety failed before observation')
        from native_safety import ATTRIBUTE
        self.session.require(all(getattr(self.adapter.objects[r], ATTRIBUTE, None) is controller
                                 for r in ('video_vae', 'audio_vae')), 'Native OOM refusal not attached')
        observation = {'schema': 'ltx.native-reference-state.v1', 'phase': 'native_reference',
            'server_identity_sha256': self.identity_sha,
            'qualification_id': self.authority.plan['qualification_id'], 'timestamp_ms': time.time_ns()//1000000,
            'sampler_routes': state['sampler_routes'], 'lean_sampler_installs': state['lean_state'],
            'decode_replicas': state['decode_replicas'], 'oom_fallback_attempts': 0,
            'queue_running': state['queue_running_ids'], 'queue_pending': state['queue_pending_ids'],
            **{'pending_' + s: [j['index'] for j in state['pipeline']['stages'].get(s, {}).get('jobs', [])]
               for s in ('encode', 'sample', 'decode', 'save')},
            'native_residency_admitted': True, 'no_owner_eviction': True,
            'oom_to_tiled_refusal_installed': True, 'safety_observation': snapshot}
        self.write('native-' + name + '.json', observation)
        return observation

    def retire_tails(self, name):
        self.quiescent(no_tails=False)
        import ltx_pipeline
        def empty():
            state = self.inspect_state()
            return state['queue_running'] == state['queue_pending'] == 0 and self.authority.active is None
        self.session.retire_completed_tails(ltx_pipeline, self.run / ('resolution-tails-' + name + '.json'), empty)
        self.quiescent()

    def action(self, name):
        import reference_gate
        import candidate_gate
        with self.lock:
            self.authority.healthy()
            self.session.require(name not in self.actions_done, 'Phase action already performed')
            self.storage_check()
            if name == 'before-native':
                self.session.require('resolution-duration108-20261007-prepare-native' in self.authority.completed,
                                     'Native preparation incomplete')
                self.native_observation('before')
            elif name == 'verify-first-native':
                native = [r for r in self.authority.plan['requests']
                          if r['phase'] in ('native-reference', 'native-repeat')]
                first = native[0]
                self.session.require(self.authority.phase == 'native_reference' and
                    'before-native' in self.actions_done and first['name'] in self.authority.completed and
                    not any(r['name'] in self.authority.completed for r in native[1:]),
                    'First-native barrier must precede the other five native requests')
                observation = self.native_observation('first')
                folder = self.root / 'output/validation' / first['name']
                metadata_raw = reference_gate.read_file(folder / 'summary.json')
                metadata = reference_gate.strict_json(metadata_raw)
                self.session.require(metadata['run_name'] == first['name'] and
                    metadata['sample_rate'] == 48000 and metadata['deterministic_enabled'] is True and
                    metadata['deterministic_warn_only'] is False, 'First-native capture identity differs')
                archive = reference_gate.read_file(folder / 'tensors.safetensors')
                tensors = reference_gate.tensor_inventory(archive, metadata['tensors'])
                memory_path = self.run / ('native-memory-after-' + first['name'] + '.json')
                memory_raw = self.session.read_regular(memory_path)
                memory = self.session.strict_json(memory_raw)
                self.session.require(memory['admitted'] is True and memory['event'] == 'after' and
                    memory['request_id'] == first['name'] and
                    memory['snapshot']['plan_sha256'] == self.session.PLAN_SHA256 and
                    memory['snapshot']['runtime_sha256'] == self.manifest_sha and
                    memory['snapshot']['phase'] == 'native-reference' and
                    memory['snapshot']['fault'] is False and
                    set(memory['snapshot']['physical_free_bytes']) == {'xpu:%d' % i for i in range(4)} and
                    all(type(v) is int and v >= 2*2**30 for v in memory['snapshot']['physical_free_bytes'].values()),
                    'First-native measured memory floor refused')
                self.write('resolution-phase-first_native_verified.json', {
                    'schema': 'ltx.duration108.first-native-admission.v1',
                    'plan_sha256': self.session.PLAN_SHA256,
                    'runtime_manifest_sha256': self.manifest_sha, 'server_identity_sha256': self.identity_sha,
                    'name': first['name'], 'frame_count': 49, 'tensors': tensors,
                    'archive_sha256': reference_gate.sha(archive),
                    'metadata_sha256': reference_gate.sha(metadata_raw),
                    'memory_after_sha256': self.session.digest(memory_raw),
                    'observation': observation,
                    'claim': 'First actual shape/finite/memory admission only; native repeat and optimized parity still required.'})
                barrier = self.run / 'resolution-phase-first_native_verified.json'
                self.first_native_binding = {
                    str(folder / 'tensors.safetensors'): reference_gate.sha(archive),
                    str(folder / 'summary.json'): reference_gate.sha(metadata_raw),
                    str(memory_path): self.session.digest(memory_raw),
                    str(barrier): self.session.digest(self.session.read_regular(barrier))}
            elif name == 'verify-native':
                self.session.require('before-native' in self.actions_done and
                    all(r['name'] in self.authority.completed for r in [r for r in self.authority.plan['requests'] if r['phase'] in ('native-reference', 'native-repeat')]),
                    'Six native requests required')
                self.capture_checkpoint('native', 6)
                self.native_observation('after')
                evidence = {str(self.packet / 'manifest.json'): self.manifest_sha,
                            str(self.run / 'native-preparation.json'): self.session.digest(
                                self.session.read_regular(self.run / 'native-preparation.json'))}
                for path in self.run.glob('native-memory-*.json'):
                    evidence[str(path)] = self.session.digest(self.session.read_regular(path))
                contract = {'schema': 'ltx.native-reference-runtime-contract.v1',
                    'plan_sha256': self.session.PLAN_SHA256,
                    'parent_manifest_sha256': self.manifest['resolution101']['parent_manifest_sha256'],
                    'server_run': str(self.run), 'server_identity_sha256': self.identity_sha,
                    'successor_manifest_sha256': self.manifest_sha,
                    'model_verification_sha256': self.manifest['model_verification_sha256'],
                    'request_names': [r['name'] for r in [r for r in self.authority.plan['requests'] if r['phase'] in ('native-reference', 'native-repeat')]],
                    'runtime_evidence': evidence}
                for key, suffix in (('before_native','before'), ('after_native','after')):
                    path = self.run / ('native-' + suffix + '.json')
                    contract[key] = {'path': str(path), 'sha256': self.session.digest(self.session.read_regular(path))}
                contract_path = self.run / 'native-runtime-contract.json'
                self.write(contract_path.name, contract)
                reference_gate.verify_references(self.root, self.plan_path, contract_path,
                    self.session.digest(self.session.read_regular(contract_path)), self.reference_receipt)
                self.authority.advance('reference_verified', self.reference_receipt,
                                       self.session.digest(self.session.read_regular(self.reference_receipt)))
                self.adapter.close()
            elif name == 'start-optimized':
                self.session.require('verify-native' in self.actions_done, 'Native proof not verified')
                self.authority.advance('optimized_preparation')
            elif name in ('admit-capture0', 'admit-capture1', 'admit-decode'):
                self.quiescent()
                self.session.require(self.authority.phase == 'optimized_preparation',
                                     'Optimized preparation phase required')
                before, after = {'admit-capture0': ('pin0', 'capture0'),
                                 'admit-capture1': ('pin1', 'capture1'),
                                 'admit-decode': ('coverage', 'decode-probe')}[name]
                self.session.require('resolution-duration108-20261007-' + before in self.authority.completed and
                                     'resolution-duration108-20261007-' + after not in self.authority.completed,
                                     'Memory admission must immediately precede its setup stage')
                if name in ('admit-capture1', 'admit-decode'):
                    needed = ['retire-capture0-tails']
                    if name == 'admit-decode':
                        needed.append('retire-capture1-tails')
                    self.session.require(all(action in self.actions_done for action in needed),
                                         'Previous capture tails must be retired before admission')
                import torch
                thresholds = {'admit-capture0': (7,7,2,9),
                              'admit-capture1': (7,7,2,9),
                              'admit-decode': (2,2,10,9)}[name]
                free = {}
                for i in range(4):
                    torch.xpu.synchronize(i)
                    free['xpu:%d' % i] = int(torch.xpu.mem_get_info(i)[0])
                for role, expected in self.adapter.controller.expected_residence.items():
                    from native_adapter import fingerprint
                    self.session.require(fingerprint(self.adapter._rows(role, require_loaded=True)) == expected,
                                         'Optimized preparation resident owner changed: ' + role)
                self.write('resolution-' + name + '.json', {'physical_free_bytes': free,
                    'required_bytes': {'xpu:%d' % i: n*2**30 for i,n in enumerate(thresholds)},
                    'allowances_are_not_proven_peak_bounds': True, 'time_ns': time.time_ns()})
                self.session.require(all(free['xpu:%d' % i] >= n*2**30 for i,n in enumerate(thresholds)),
                                     'Actual optimized preparation memory admission refused')
            elif name in ('retire-capture0-tails', 'retire-capture1-tails'):
                row = next(r for r in self.setup.values() if r.get('retirement_action') == name)
                index = row['clip_index']
                self.session.require(row['name'] in self.authority.completed,
                                     'Capture request incomplete')
                # A tail that silently failed must never be mistaken for a successful capture.
                done = self.receipt('pipeline-done-sample-', str(index))
                observation = done.get('session_observation', {})
                self.session.require(observation.get('server_identity_sha256') == self.identity_sha and
                    observation.get('runtime_manifest_sha256') == self.manifest_sha and
                    observation.get('plan_sha256') == self.session.PLAN_SHA256 and
                    observation.get('phase') == 'optimized_preparation' and
                    observation.get('reference_receipt_sha256') == self.authority.references_sha and
                    done.get('stage') == 'sample' and done.get('index') == index and done['finite'] is True,
                                     'Capture sample did not finish finite')
                capture = self.receipt('pipeline-sampler-', row['name'])
                authorization = capture.get('phase_authorization', {})
                target = 'ltx-sample-%d' % row['worker']
                self.session.require(capture.get('pinned_worker') == target and
                    capture.get('clip_index') == index and capture.get('run_name') == row['name'] and
                    capture.get('server_identity_sha256') == self.identity_sha and
                    capture.get('sampler_workers') == 2 and capture.get('sampler_batch') == 1 and
                    capture.get('mode') == 'pipeline' and capture.get('depth') == 1 and
                    capture.get('detail', {}).get('emitted_index') == -1 and
                    capture.get('detail', {}).get('fill') is True and
                    authorization.get('phase') == 'optimized_preparation' and
                    authorization.get('plan_sha256') == self.session.PLAN_SHA256 and
                    authorization.get('qualification_id') == self.authority.plan['qualification_id'] and
                    authorization.get('runtime_manifest_sha256') == self.manifest_sha and
                    authorization.get('server_identity_sha256') == self.identity_sha and
                    authorization.get('reference_receipt_sha256') == self.authority.references_sha,
                    'Capture request worker or phase binding differs')
                state = self.quiescent(no_tails=False)
                jobs = state['pipeline']['stages'].get('sample', {}).get('jobs', [])
                self.session.require(len(jobs) == 1 and jobs[0]['index'] == index and
                    jobs[0].get('target') == target and jobs[0]['done'] is True and jobs[0]['error'] is None,
                    'Capture live job does not match its pinned worker')
                import torch
                free = {}
                for device in range(4):
                    torch.xpu.synchronize(device)
                    free['xpu:%d' % device] = int(torch.xpu.mem_get_info(device)[0])
                self.write('resolution-memory-after-' + row['kind'] + '.json',
                    {'physical_free_bytes': free, 'minimum_bytes': 2*2**30, 'time_ns': time.time_ns()})
                self.session.require(all(value >= 2*2**30 for value in free.values()),
                                     'Post-capture physical memory floor refused')
                self.retire_tails(name)
            elif name == 'verify-candidate':
                self.retire_tails(name)
                self.capture_checkpoint('candidate', 15)
                candidate_gate.verify_outputs(self.root, self.plan_path, self.reference_receipt,
                    self.authority.references_sha, 'candidate-check', self.candidate_receipt)
                self.authority.advance('candidate_verified', self.candidate_receipt,
                                       self.session.digest(self.session.read_regular(self.candidate_receipt)))
            elif name == 'start-timing':
                self.session.require('verify-candidate' in self.actions_done, 'Candidate proof not verified')
                self.authority.advance('timing')
            elif name == 'verify-fast-timed':
                self.retire_tails(name)
                self.capture_checkpoint('timed-fast', 22)
                candidate_gate.verify_outputs(self.root, self.plan_path, self.reference_receipt,
                    self.authority.references_sha, 'timed-fast', self.fast_timed_receipt,
                    self.candidate_receipt, self.authority.candidate_sha)
                self.write('resolution-phase-fast_verified.json', {
                    'schema': 'ltx.client-fast-barrier.v1',
                    'plan_sha256': self.session.PLAN_SHA256,
                    'runtime_manifest_sha256': self.manifest_sha,
                    'server_identity_sha256': self.identity_sha,
                    'fast_receipt_path': str(self.fast_timed_receipt),
                    'fast_receipt_sha256': self.session.digest(self.session.read_regular(self.fast_timed_receipt))})
            else:
                raise RuntimeError('Unknown finite resolution action')
            self.actions_done.add(name)
            self.storage_check()
            result = {'passed': True, 'action': name, 'phase': self.authority.phase}
            return result


class LTXResolutionPrepareNative:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}
    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, run_name):
        if _CTX is None:
            raise RuntimeError('Resolution runtime not initialized')
        _CTX.prepare_native(run_name)
        return {'ui': {'text': ['native residence admitted']}}


NODE_CLASS_MAPPINGS = {'LTXResolutionPrepareNative': LTXResolutionPrepareNative}


def install(packet, manifest, manifest_sha, run):
    global _CTX
    if _CTX is not None:
        raise RuntimeError('Resolution integration may only install once')
    import execution
    import executor_guard
    _CTX = Runtime(packet, manifest, manifest_sha, run)
    result = executor_guard.install(execution.PromptExecutor, _CTX.authority,
        _CTX.before_request, _CTX.after_request, _CTX.on_failure)
    _CTX.write('resolution-executor-guard.json', result)


def install_routes():
    from aiohttp import web
    from server import PromptServer
    if _CTX is None:
        raise RuntimeError('Resolution routes require sealed launcher installation')

    @web.middleware
    async def admission(request, handler):
        if request.method == 'POST' and request.path == '/prompt':
            if _CTX.action_busy or _CTX.authority.failed is not None or _CTX.fault():
                return web.json_response({'error': 'resolution phase closed or halted'}, status=503)
        return await handler(request)
    PromptServer.instance.app.middlewares.append(admission)

    @PromptServer.instance.routes.get('/ltx-resolution/status')
    async def status(request):
        with _CTX.authority.lock:
            state = _CTX.inspect_state()
            observation = {'schema': 'ltx.resolution-client-phase.v1', 'phase': _CTX.authority.phase,
                'plan_sha256': _CTX.session.PLAN_SHA256,
                'runtime_manifest_sha256': _CTX.manifest_sha,
                'server_identity_sha256': _CTX.identity_sha,
                'qualification_id': _CTX.authority.plan['qualification_id'],
                'reference_receipt_sha256': _CTX.authority.references_sha,
                'candidate_receipt_sha256': _CTX.authority.candidate_sha,
                'active_request': _CTX.authority.active,
                'fault': _CTX.fault() or _CTX.authority.failed is not None,
                'observed_at_ms': time.time_ns()//1000000,
                'queue_running': state['queue_running'], 'queue_pending': state['queue_pending']}
            # This is explicitly the latest observation, not a qualification
            # receipt. Atomic replacement keeps readers from seeing partial JSON.
            temporary = _CTX.run / 'resolution-client-phase.json.next'
            _CTX.session.write_exclusive(temporary, observation)
            os.replace(temporary, _CTX.run / 'resolution-client-phase.json')
            directory = os.open(_CTX.run, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        return web.json_response({'phase': _CTX.authority.phase, 'halted': _CTX.authority.failed,
            'active': _CTX.authority.active, 'completed': list(_CTX.authority.completed),
            'actions': sorted(_CTX.actions_done), 'state': state,
            'server_identity_sha256': _CTX.identity_sha, 'runtime_manifest_sha256': _CTX.manifest_sha})

    @PromptServer.instance.routes.post('/ltx-resolution/action')
    async def action(request):
        if _CTX.action_busy:
            return web.json_response({'error': 'resolution action already active'}, status=409)
        body = await request.json()
        if set(body) != {'action'} or not isinstance(body['action'], str):
            return web.json_response({'error': 'one named action required'}, status=400)
        if _CTX.action_busy:
            return web.json_response({'error': 'resolution action already active'}, status=409)
        _CTX.action_busy = True
        try:
            result = await asyncio.to_thread(_CTX.action, body['action'])
            return web.json_response(result)
        except Exception as error:
            try:
                _CTX.authority.halt(error)
            except Exception:
                pass
            return web.json_response({'error': str(error), 'halted': True}, status=409)
        finally:
            _CTX.action_busy = False
