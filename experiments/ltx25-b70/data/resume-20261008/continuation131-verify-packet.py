#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Read-only recursive verification of sealed131 and its authored components."""
import importlib.util
import json
from pathlib import Path

LANE = Path(__file__).resolve().parents[2]
AUTHOR = LANE / 'recovery/20261010-continuation131-stream'
OUT = Path(__file__).resolve().parent / 'continuation131-tests'
spec = importlib.util.spec_from_file_location('verify131', AUTHOR/'runtime_packet.py')
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)
seal = json.loads((OUT/'seal.json').read_text())
manifest = rp.verify_packet(rp.PACKET, seal['manifest_sha256'])
plan = json.loads((rp.PACKET/'resolution/stream-plan.json').read_text())
assert not list(rp.PACKET.rglob('__pycache__')) + list(rp.PACKET.rglob('*.pyc'))
for name in rp.COMPONENTS:
    assert rp.sha(AUTHOR/name) == rp.sha(rp.PACKET/'resolution/components'/name), name
result = dict(status='source-closure-verified', recursive_parent_verification=True,
    manifest_sha256=seal['manifest_sha256'], plan_sha256=plan['plan_sha256'],
    bound_files=len(manifest['files']), physical_files=sum(p.is_file() for p in rp.PACKET.rglob('*')),
    pycache_count=0, pyc_count=0, author_components_match=True, model_requests=0)
(OUT/'recursive-verification.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
