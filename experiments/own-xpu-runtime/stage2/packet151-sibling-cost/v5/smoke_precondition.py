"""Resolve the current proposal and validate its completed, pinned smoke."""
from pathlib import Path
from common import HERE, ROOT, read, require, sha
from p151_v5_compare import load


def checked_smoke(variant, lane, proposal=None):
    proposal = proposal or ROOT / 'experiments/own-xpu-runtime/ops/lane-queue' / ('proposed-p151-smoke-' + lane + '.txt')
    job = read(proposal)
    argv = job['argv']
    def option(name):
        require(argv.count(name) == 1, 'missing/ambiguous smoke option: ' + name)
        return argv[argv.index(name) + 1]
    require(job['lane'] == lane and option('--lane') == lane and
            option('--kind') == 'smoke' and option('--variant') == variant,
            'smoke proposal identity differs')
    output = Path(option('--output'))
    if not output.is_absolute():
        output = ROOT / output
    output = output.resolve(strict=True)
    pin = read(HERE / 'smoke-precondition.json')
    require(str(output) == pin['output'] and sha(output / 'window.json') == pin['window_sha256'],
            'smoke is not the qualified completed window')
    # Preserve the measured wrapper identity across this Python-only reseal.
    prior = HERE.parent / 'lineage-inputs/p151e-before/cpu-seal.json'
    require(sha(prior) == pin['wrapper_seal_sha256'], 'smoke wrapper pin changed')
    identity = read(output / 'identity.json')
    require(identity['lane'] == lane and Path(identity['lineage']) == HERE / 'lineage' / variant,
            'smoke lane/variant differs')
    for key, path in (
            ('binary_sha256', HERE / 'build/device/own-rt-iq3'),
            ('selection_sha256', HERE / 'lineage' / variant / 'selection.json'),
            ('dispatch_sha256', HERE / 'lineage' / variant / 'dispatch-speed6.json'),
            ('memory_plan_sha256', HERE / 'lineage' / variant / 'memory-plan.json'),
            ('bracket_config_sha256', HERE / 'configs' / (variant + '-smoke.json'))):
        require(identity[key] == sha(path), 'smoke runtime identity changed: ' + key)
    result = load(output, wrapper_seal_sha256=pin['wrapper_seal_sha256'])
    require(result.get('kind') == 'smoke' and result.get('passed') is True and
            result.get('request_count') == 12 and result.get('max_new') == 64,
            'exact matching 12x64 smoke required')
    return result
