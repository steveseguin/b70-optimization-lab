#!/usr/bin/env python3
"""One authorized CPU-tool probe; default is a read-only plan, never native execution.

Original p198 device/host checkpoints are read-only. Native deletion is confined
to a new ignored copy of the tiny host s1 fixture. Only the pinned GNU host ELF
and its two checkpoint tool modes can execute; no model owner/generation exists.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

from checkpoint_bridge import IDENTITY_FIELDS, validate_snapshot
from native_checkpoint_store import NativeCheckpointStore


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PACKET = HERE.parent / 'stage2/packet198-postreply-checkpoint'
DEVICE_ROOT = PACKET / 'evidence/device-p198-lifecycle-A-a/checkpoints'
HOST_BINARY = PACKET / 'build/host/own-rt-iq3'
HOST_SHA = '41cbb6c4ad3bf6626dfba24d3bbd9d95d76b512102e8b94c164e9d421b3c40ca'
DEVICE_SHA = 'c9b401089d95eeb152953a8c0d82d0678de2474934941bc6c97abd4b03287875'
FIXTURES = HERE / 'checkpoint-fixtures-p198'
SCRATCH = HERE / '.native-checkpoint-store-probe/20261023-a'
RECEIPT = HERE / 'receipts/native-checkpoint-store-tools-20261023.json'
MANIFESTS = {
    's1': 'e22f08a8eedadca40f395c2c4254f35626b31249beca0367439e10d42450b361',
    's3': 'e36cb9913f2967be8a8636a07c3605367c8970e189c4bb1b94592198bd78f8bb',
}
ANCHORS = {
    'evidence/independent-device-result.json': '2e0bfb78c6703e9e34c4cf44e88a20c301ea8a072e587e09586d4604eb6bbb31',
    'READY-FOR-DEVICE.json': 'ae105c292f6122165fc9695c59228a08694e79688369de621ad60894a2c75aed',
    'evidence/build-compile-only.json': 'c1b3378c6237254a4b6363a8bccd20cfbfb67b186deefa7ea7899b2828e2e962',
    'evidence/host-probe.json': 'a35a03c966536c5421bc335a32a7915f211f470ec7e2c424c8788a1ad03bbc70',
    'evidence/host-probe-artifacts.json': '3811ea9b20761648b3cb6ccf260c7169e855803b4e48b828d5475c3f24335108',
}
ENV_SOURCE = PACKET.parent / 'packet181-session-swap-v3/one-card/launch_env.py'
ENV_SHA = 'a55f31e6052e33d5b4702b01eddd4e5af5c4029fda6fc452dd8f564f3dfdc364'
HOST_S1_SHA = 'e6662298129208a75996dff27957e974665ace9408e714eb036700db7fe98847'


def require(ok, message):
    if not ok: raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as file: return hashlib.file_digest(file, 'sha256').hexdigest()


def read(path): return json.loads(Path(path).read_text())


def save(path, row): Path(path).write_text(json.dumps(row, indent=2, allow_nan=False) + '\n')


def preflight():
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19 and
            set(os.sched_getaffinity(0)) <= set(range(8,16)) | set(range(24,32)), 'nice19/helper cores required')
    require(os.environ.get('OMP_NUM_THREADS') == '2', 'two helper threads required')
    require(shutil.disk_usage(HERE).free - 4*1024**2 >= 27_000_000_000, '27 GB floor after bounded fixture writes')
    require(not FIXTURES.exists() and not SCRATCH.exists() and not RECEIPT.exists(), 'fresh one-shot destinations required; no retry/overwrite')
    for name, digest in ANCHORS.items(): require(sha(PACKET / name) == digest, 'admitted receipt drift: ' + name)
    require(sha(HOST_BINARY) == HOST_SHA and sha(ENV_SOURCE) == ENV_SHA, 'admitted host executable/environment changed')
    build = read(PACKET / 'evidence/build-compile-only.json')
    plans = {row['target']: row for row in build['plans']}
    require(build['passed'] and build['device_executed'] is False and build['native_executed'] is False, 'compile-only proof')
    require(plans['host']['binary'] == str(HOST_BINARY) and plans['host']['binary_sha256'] == HOST_SHA
            and '-DOWN_RT_HOST_ONLY' in plans['host']['commands'][0] and plans['host']['commands'][0][0] == '/usr/bin/g++',
            'exact GNU host-only entry required')
    ready = read(PACKET / 'READY-FOR-DEVICE.json')
    require(ready['files_sha256'][str((PACKET / 'build/device/own-rt-iq3').relative_to(ROOT))] == DEVICE_SHA,
            'expected device engine differs from independently admitted READY')
    audit = read(PACKET / 'evidence/independent-device-result.json')
    require(audit['passed'] is True and audit['checks']['all_save_events_receipts_manifest_hashes_exact'] is True
            and audit['checks']['all_five_checkpoint_blobs_verified'] is True, 'independent device checkpoint audit missing')
    expected = None
    for checkpoint_id, digest in MANIFESTS.items():
        manifest_path = DEVICE_ROOT / checkpoint_id / 'manifest.json'
        require(audit['checkpoint_files'][checkpoint_id]['manifest_sha256'] == digest and sha(manifest_path) == digest,
                'fixed independently audited manifest differs: ' + checkpoint_id)
        # Identity comes only after matching a pre-admitted manifest SHA and the
        # independently sealed binary. It is not trusted because a checkpoint says so.
        manifest = read(manifest_path)
        require(manifest['engine']['binary_sha256'] == DEVICE_SHA and manifest['contract'] == 'v1.2+p198'
                and manifest['label'] == 'experimental-postreply-front', 'admitted device identity mismatch')
        identity = {key: manifest[key] for key in IDENTITY_FIELDS}
        if expected is None: expected = identity
        else: require(expected == identity, 'audited s1/s3 identities differ')
    host = read(PACKET / 'evidence/host-probe.json')
    host_s1 = Path(host['lifecycle']['run_directory']) / 'checkpoints/s1'
    require(host_s1.is_relative_to(PACKET / 'build') and sha(host_s1 / 'manifest.json') == HOST_S1_SHA, 'fixed tiny host fixture changed')
    env_spec = importlib.util.spec_from_file_location('store_probe_closed_environment', ENV_SOURCE)
    module = importlib.util.module_from_spec(env_spec); env_spec.loader.exec_module(module)
    environment = module.environment()
    require(set(environment) == {'PATH','OMP_NUM_THREADS','LD_LIBRARY_PATH'}, 'closed loader environment')
    return expected, host_s1, environment, audit


def run_probe(expected, host_s1, environment, audit):
    FIXTURES.mkdir(); (FIXTURES / 'tool-calls').mkdir()
    SCRATCH.mkdir(parents=True); scratch_root = SCRATCH / 'checkpoints'; scratch_root.mkdir()
    calls = []
    allowed = [('--checkpoint-inspect-metadata', DEVICE_ROOT / 's1'),
               ('--checkpoint-inspect-metadata', DEVICE_ROOT / 's3'),
               ('--checkpoint-inspect-metadata', scratch_root / 's1'),
               ('--checkpoint-delete', scratch_root / 's1'),
               ('--checkpoint-delete', scratch_root / 's1')]
    def runner(argv, **kwargs):
        index = len(calls)
        require(index < len(allowed) and argv == [str(HOST_BINARY), allowed[index][0], str(allowed[index][1])],
                'unregistered native tool invocation refused')
        require(kwargs['env'] == environment and kwargs['timeout'] == 15 and kwargs['stdin'] == subprocess.DEVNULL,
                'native tool launch bounds/environment changed')
        require(kwargs['executable'].startswith('/proc/self/fd/') and len(kwargs['pass_fds']) == 1,
                'verified executable descriptor required')
        result = subprocess.run(argv, **kwargs)
        out = FIXTURES / 'tool-calls' / (str(index) + '.stdout.json')
        err = FIXTURES / 'tool-calls' / (str(index) + '.stderr.log')
        out.write_bytes(result.stdout); err.write_bytes(result.stderr)
        calls.append(dict(argv=argv, returncode=result.returncode, stdout=str(out.relative_to(ROOT)), stdout_sha256=sha(out),
                          stderr=str(err.relative_to(ROOT)), stderr_sha256=sha(err), mode='native CPU metadata tool only'))
        return result
    record = dict(passed=False, device_executed=False, model_executed=False, native_cpu_tools_executed=False,
                  native_model_owners_started=0, calls=calls, original_checkpoints_deleted=False)
    try:
        save(FIXTURES / 'admitted-engine-identity.json', expected)
        snapshots = {}
        with NativeCheckpointStore(DEVICE_ROOT, HOST_BINARY, HOST_SHA, environment, runner=runner) as store:
            for checkpoint_id in ('s1','s3'):
                snapshot = store.snapshot(checkpoint_id)
                require(snapshot is not None, 'admitted checkpoint disappeared')
                view = validate_snapshot(**snapshot.bridge_arguments(), expected_identity=expected, admitted_contract='v1.2+p198')
                require(view.manifest_sha256 == MANIFESTS[checkpoint_id] and view.native_inspect_mode == 'metadata', 'bridge snapshot identity')
                manifest = json.loads(snapshot.manifest_bytes)
                expected_bin_bytes = sum(row['bytes'] for row in manifest['blobs']) + len(snapshot.tokens_bytes)
                require(expected_bin_bytes == audit['checkpoint_files'][checkpoint_id]['total_bin_bytes'], 'audited binary payload extent')
                expected_storage = expected_bin_bytes + len(snapshot.manifest_bytes) + (DEVICE_ROOT / checkpoint_id / 'fields.tsv').stat().st_size
                require(snapshot.storage_bytes == expected_storage, 'complete logical storage accounting')
                (FIXTURES / (checkpoint_id + '.manifest.json')).write_bytes(snapshot.manifest_bytes)
                (FIXTURES / (checkpoint_id + '.inspect.json')).write_bytes(snapshot.inspect_stdout)
                (FIXTURES / (checkpoint_id + '.inspect.stderr.log')).write_bytes(snapshot.inspect_stderr)
                save(FIXTURES / (checkpoint_id + '.small-payloads.json'),
                     {'tokens.bin': snapshot.tokens_bytes.hex(), 'next_token.bin': snapshot.next_token_bytes.hex()})
                snapshots[checkpoint_id] = dict(manifest_sha256=view.manifest_sha256, storage_bytes=snapshot.storage_bytes,
                    processed_tokens=len(view.processed_tokens), pending_token=view.pending_token, inspect_returncode=snapshot.inspect_returncode,
                    native_inspect_mode=view.native_inspect_mode, full_state_revalidated_by_probe=False,
                    source_directory=str(DEVICE_ROOT / checkpoint_id))
        # Tiny host checkpoint copy only; each copied file is bound by the fixed
        # previously audited host artifact manifest. Source files are never changed.
        inventory = read(PACKET / 'evidence/host-probe-artifacts.json')['files_sha256']
        target = scratch_root / 's1'; target.mkdir()
        copied = {}
        for source in sorted(host_s1.iterdir()):
            require(source.is_file() and not source.is_symlink(), 'tiny checkpoint must be a closed regular file set')
            relative = str(source.relative_to(ROOT))
            require(relative in inventory and sha(source) == inventory[relative], 'original host fixture drift')
            shutil.copyfile(source, target / source.name)
            require(sha(target / source.name) == inventory[relative], 'scratch copy differs')
            copied[source.name] = inventory[relative]
        with NativeCheckpointStore(scratch_root, HOST_BINARY, HOST_SHA, environment, runner=runner) as store:
            tiny = store.snapshot('s1')
            require(tiny is not None and tiny.storage_bytes == sum(path.stat().st_size for path in target.iterdir()), 'tiny copied storage accounting')
            with store._shared_lock('s1'):  # Exercise the same outer lock against the actual native exclusive delete.
                require(store.delete('s1') == 'in_use', 'native delete ignored shared snapshot lock')
            require(all(sha(target / name) == digest for name,digest in copied.items()), 'in-use delete changed files')
            require(store.delete('s1') == 'ok' and not target.exists(), 'native scratch deletion failed')
            calls_before_missing = len(calls)
            require(store.delete('s1') == 'missing' and len(calls) == calls_before_missing, 'missing must be proven without another native call')
        require(len(calls) == 5 and [row['returncode'] for row in calls] == [0,0,0,1,0], 'unexpected native tool call count/results')
        for checkpoint_id, digest in MANIFESTS.items():
            require(sha(DEVICE_ROOT / checkpoint_id / 'manifest.json') == digest, 'original device metadata changed')
        require(all(sha(host_s1 / name) == digest for name,digest in copied.items()), 'original host checkpoint changed')
        record.update(passed=True, native_cpu_tools_executed=True, snapshots=snapshots,
                      delete_statuses=['in_use','ok','missing'], original_host_files_unchanged=True,
                      scratch_root=str(scratch_root), copied_files_sha256=copied)
        files = {str(path.relative_to(FIXTURES)): sha(path) for path in sorted(FIXTURES.rglob('*')) if path.is_file()}
        provenance = dict(schema='packet198.native-store-metadata-fixtures.v1', passed=True, device_executed=False,
            host_tool_binary=str(HOST_BINARY), host_tool_binary_sha256=HOST_SHA, admitted_device_binary_sha256=DEVICE_SHA,
            admission_receipts={str((PACKET/name).relative_to(ROOT)):digest for name,digest in ANCHORS.items()},
            source_manifest_sha256=MANIFESTS, identity_source='s1 manifest accepted only after its independently audited fixed SHA and READY engine check',
            snapshots=snapshots, files_sha256=files, native_tool_calls=calls,
            scope='Actual CPU metadata inspect + exact small bytes + bridge; stat extents/accounting only for large blobs. No new full tensor hashing or device execution.')
        save(FIXTURES / 'provenance.json', provenance)
        record['fixture_provenance_sha256'] = sha(FIXTURES / 'provenance.json')
    except BaseException as error:
        record.update(error=str(error), native_cpu_tools_executed=bool(calls))
        raise
    finally:
        record['sources_sha256'] = {str(path.relative_to(ROOT)): sha(path) for path in
            (Path(__file__), HERE/'native_checkpoint_store.py', HERE/'checkpoint_bridge.py')}
        save(RECEIPT, record)
    return record


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run-cpu-tools', action='store_true')
    args = ap.parse_args()
    expected, host_s1, environment, audit = preflight()
    if not args.run_cpu_tools:
        print(json.dumps(dict(passed=True, native_executed=False, device_executed=False, plan_only=True,
            host_binary=str(HOST_BINARY), host_binary_sha256=HOST_SHA,
            snapshot_sources=[str(DEVICE_ROOT/name) for name in ('s1','s3')],
            copy_source=str(host_s1), delete_target=str(SCRATCH/'checkpoints/s1'),
            native_modes=['--checkpoint-inspect-metadata','--checkpoint-delete'], native_call_count=5,
            fixtures=str(FIXTURES), receipt=str(RECEIPT), original_inputs_read_only=True,
            proposed_command=['/usr/bin/nice','-n','19','/usr/bin/taskset','-c','8-15,24-31','/usr/bin/env',
                'OMP_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2','/usr/bin/python3','-B',str(Path(__file__).resolve()),'--run-cpu-tools'])))
        return
    result = run_probe(expected, host_s1, environment, audit)
    print(json.dumps(dict(passed=result['passed'], device_executed=False, native_cpu_tool_calls=len(result['calls']),
                         fixtures=str(FIXTURES), receipt=str(RECEIPT))))


if __name__ == '__main__': main()
