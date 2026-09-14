#!/usr/bin/env python3
"""Inactive guarded actual tiny-CPU resident lifecycle qualification. No compilation or accelerator access.

Reuses the frozen integration process-local guards; native scheduling remains separate.
--check-only is stdlib-only. Native CPU execution requires parent scheduling.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import traceback
import unittest

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
SOURCE = ROOT / 'prepared-encoder-na-axis-10/source'
TRITON_UTILS = Path('/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/torch/utils/_triton.py')
HELPERS = {
    'scripts/test-host-embedding-integration-cpu.py': '6f0e89f549b9abd704c4648d1f06288b57607d3c31174c3a7dc1cfc22103e26d',
    'scripts/host_embedding_resident_node_v2.py': 'bdaa14a06bd9937946eee470e562f6109df239273e905197d6e94fad28dd02f7',
    'scripts/host_embedding_transition_memory.py': '707de7176a47a26063b7282fc7368818d3362b1bd917c76141d58ed00dfcdb86',
    'scripts/test-host-embedding-resident-lifecycle-cpu-fixture.py': '4e2d0d92eea345dcb0ae36a4143f7f0d8887dda5c996845c37c6eba30673ee73',
    'scripts/test-host-embedding-candidate-cpu-v3.py': '1448bcf30e481f6c8e5d46a23cea1f84ef2e01b8cd574abd9716bddb03c1e6ca',
    'scripts/host_embedding_clip_v2.py': '53d45d883bcc46d1a5889d3b6f162b0e95417e834c62dde8d8836791cffe2994',
    'scripts/host_embedding_placement_node_v2.py': '4ab92f1580f8f54ecc6631acd4fb74603d06bc8cf6c3760ede7638c655f5753b',
    'scripts/test-host-embedding-integration-cpu-fixture.py': '2fa5d3636afdc7f17fc5957916cc525fa935ff1181efc90dad8753860e69f79e',
    'scripts/cpu_comfy_import_policy_v1.py': '7634e653e66a682596e2bd941017722a41b9241c785dd1fb4885bfc051c31bec',
    'scripts/test-host-embedding-candidate-cpu-v2.py': '9d8053868a7a26c6dd36ff0ae1889278effee866e93cf7e931546d06a8493bd3',
    'scripts/test-host-embedding-candidate-cpu.py': '2088003e92f50c4d2c2012fb2012f1289053ab3ac782edd0228bb3a297b47534',
    'scripts/test-host-embedding-candidate-cpu-fixture-v2.py': 'b1295210e04c20069bded9972bdbb29ee65589410c57dc81a410956ae7e63a32',
    'scripts/ltx_host_embedding_candidate.py': 'b58bf0bbfc084ea89f2673f3c10d9520b5f6ac1993517c79e346ea2c573ca7e9',
    'native-cpp-block-01/accelerator_guard_v2.py': 'b37549c29f589702e1a9a8279a9ecdc5355fb7b56277f35ff0199a34488908ce',
    'native-cpp-block-01/cpu_import_policy_v3.py': '03fdcf06f6de141ef7197b2b8e5a813a0929bd2bc958825c7d68f4e353843c0a',
}
COMFY_MANAGEMENT_SHA = 'ef3f3af0657c1b022ad69b25928fa52dd429db9aed9cb688e89c7fbe68ab50cd'
CPU_QUALIFICATION = ROOT / 'host-embedding-cpu-v3-native-01/result.json'
CPU_QUALIFICATION_SHA = 'eacb3389cc9fd8065c135bc6dea2a11b9b4263520c3d88f8096ce08f4c762948'
INTEGRATION_QUALIFICATION = ROOT / 'host-embedding-cpu-integration-native-01/result.json'
INTEGRATION_QUALIFICATION_SHA = 'b06e617ccb8c307eeb0a8b29981049f30561985480007c85259cca54b7e09326'
TRITON_SHA = '4ff5137347620b8995807cfe3711f7826ef062581cde7d19e798ffbc781f810a'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_gate():
    require(not (ROOT / 'FAULT.json').exists(), 'Fault latch prohibits native work')
    for name, expected in HELPERS.items():
        require(sha(LANE / name) == expected, 'Frozen helper changed: ' + name)
    require(sha(SOURCE / 'comfy/model_management.py') == COMFY_MANAGEMENT_SHA, 'Pinned Comfy import source changed')
    require(sha(TRITON_UTILS) == TRITON_SHA, 'Triton helper source changed')
    tree = ast.parse((LANE / 'scripts/test-host-embedding-candidate-cpu-fixture-v2.py').read_text())
    pins = ast.literal_eval(next(node.value for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'PINS' for target in node.targets)))
    pins.update({'comfy/sd.py': '41cbf195657cc81a60173f13f192966c4276bf7931a6c10f75870a66c59546b0',
                 'scripts/encoder_diagnostics.py': 'f16d8cefa02dd7557c13348a95e6c0ce07a42c4d0f46b36329ab1c4f182a439a'})
    require(sha(CPU_QUALIFICATION) == CPU_QUALIFICATION_SHA, 'Qualified CPU candidate receipt changed')
    qualification = json.loads(CPU_QUALIFICATION.read_text())
    require(qualification['status'] == 'passed-guarded-cpu-fixture' and qualification['tests_run'] == 6
            and qualification['xpu_initialized'] is False and qualification['cuda_initialized'] is False
            and qualification['final_guards_intact'] is True, 'Standalone CPU qualification missing')
    require(sha(INTEGRATION_QUALIFICATION) == INTEGRATION_QUALIFICATION_SHA, 'Qualified CLIP integration receipt changed')
    previous = json.loads(INTEGRATION_QUALIFICATION.read_text())
    require(previous['status'] == 'passed-guarded-cpu-integration' and previous['tests_run'] == 6
            and previous['xpu_initialized'] is False and previous['cuda_initialized'] is False
            and previous['final_guards_intact'] is True, 'Actual CLIP integration qualification missing')
    for name, expected in pins.items():
        require(sha(SOURCE / name) == expected, 'Frozen actual source changed: ' + name)
    return pins


def write_exclusive(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def install_backend_refusals(torch, triton_utils, report, guard):
    """Block every backend lookup/compile attempt; never call originals."""
    guard.require_clean(report)
    require('backend_refusals' not in report, 'Backend refusal cannot be reinstalled')
    report['backend_refusals'] = {'scope': 'All triton_backend and torch.compile calls forbidden; no compilation',
                                  'attempts': [], 'tripped': False}
    def make_trap(label):
        def blocked(*args, **kwargs):
            report['accelerator_guard_tripped'] = True
            record = {'entry': label, 'pid': os.getpid(), 'phase': report.get('phase'),
                      'monotonic_ns': time.monotonic_ns(), 'stack': traceback.format_stack(limit=24)}
            report['backend_refusals']['tripped'] = True
            report['backend_refusals']['attempts'].append(record)
            raise guard.AcceleratorAccessBlocked('CPU embedding proof forbids ' + label)
        return blocked
    backend_trap = make_trap('torch.utils._triton.triton_backend')
    compile_trap = make_trap('torch.compile')
    triton_utils.triton_backend = backend_trap
    torch.compile = compile_trap
    def intact():
        guard.require_clean(report)
        require(triton_utils.triton_backend is backend_trap and torch.compile is compile_trap,
                'CPU backend refusal identity changed')
    intact()
    return intact


class StopOnFailureResult(unittest.TextTestResult):
    def addError(self, test, error):
        super().addError(test, error)
        self.stop()

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    directory = args.evidence_dir
    require(directory.is_absolute() and directory.parent == ROOT and
            directory.name.startswith('host-embedding-cpu-') and not directory.exists()
            and not directory.is_symlink(), 'Evidence directory must be a new bounded absolute path')
    directory.mkdir()
    report = {'schema': 'ltx.host-embedding-resident-lifecycle-guarded-cpu.v1', 'status': 'failed',
              'pid': os.getpid(), 'ppid': os.getppid(), 'command': list(sys.argv),
              'phase': 'source-gate', 'torch_imported': False, 'tests_run': 0,
              'native_gpu_requests': 0, 'compilation_permitted': False,
              'driver_sha256': sha(Path(__file__)), 'helper_sha256s': HELPERS,
              'candidate_cpu_receipt_sha256': CPU_QUALIFICATION_SHA,
              'integration_cpu_receipt_sha256': INTEGRATION_QUALIFICATION_SHA,
              'triton_utils_sha256': TRITON_SHA, 'comfy_model_management_sha256': COMFY_MANAGEMENT_SHA,
              'scope': 'Actual tiny CPU CLIP loader registry and weakref lifecycle across resident modes; nonencoder owners and memory observations are fakes; no full model, GPU placement, real clip, speed or full-memory-peak qualification'}
    torch = None
    integrity = None
    try:
        require('torch' not in sys.modules, 'Fresh disposable interpreter required')
        report['source_pins'] = source_gate()
        startup = {**report, 'timestamp_utc': datetime.now(timezone.utc).isoformat(),
            'proc_start_ticks': Path(f'/proc/{os.getpid()}/stat').read_text().split(') ')[1].split()[19],
            'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'status': 'startup-before-torch'}
        write_exclusive(directory / 'startup-identity.json', startup)
        report['startup_sha256'] = sha(directory / 'startup-identity.json')
        if args.check_only:
            report.update(status='passed-stdlib-source-check', phase='source-check-only', native_cpu_tests_executed=False)
            return 0
        report['phase'] = 'torch-import'
        import torch as imported_torch
        torch = imported_torch
        report['torch_imported'] = True
        guard = load('host_embedding_accelerator_guard', LANE / 'native-cpp-block-01/accelerator_guard_v2.py')
        policy = load('host_embedding_cpu_import_policy', LANE / 'native-cpp-block-01/cpu_import_policy_v3.py')
        guard.install(torch, report)
        comfy_import_policy = load('host_embedding_comfy_import_policy', LANE / 'scripts/cpu_comfy_import_policy_v1.py')
        import_controller = comfy_import_policy.ComfyImportPolicy(torch, report, guard,
            model_management_source=SOURCE / 'comfy/model_management.py')
        imports_complete = False
        cpu_intact = policy.install(torch, report, guard)
        report['phase'] = 'backend-refusal-install-before-Comfy'
        import torch.utils._triton as triton_utils
        require(Path(triton_utils.__file__).resolve() == TRITON_UTILS, 'Unexpected Triton helper module')
        backend_intact = install_backend_refusals(torch, triton_utils, report, guard)
        def integrity():
            cpu_intact()
            backend_intact()
            import_controller.require_intact(require_complete=imports_complete)
            require(not torch.xpu.is_initialized() and not torch.cuda.is_initialized(), 'Accelerator initialized')
            require(not (ROOT / 'FAULT.json').exists(), 'Fault latch prohibits CPU work')
        integrity()
        report['phase'] = comfy_import_policy.EXPECTED_PHASE
        fixture = load('guarded_host_embedding_resident_fixture', LANE / 'scripts/test-host-embedding-resident-lifecycle-cpu-fixture.py')
        import_controller.finish_import(sys.modules['comfy.model_management'])
        imports_complete = True
        integrity()
        report['identity_after_import'] = {'guards_intact': True, 'xpu_initialized': False, 'cuda_initialized': False}
        report['cpu_policy_reuse_note'] = 'Frozen policy description mentions compiled arms; this driver permits only these CPU eager tests and rejects every compile/backend lookup.'
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True, warn_only=False)
        report['determinism'] = {'enabled': torch.are_deterministic_algorithms_enabled(),
                                'warn_only': torch.is_deterministic_algorithms_warn_only_enabled()}
        fixture.Tests.setUp = lambda self: integrity()
        fixture.Tests.tearDown = lambda self: integrity()
        report['phase'] = 'actual-CPU-tests'
        with (directory / 'tests.log').open('x') as stream:
            result = unittest.TextTestRunner(stream=stream, verbosity=2,
                resultclass=StopOnFailureResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(fixture.Tests))
        write_exclusive(directory / 'fixture-evidence.json', fixture.EVIDENCE)
        report['fixture_evidence_sha256'] = sha(directory / 'fixture-evidence.json')
        report['test_names'] = list(fixture.TEST_NAMES)
        report['test_skips'] = [reason for _, reason in result.skipped]
        report['tests_run'] = result.testsRun
        report['test_failures'] = [text for _, text in result.failures]
        report['test_errors'] = [text for _, text in result.errors]
        integrity()
        require(source_gate() == report['source_pins'], 'Source identity changed during tests')
        require(result.wasSuccessful() and result.testsRun == 6 and not result.skipped, 'CPU fixture failed; no retry')
        report.update(status='passed-guarded-cpu-resident-lifecycle', phase='finished', native_cpu_tests_executed=True,
                      identity_after_tests={'guards_intact': True, 'xpu_initialized': False, 'cuda_initialized': False})
        return 0
    except BaseException as error:
        report.update(status='failed', error=repr(error), traceback=traceback.format_exc())
        return 1
    finally:
        if torch is not None:
            report['xpu_initialized'] = bool(torch.xpu.is_initialized())
            report['cuda_initialized'] = bool(torch.cuda.is_initialized())
            if integrity is not None:
                try:
                    integrity()
                    report['final_guards_intact'] = True
                except BaseException as error:
                    report.update(status='failed', final_guards_intact=False, final_guard_error=repr(error))
        write_exclusive(directory / 'result.json', report)
        if report['status'] == 'failed':
            return 1


if __name__ == '__main__':
    raise SystemExit(main())
