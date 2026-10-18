"""CPU-only imports and identity checks for diagnostic screens."""
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
VENDOR = HERE.parent / 'lineage-inputs/vendor/repo/experiments/own-xpu-runtime/stage2'
P56 = VENDOR / 'packet56-draft-prefix'
P58 = VENDOR / 'packet58-onecard'
ARITHMETIC = 'iq3-p49-split32-v1'
# Packet56's seal predates dispatch-speed6.json in its source closure. This is
# the exact retained SPEED6/packet56 production dispatch, not an arbitrary map.
P56_DISPATCH_SHA256 = '477f62ec5cea61624047267ff69d74580c153ef40afe8558822dedb544018612'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


# These imports perform no device discovery, launches or journal reads.
M = module('screen_memory', P58 / 'memory_plan.py')
sys.modules['memory_plan'] = M
W = module('screen_safety', P58 / 'window.py')
S, SUPPORT = W.S, W.SUPPORT
D = module('screen_oracle', P58 / 'suite_driver.py')
METRICS = D.METRICS
DISPATCH = module('screen_dispatch', P56 / 'merge_dispatch.py')
require, sha, save = S.require, S.sha, S.save


def read(path):
    return json.loads(Path(path).read_text())


def verify_map(root, entries):
    require(isinstance(entries, dict) and entries, 'missing sealed file closure')
    for name, digest in entries.items():
        path = W.safe_path(root, name)
        require(sha(path) == digest, 'sealed file changed: ' + name)


def sealed(args):
    """Check existing receipts, never regenerate them or rerun CPU campaigns."""
    root = args.lineage.resolve()
    if root.parent == HERE / 'lineage':
        from bracket_config import sealed_identity
        return sealed_identity(args)
    receipt = (args.seal or root / 'build-receipt.json').resolve()
    row = read(receipt)
    require(row.get('passed') is True and row.get('device_executed') is False,
            'a completed CPU seal is required')
    require(row.get('arithmetic') == ARITHMETIC, 'wrong arithmetic lineage')
    verify_map(ROOT, row.get('sources'))
    modern = 'artifacts' in row
    artifacts = row.get('artifacts' if modern else 'artifacts_sha256', {})
    artifact_root = root if modern else root / 'build'
    binary = (args.binary or root / 'build/device/own-rt-iq3').resolve()
    key = str(binary.relative_to(artifact_root.resolve()))
    require(artifacts.get(key) == sha(binary), 'binary not bound to CPU seal')
    gates = row.get('gates' if modern else 'gates_sha256')
    verify_map(root, gates)
    for name in gates:
        gate = read(root / name)
        require(gate.get('passed') is True and gate.get('device_executed') is False,
                'failed/non-CPU gate in seal: ' + name)
    dispatch = (args.dispatch or root / 'dispatch-speed6.json').resolve()
    DISPATCH.validate(DISPATCH.read(dispatch))
    selection = root / 'selection.json'
    memory = root / 'memory-plan.json'
    # These control runtime arithmetic and allocation, and must be source-bound.
    for path in (selection, memory):
        key = str(path.relative_to(ROOT))
        if path == memory and not modern:
            require(read(path) == row.get('memory_plan'), 'memory plan changed')
        elif path == selection and row.get('schema') == 'packet57.diagnostic-cpu-seal.v1':
            require(row.get('selection', {}).get('selection_sha256') == sha(path), 'packet57 selection changed')
        else:
            require(row['sources'].get(key) == sha(path), 'unsealed runtime configuration: ' + key)
    if row.get('schema') == 'own-runtime.screen.cpu-seal.v1':
        require(row.get('profile') == args.profile, 'seal profile differs')
        require(row['sources'].get(str(dispatch.relative_to(ROOT))) == sha(dispatch), 'dispatch not sealed')
        verify_map(root, row.get('fixture_files'))
    elif args.profile == 'onecard':
        require(row.get('schema') == 'own-runtime.packet58.build.v1', 'onecard needs packet58 ABI or screen seal')
        require(row['sources'].get(str(dispatch.relative_to(ROOT))) == sha(dispatch), 'dispatch not sealed')
    else:
        require(row.get('schema') in ('packet56.scoped-cpu-seal.v1', 'packet57.diagnostic-cpu-seal.v1'), 'tp2 needs packet56/57 ABI or screen seal')
        require(sha(dispatch) == P56_DISPATCH_SHA256, 'packet56 requires pinned production dispatch')
    if args.profile == 'onecard':
        require(read(memory) == M.plan(), 'onecard allocation budget changed; new safety profile required')
    timing_modes = ['token']
    if row.get('schema') == 'packet57.diagnostic-cpu-seal.v1':
        timing_modes.append('attribution')
    # Lean candidate seals may explicitly declare additional timing support.
    if row.get('schema') == 'own-runtime.screen.cpu-seal.v1':
        timing_modes = row.get('timing_modes', ['token'])
    require(args.timing in timing_modes, 'timing mode unsupported by sealed lineage')
    from p145_v5_placement import admit
    placement = admit(root, row, receipt, dispatch, getattr(args, 'placement', '1-split23'))
    return dict(placement=placement, timing=args.timing, timing_modes=timing_modes, lineage=str(root), seal=str(receipt), seal_sha256=sha(receipt),
                binary=str(binary), binary_sha256=sha(binary), dispatch=str(dispatch),
                dispatch_sha256=sha(dispatch), selection_sha256=sha(selection),
                memory_plan_sha256=sha(memory), profile=args.profile)


def compare_tokens(tokens, expected, count, prompt_id):
    require(len(expected) >= count and len(tokens) == count and tokens == expected[:count],
            'every-token oracle mismatch: ' + prompt_id)


def label(row):
    row.update(evidence_label='screen', diagnostic=True, qualifying=False,
               submission_eligible=False, speed_evidence_eligible=False,
               realistic_final_gate={'passed': False, 'reason': 'screen only; full sealed chain required'},
               prompt_kv_response_reuse=False)
    return row


def summary(rows, incident, profile):
    require(len(rows) == 12 and [r['prompt_id'] for r in rows] == list(D.CHECK.PROMPT_IDS),
            'screen requires all 12 prompts in registered order')
    require(incident.get('passed') is True and all(r.get('passed') is True for r in rows),
            'screen exactness failed')
    if all(len(r['tokens'])==64 for r in rows):
        return label(dict(passed=True,profile=profile,arithmetic=ARITHMETIC,context=4096,kv_dtype='BF16',gpu_count=2,incident64=incident,requests=rows,cached_tokens=0,requested_max_new=64,request_count=12,timing_status='smoke only; no speed verdict'))
    result = METRICS.aggregate(rows)
    # Keep numerical WS128 accounting; never export submission payload fields.
    result.pop('raw_payload_fields', None)
    result.update(schema='own-runtime.screen.summary.v3', passed=True, profile=profile,
                  arithmetic=ARITHMETIC, context=4096, kv_dtype='BF16',
                  gpu_count=2 if profile == 'tp2' else 1, incident64=incident,
                  requests=[label(r) for r in rows], retained_steps='none',
                  cached_tokens=0, requested_max_new=128, request_count=12)
    if profile == 'onecard':
        result['draft_metrics_status'] = 'not applicable: target-only; acceptance and hit/miss cycles are null'
    return label(result)
