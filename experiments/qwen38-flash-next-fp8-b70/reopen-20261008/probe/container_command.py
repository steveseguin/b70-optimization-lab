#!/usr/bin/env python3
"""Print only. Never calls Docker, opens a device, or creates output directories."""
import argparse
import hashlib
import json
from pathlib import Path
import os
import re
import shlex
from single_rank_slab_probe import add_exit_arguments, idle_seconds, lane

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
CONF = 'pinned_max_round_threshold_mb:1,pinned_max_cached_size_mb:1'


# Remedy A, notes/2026-10-09-runtime-comparison.md: ordered source, resolved
# image target, and inspected host SHA256. Never substitute package labels.
HOST_UMD_OVERLAY = (
    ('/usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1.15.38308',
     '/usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1.15.39122',
     '26fa68779adb03b200a8c3001cf81e59fc9a3d63e0f38627ec0005ffce574e7a'),
    ('/usr/lib/x86_64-linux-gnu/intel-opencl/libigdrcl.so',
     '/usr/lib/x86_64-linux-gnu/intel-opencl/libigdrcl.so',
     '0cfd5ba1211615558b2f8f3912451889949c0a75245a1f3fd5ee6dbf9fd338bf'),
    ('/usr/lib/x86_64-linux-gnu/libze_loader.so.1.28.2',
     '/usr/lib/x86_64-linux-gnu/libze_loader.so.1.32.0',
     '0fe232b18985ae078dd546b57bc6d11bacf1030834c0544f7e3feb53ed71c1d0'),
    ('/usr/lib/x86_64-linux-gnu/libze_tracing_layer.so.1.28.2',
     '/usr/lib/x86_64-linux-gnu/libze_tracing_layer.so.1.32.0',
     'ed9405ce2cd588f7ca78a777865de6d6e3d0d4776fd70b89c6e5ca4826fba59e'),
    ('/usr/lib/x86_64-linux-gnu/libze_validation_layer.so.1.28.2',
     '/usr/lib/x86_64-linux-gnu/libze_validation_layer.so.1.32.0',
     '50115b6679a89f4dfee36384fd7667a7f22f5e8d094d412da4fd86304397973c'),
    ('/usr/lib/x86_64-linux-gnu/libigdgmm.so.12.10.0',
     '/usr/lib/x86_64-linux-gnu/libigdgmm.so.12.10.0',
     '41892701dc8de4a9086653e1599c533f40e8e28baf435df27cab70ec2d0b9526'),
    ('/usr/local/lib/libigc.so.2.34.4+1778234987',
     '/usr/local/lib/libigc.so.2.38.2+1782393643',
     '5dbf0da8af02783b7770b9294485a034ce9756cf6bcdbed95d9a3b6d10f0674a'),
    ('/usr/local/lib/libigdfcl.so.2.34.4+1778234987',
     '/usr/local/lib/libigdfcl.so.2.38.2+1782393643',
     'f9b9db2bc681f44040f3c29fbd17de5ec1bb82dd92921a8022b992b0e02e50e5'),
    ('/usr/local/lib/libiga64.so.2.34.4+1778234987',
     '/usr/local/lib/libiga64.so.2.38.2+1782393643',
     '79adaf47e87ff5c6df0608b74fa71019e83f2c049b439e9ec59acca5d3457215'),
    ('/usr/local/lib/libopencl-clang2.so.16',
     '/usr/local/lib/libopencl-clang2.so.16',
     'bff108c0dc259768a574372e1d33e3101543da4f2453a47f4296152aa314519d'),
    ('/usr/lib/x86_64-linux-gnu/libz.so.1.3',
     '/usr/lib/x86_64-linux-gnu/libz.so.1.3',
     '86200da370f20476a2507e9097a789b5ef97269b4ca8d5e164ad82dab9d99892'),
    ('/usr/lib/x86_64-linux-gnu/libzstd.so.1.5.5',
     '/usr/lib/x86_64-linux-gnu/libzstd.so.1.5.5',
     '0a2128bc10841fb29e76d08d945864dfb0b6a66da5df6df5d8299197439e54bb'),
)


def host_umd_mounts():
    mounts = []
    for source, target, expected in HOST_UMD_OVERLAY:
        try:
            with Path(source).open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        except OSError as exc:
            raise ValueError('host UMD source missing or unreadable: ' + source) from exc
        if actual != expected:
            raise ValueError('host UMD SHA-256 mismatch: ' + source)
        mounts += ['--mount', f'type=bind,src={source},dst={target},readonly']
    return mounts


