#!/usr/bin/env python3
"""Extract and hash the built control without starting a container or GPU code."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--kernel-reuse-receipt', required=True, type=Path)
    args = parser.parse_args()
    recipe = Path(__file__).resolve().parent
    args.output.mkdir(parents=True, exist_ok=False)
    info = json.loads(subprocess.check_output(['docker', 'image', 'inspect', args.image]))[0]
    assert 'VLLM_USE_V2_MODEL_RUNNER=0' in info['Config']['Env']
    base = json.loads(subprocess.check_output(['docker', 'image', 'inspect',
        'vllm/vllm-openai-xpu@sha256:28915aadfe9665dd70f1cf36e6f7362e25df24e9035785dedd00559652bbef41']))[0]
    reuse = json.loads(args.kernel_reuse_receipt.read_text())
    assert reuse['torch_and_native_dependency_hashes_equal'] is True
    assert reuse['identities']['new_base']['image_id'] == base['Id']
    expected = [line.split() for line in (recipe/'candidate-python.sha256').read_text().splitlines()]
    actual = {}
    helpers = ['vllm/v1/attention/backend.py', 'vllm/v1/attention/backends/utils.py',
        'vllm/third_party/flash_linear_attention/ops/index.py', 'vllm/third_party/flash_linear_attention/ops/utils.py']
    helper_hashes = {}
    container = subprocess.check_output(['docker', 'create', '--entrypoint', '/bin/true', info['Id']], text=True).strip()
    try:
        for wanted, relative in expected:
            target = args.output/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['docker', 'cp', f'{container}:/opt/venv/lib/python3.12/site-packages/{relative}', str(target)], check=True)
            digest = sha(target)
            assert digest == wanted, (relative, wanted, digest)
            actual[relative] = digest
        for relative in helpers:
            target = args.output/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['docker', 'cp', f'{container}:/opt/venv/lib/python3.12/site-packages/{relative}', str(target)], check=True)
            helper_hashes[relative] = sha(target)
    finally:
        subprocess.run(['docker', 'rm', container], check=True)
    result = {
        'schema': 'neural.download.mtp-control-source-identity.v1',
        'recorded_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'source-verified-runtime-unqualified',
        'image_id': info['Id'], 'image_created': info['Created'],
        'base_image_id': base['Id'], 'base_image_created': base['Created'],
        'upstream_commit': 'dc36fcce902a63eab06c1b93a5c4a5ee178a0c56',
        'runtime_versions': {'torch': '2.13.0+xpu', 'vllm': '0.29.1rc1.dev47+gdc36fcce9', 'vllm_xpu_kernels': '0.1.14.1'},
        'runner': 'V1', 'speculative_method_intent': 'native-MTP',
        'image_environment': info['Config']['Env'],
        'installed_python_sha256': actual, 'metadata_helper_sha256': helper_hashes,
        'kernel_reuse_receipt_sha256': sha(args.kernel_reuse_receipt),
        'native_kernel_sha256': reuse['kernel_artifact_sha256'],
        'recipe_sha256': {p.name: sha(p) for p in sorted(recipe.iterdir()) if p.is_file()},
        'gpu_access': False, 'container_started_for_extraction': False,
        'quality_and_performance_measured': False,
    }
    (args.output/'identity.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({'image_id': info['Id'], 'python_files_matched': len(actual), 'identity': str(args.output/'identity.json')}, indent=2))


if __name__ == '__main__':
    main()
