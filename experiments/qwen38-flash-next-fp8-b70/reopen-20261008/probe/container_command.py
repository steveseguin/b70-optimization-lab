#!/usr/bin/env python3
"""Print only. Never calls Docker, opens a device, or creates output directories."""
import argparse
import json
from pathlib import Path
import re
import shlex

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
CONF = 'pinned_max_round_threshold_mb:1,pinned_max_cached_size_mb:1'


def command(render_node, health, receipt_dir, direct=False):
    if not re.fullmatch(r'/dev/dri/by-path/pci-0000:(23|27|43|47):00\.0-render', render_node):
        raise ValueError('select one four-card-host by-path render node')
    health = Path(health).absolute()
    receipt_dir = Path(receipt_dir).absolute()
    if any(',' in str(p) or '\n' in str(p) for p in (HERE, PACKAGE, health, receipt_dir)):
        raise ValueError('Docker mount paths may not contain comma/newline')
    cmd = ['docker', 'run', '--rm', '--pull=never', '--restart=no', '--network=none',
           '--device=' + render_node + ':/dev/dri/renderD128:rw',
           '--security-opt=seccomp=unconfined', '--stop-signal=SIGINT',
           '--entrypoint=/opt/venv/bin/python', '-w', '/opt/venv']
    env = {'NEOReadDebugKeys': '1', 'EnableDeferBacking': '0',
           **{k: CONF for k in ('PYTORCH_ALLOC_CONF', 'PYTORCH_CUDA_ALLOC_CONF', 'PYTORCH_HIP_ALLOC_CONF')},
           'ZE_AFFINITY_MASK': '0', 'ZE_FLAT_DEVICE_HIERARCHY': 'FLAT',
           'VLLM_TARGET_DEVICE': 'xpu', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
           'HF_DATASETS_OFFLINE': '1', 'HF_HOME': '/receipts/cache/hf',
           'TRITON_CACHE_DIR': '/receipts/cache/triton', 'VLLM_CACHE_ROOT': '/receipts/cache/vllm',
           'XDG_CACHE_HOME': '/receipts/cache/xdg', 'PYTHONDONTWRITEBYTECODE': '1',
           'OMP_NUM_THREADS': '1', 'FLASHNEXT_PROBE_PACKAGE': '/screen-package',
           'FLASHNEXT_PROBE_ADMIT': '1'}
    for key, value in env.items():
        cmd += ['-e', key + '=' + value]
    for source, target, readonly in ((HERE, '/probe', True), (PACKAGE, '/screen-package', True),
                                    (health, '/health.json', True), (receipt_dir, '/receipts', False)):
        cmd += ['--mount', f'type=bind,src={source},dst={target}' + (',readonly' if readonly else '')]
    image = json.loads((PACKAGE / 'image-plan.json').read_text())['image']
    cmd += [image, '-B', '/probe/single_rank_slab_probe.py', '--health-receipt', '/health.json',
            '--receipt-dir', '/receipts']
    if direct:
        cmd += ['--direct-host-pointer']
    return cmd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render-node', required=True)
    parser.add_argument('--health-receipt', required=True)
    parser.add_argument('--receipt-dir', required=True)
    parser.add_argument('--direct-host-pointer', action='store_true')
    args = parser.parse_args()
    print(shlex.join(command(args.render_node, args.health_receipt, args.receipt_dir,
                             args.direct_host_pointer)))


if __name__ == '__main__':
    main()