def command(render_node, health, receipt_dir, direct=False, host_umd_overlay=False,
            clean_exit=False, exit_after_sleep=None, owner_acceptance=None):
    if clean_exit and exit_after_sleep is not None:
        raise ValueError('--clean-exit and --exit-after-sleep are mutually exclusive')
    if exit_after_sleep is not None:
        exit_after_sleep = idle_seconds(exit_after_sleep)
    if not re.fullmatch(r'/dev/dri/by-path/pci-0000:(23|27|43|47):00\.0-render', render_node):
        raise ValueError('select one four-card-host by-path render node')
    # The lane's screen.py computes REPO = HERE.parents[2] at import (attempt 2 of 2026-10-09 refused with
    # IndexError at /screen-package), so the package is mounted at its repo-relative depth under /repo.
    # Docker splits --device on ':' and the by-path name contains two (attempt 1 of 2026-10-09 was
    # refused with "bad format for path"); pass the resolved renderD node and keep the by-path name in the env.
    resolved = os.path.realpath(render_node)
    if not re.fullmatch(r'/dev/dri/renderD\d+', resolved):
        raise ValueError('by-path render node does not resolve to /dev/dri/renderD*: ' + resolved)
    health = Path(health).absolute()
    receipt_dir = Path(receipt_dir).absolute()
    if any(',' in str(p) or '\n' in str(p) for p in (HERE, PACKAGE, health, receipt_dir)):
        raise ValueError('Docker mount paths may not contain comma/newline')
    cmd = ['docker', 'run', '--rm', '--pull=never', '--restart=no', '--network=none',
           '--device=' + resolved + ':/dev/dri/renderD128:rw',
           '--security-opt=seccomp=unconfined', '--stop-signal=SIGINT',
           '--entrypoint=/opt/venv/bin/python', '-w', '/opt/venv']
    env = {'FLASHNEXT_PROBE_RENDER_BYPATH': render_node, 'FLASHNEXT_PROBE_RENDER_NODE': resolved,
           'NEOReadDebugKeys': '1', 'EnableDeferBacking': '0',
           **{k: CONF for k in ('PYTORCH_ALLOC_CONF', 'PYTORCH_CUDA_ALLOC_CONF', 'PYTORCH_HIP_ALLOC_CONF')},
           'ZE_AFFINITY_MASK': '0', 'ZE_FLAT_DEVICE_HIERARCHY': 'FLAT',
           'VLLM_TARGET_DEVICE': 'xpu', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
           'HF_DATASETS_OFFLINE': '1', 'HF_HOME': '/receipts/cache/hf',
           'TRITON_CACHE_DIR': '/receipts/cache/triton', 'VLLM_CACHE_ROOT': '/receipts/cache/vllm',
           'XDG_CACHE_HOME': '/receipts/cache/xdg', 'PYTHONDONTWRITEBYTECODE': '1',
           'OMP_NUM_THREADS': '1', 'FLASHNEXT_PROBE_PACKAGE': '/repo/experiments/qwen38-flash-next-fp8-b70/reopen-20261008',
           'FLASHNEXT_PROBE_ADMIT': '1'}
    overlay_mounts = host_umd_mounts() if host_umd_overlay else []
    if host_umd_overlay:
        env['LD_LIBRARY_PATH'] = '/usr/local/lib:/opt/ucx/lib:/opt/venv/lib'
        env['FLASHNEXT_PROBE_UMD'] = 'host-26.18.38308'
    for key, value in env.items():
        cmd += ['-e', key + '=' + value]
    for source, target, readonly in ((HERE, '/probe', True), (PACKAGE, '/repo/experiments/qwen38-flash-next-fp8-b70/reopen-20261008', True),
                                    (health, '/health.json', True), (receipt_dir, '/receipts', False)):
        cmd += ['--mount', f'type=bind,src={source},dst={target}' + (',readonly' if readonly else '')]
    acceptance_target = None
    if owner_acceptance is not None:
        # Do not consult the journal or admit execution in this print-only tool.
        # Use the canonical repository-relative location in the container too.
        source = Path(owner_acceptance).resolve()
        screen = lane()
        if source != (screen.REPO / screen.OWNER_ACCEPTANCE_RELATIVE).resolve():
            raise ValueError('owner acceptance must be the committed receipt path')
        if not source.is_file():
            raise ValueError('owner acceptance must be a regular receipt file')
        if hashlib.sha256(source.read_bytes()).hexdigest() != screen.OWNER_ACCEPTANCE_SHA256:
            raise ValueError('owner acceptance SHA256 mismatch')
        acceptance_target = '/repo/' + str(screen.OWNER_ACCEPTANCE_RELATIVE)
        cmd += ['--mount', f'type=bind,src={source},dst={acceptance_target},readonly']
    cmd += overlay_mounts
    image = json.loads((PACKAGE / 'image-plan.json').read_text())['image']
    cmd += [image, '-B', '/probe/single_rank_slab_probe.py', '--health-receipt', '/health.json',
            '--receipt-dir', '/receipts']
    if acceptance_target is not None:
        cmd += ['--owner-acceptance', acceptance_target]
    if direct:
        cmd += ['--direct-host-pointer']
    if clean_exit:
        cmd += ['--clean-exit']
    if exit_after_sleep is not None:
        cmd += ['--exit-after-sleep', str(exit_after_sleep)]
    return cmd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render-node', required=True)
    parser.add_argument('--owner-acceptance')
    parser.add_argument('--health-receipt', required=True)
    parser.add_argument('--receipt-dir', required=True)
    parser.add_argument('--direct-host-pointer', action='store_true')
    parser.add_argument('--host-umd-overlay', action='store_true',
                        help='verify and bind the twelve pinned Remedy A host libraries read-only')
    add_exit_arguments(parser)
    args = parser.parse_args()
    print(shlex.join(command(args.render_node, args.health_receipt, args.receipt_dir,
                             args.direct_host_pointer, args.host_umd_overlay,
                             args.clean_exit, args.exit_after_sleep, args.owner_acceptance)))


if __name__ == '__main__':
    main()
