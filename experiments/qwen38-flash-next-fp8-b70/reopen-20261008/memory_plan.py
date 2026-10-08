#!/usr/bin/env python3
"""CPU-only Screen 1b tensor/lifetime admission. No torch or accelerator imports.

A numerical planning scenario is not a qualified bound. Unknown required phase
bounds remain null and REFUSE execution, even when a scenario happens to fit.
GB means 10**9 bytes; the vLLM cpu-offload-gb CLI uses GiB instead.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from decimal import Decimal
from placement_plan import storage_plan, enumerate_candidates
import hashlib
import json
import math
from pathlib import Path
import re
import struct

HERE = Path(__file__).resolve().parent
GIB = 1 << 30
MIB = 1 << 20
HOST_LIMIT = 90_000_000_000
VRAM_RESERVE = 4 * GIB
WATCHDOG_AVAILABLE = 32 * GIB
WATCHDOG_PRESSURE = 80_000_000_000
CHUNK_BYTES = 256 * MIB
DEFAULT_MODEL = Path('/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8')
DTYPE_BYTES = {'F64': 8, 'F32': 4, 'F16': 2, 'BF16': 2, 'I64': 8,
               'I32': 4, 'I16': 2, 'I8': 1, 'U8': 1, 'BOOL': 1,
               'F8_E4M3': 1, 'F8_E5M2': 1, 'F8_E4M3FN': 1}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _nonnegative(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f'{name} must be a known nonnegative integer byte count')
    return value


def host_phase(other_host, pins, private, copies, retained, active_files,
               driver, safety):
    """One owner per allocation: never add RSS/cgroup observations to pins."""
    lengths = {len(pins), len(private), len(copies), len(retained)}
    if len(lengths) != 1:
        raise ValueError('per-rank phase vectors have different lengths')
    values = [other_host, active_files, driver, safety, *pins, *private,
              *copies, *retained]
    return sum(_nonnegative(x, 'Hphase input') for x in values)


def gate_arithmetic(phases, vram_phases, physical, available=None,
                    remaining_growth=None, shutdown_margin=WATCHDOG_AVAILABLE):
    """Evaluate exactly Hpred=max(Hphase), Vpeak[r]=max(Vphase[r])."""
    reasons = []
    if not physical or any(len(values) != len(physical) for values in vram_phases.values()):
        raise ValueError('VRAM phase rank counts do not match physical capacity vector')
    if not phases or any(x is None for x in phases.values()):
        hpred = None
        reasons.append('required host phase bound unknown')
    else:
        hpred = max(_nonnegative(x, 'Hphase') for x in phases.values())
        if hpred > HOST_LIMIT:
            reasons.append(f'predicted host peak {hpred} exceeds {HOST_LIMIT} bytes')
    peaks, reserves = [], []
    for rank, capacity in enumerate(physical):
        values = [p[rank] for p in vram_phases.values()]
        if not values or capacity is None or any(x is None for x in values):
            peaks.append(None)
            reserves.append(None)
            reasons.append(f'rank {rank}: required VRAM phase/capacity bound unknown')
            continue
        peak = max(_nonnegative(x, 'Vphase') for x in values)
        reserve = _nonnegative(capacity, 'physical VRAM') - peak
        peaks.append(peak)
        reserves.append(reserve)
        if reserve < VRAM_RESERVE:
            reasons.append(f'rank {rank}: VRAM reserve {reserve} below {VRAM_RESERVE}')
    if available is None or remaining_growth is None:
        reasons.append('post-hash MemAvailable/remaining committed growth unknown')
    elif available < remaining_growth + shutdown_margin:
        reasons.append('post-hash MemAvailable cannot cover growth and shutdown margin')
    return {'host_peak_bytes': hpred, 'vram_peak_bytes_per_rank': peaks,
            'vram_reserve_bytes_per_rank': reserves, 'refusal_reasons': reasons}


def read_metadata(root):
    """Read config, index and bounded headers only; never seek tensor payloads."""
    root = Path(root)
    config_path = root / 'config.json'
    index_path = root / 'model.safetensors.index.json'
    config = json.loads(config_path.read_text())
    index = json.loads(index_path.read_text())
    tensors, header_pins = {}, {}
    total_header_bytes = 0
    for filename in sorted(set(index['weight_map'].values())):
        rel = Path(filename)
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError(f'unsafe safetensors index path: {filename}')
        path = root / rel
        with path.open('rb') as stream:
            length_bytes = stream.read(8)
            if len(length_bytes) != 8:
                raise ValueError(f'truncated header length: {filename}')
            length = struct.unpack('<Q', length_bytes)[0]
            if length > 32 * MIB:
                raise ValueError(f'header exceeds 32 MiB: {filename}')
            total_header_bytes += length
            if total_header_bytes > 256 * MIB:
                raise ValueError('aggregate safetensors headers exceed 256 MiB')
            raw = stream.read(length)
            if len(raw) != length:
                raise ValueError(f'truncated safetensors header: {filename}')
        header_pins[filename] = hashlib.sha256(length_bytes + raw).hexdigest()
        header = json.loads(raw)
        for name, info in header.items():
            if name == '__metadata__':
                continue
            if name in tensors or index['weight_map'].get(name) != filename:
                raise ValueError(f'duplicate/unindexed tensor: {name}')
            shape = info['shape']
            if any(type(x) is not int or x < 0 for x in shape):
                raise ValueError(f'invalid tensor shape: {name}')
            dtype = info['dtype']
            if dtype not in DTYPE_BYTES:
                raise ValueError(f'unknown dtype {dtype}: {name}')
            count = math.prod(shape) * DTYPE_BYTES[dtype]
            start, end = info['data_offsets']
            if start < 0 or end - start != count or end > path.stat().st_size - 8 - length:
                raise ValueError(f'invalid data offsets/shape: {name}')
            tensors[name] = {'shape': shape, 'dtype': dtype, 'bytes': count}
    if set(tensors) != set(index['weight_map']):
        raise ValueError('index/header tensor coverage mismatch')
    if sum(t['bytes'] for t in tensors.values()) != index['metadata']['total_size']:
        raise ValueError('index total_size/header byte count mismatch')
    return config, tensors, {'config_sha256': sha256(config_path),
                              'index_sha256': sha256(index_path),
                              'safetensors_header_sha256': header_pins,
                              'header_bytes_read': total_header_bytes}


def flag(command, name, default=None):
    for i, arg in enumerate(command):
        if arg == name:
            return command[i + 1]
        if arg.startswith(name + '='):
            return arg.split('=', 1)[1]
    return default


def launch_identity(command):
    tp = int(flag(command, '--tensor-parallel-size', '1'))
    if tp != 4 or '--enable-expert-parallel' not in command:
        raise ValueError('Screen 1b predictor is bound to TP4/EP4')
    if flag(command, '--offload-backend') != 'uva':
        raise ValueError('Screen 1b requires selective UVA offload')
    if flag(command, '--dtype') != 'bfloat16' or flag(command, '--kv-cache-dtype') not in ('auto', 'bfloat16'):
        raise ValueError('Screen 1b requires unchanged BF16-family KV and model dtype')
    budget = int(Decimal(flag(command, '--cpu-offload-gb')) * GIB)
    if not 12 * GIB <= budget <= 18 * GIB:
        raise ValueError('generic census is qualified only for 12..18 GiB/rank candidate budgets')
    if '--language-model-only' in command or '--enable-eplb' in command:
        raise ValueError('vision pruning or expert rebalancing requires a new allocation census')
    spec = json.loads(flag(command, '--speculative-config', '{}'))
    if spec and (spec.get('method') != 'mtp' or spec.get('num_speculative_tokens') not in (1, 3)):
        raise ValueError('unsupported speculative configuration')
    suffixes = []
    if '--cpu-offload-params' in command:
        start = command.index('--cpu-offload-params') + 1
        for arg in command[start:]:
            if arg.startswith('--'):
                break
            suffixes.append(arg)
    accepted = {'ple_embedding.ngram_embedding.weight', 'mlp.experts.w13_weight',
                'mlp.experts.w2_weight'}
    placement = next((x.split('=', 1)[1] for x in command if x.startswith('Q38_EXPERT_HOST_PLACEMENT=')), None)
    if placement:
        if placement != '/screen-package/placement-certified-v5.json':
            raise ValueError('unbound placement path')
        if set(suffixes) != {'ple_embedding.ngram_embedding.weight', 'embed_tokens.weight'} or budget != int(12.25*GIB):
            raise ValueError('v5 requires certified PLE/embedding budget and suffixes')
        if flag(command, '--gpu-memory-utilization') != '0.92':
            raise ValueError('v5 prediction requires certified utilization')
        graph = json.loads(flag(command, '--compilation-config'))
        if graph.get('mode') != 0 or graph.get('cudagraph_mode') != 'FULL_DECODE_ONLY':
            raise ValueError('v5 prediction requires compilation NONE / FULL_DECODE_ONLY')
    elif set(suffixes) != accepted:
        raise ValueError('registration census supports exactly PLE/w13/w2 suffixes')
    return {'tensor_parallel_size': tp, 'expert_parallel_size': tp,
            'cpu_offload_bytes_per_rank': budget,
            'offload_suffixes': suffixes,
            'placement': placement,
            'gpu_memory_utilization': flag(command, '--gpu-memory-utilization'),
            'compilation': json.loads(flag(command, '--compilation-config', '{}')),
            'max_model_len': int(flag(command, '--max-model-len')),
            'max_num_seqs': int(flag(command, '--max-num-seqs')),
            'max_num_batched_tokens': int(flag(command, '--max-num-batched-tokens')),
            'kv_bytes_per_rank': int(flag(command, '--kv-cache-memory-bytes')),
            'mtp_depth': spec.get('num_speculative_tokens', 0),
            'command_sha256': hashlib.sha256(json.dumps(command, separators=(',', ':')).encode()).hexdigest()}


def planned_parameters(config, tensors, tp):
    """V30 registration order: layer0 experts; layer1 PLE then experts.

    Only the three explicitly accepted suffixes are enumerated. Expert scales
    are device allocations, never selected by the whole-segment UVA matcher.
    """
    cfg = config['text_config']
    if cfg['num_experts'] % tp:
        raise ValueError('uneven EP partition unsupported')
    ple_parts = [(name, t) for name, t in tensors.items()
                 if 'ple_embedding.ngram_embedding' in name and len(t['shape']) == 2]
    if not ple_parts or any(t['dtype'] not in ('F8_E4M3', 'F8_E4M3FN') for _, t in ple_parts):
        raise ValueError('native FP8 PLE table headers missing/changed')
    width = cfg['ple_embed_dim'] // ((cfg['ngram_size'] - 1) * cfg['heads_per_ngram'])
    if any(t['shape'][1] != width for _, t in ple_parts):
        raise ValueError('PLE shape/config mismatch')
    rows = sum(t['shape'][0] for _, t in ple_parts)
    padding = cfg['make_ngram_vocab_size_divisible_by']
    padded = math.ceil(rows / padding) * padding
    if padded % tp:
        raise ValueError('PLE table does not shard evenly')
    ple = padded // tp * width
    local_experts = cfg['num_experts'] // tp
    h, intermediate = cfg['hidden_size'], cfg['moe_intermediate_size']
    w13 = local_experts * 2 * h * intermediate
    w2 = local_experts * h * intermediate
    parameters = []
    for layer in range(cfg['num_hidden_layers']):
        prefix = f'model.language_model.layers.{layer}'
        if layer + 1 in cfg['ple_layer_ids']:
            parameters.append({'name': prefix + '.ple.ple_embedding.ngram_embedding.weight',
                               'bytes': ple, 'kind': 'ple'})
        # Check actual checkpoint byte identities, including native FP8 dtype.
        for projection in ('gate_proj', 'up_proj', 'down_proj'):
            name = f'{prefix}.mlp.experts.0.{projection}.weight'
            t = tensors.get(name)
            if t is None or t['bytes'] != h * intermediate or t['dtype'] not in ('F8_E4M3', 'F8_E4M3FN'):
                raise ValueError(f'expert layout changed: {name}')
        parameters.extend(({'name': prefix + '.mlp.experts.w13_weight', 'bytes': w13, 'kind': 'experts'},
                           {'name': prefix + '.mlp.experts.w2_weight', 'bytes': w2, 'kind': 'experts'}))
    return parameters


def select_offload(parameters, budget):
    """Match V30's budget-before-parameter check, including final overshoot."""
    selected, count = [], 0
    for parameter in parameters:
        if count >= budget:
            break
        selected.append(parameter)
        count += parameter['bytes']
    return selected, count


def pressure_sample(meminfo):
    fields = dict(re.findall(r'^(\w+):\s+(\d+) kB', meminfo, re.M))
    total, available = int(fields['MemTotal']) * 1024, int(fields['MemAvailable']) * 1024
    return {'mem_total_bytes': total, 'mem_available_bytes': available,
            'accounted_pressure_bytes': total - available}


def collect_observations(proc_root=Path('/proc'), cgroup_root=Path('/sys/fs/cgroup')):
    """Read only this controller's accessible CPU accounting; never sudo.

    Capture before and after hashing. Container/worker observations belong to
    subsequent qualification, not this prelaunch snapshot. Inaccessible files
    remain explicit errors. Numbers are observations, not allocations to add.
    """
    proc_root, cgroup_root = Path(proc_root), Path(cgroup_root)
    result = {'errors': [], 'process': {}, 'cgroup': {}}
    def read(path):
        try:
            return path.read_text()
        except (OSError, UnicodeError) as exc:
            result['errors'].append(f'{path}: {type(exc).__name__}')
            return None
    raw = read(proc_root / 'meminfo')
    if raw is not None:
        result['meminfo'] = raw
        try:
            result.update(pressure_sample(raw))
        except (KeyError, ValueError):
            result['errors'].append('missing/invalid MemTotal or MemAvailable')
    for name in ('status', 'smaps_rollup', 'stat'):
        result['process'][name] = read(proc_root / 'self' / name)
    membership = read(proc_root / 'self' / 'cgroup')
    if membership is not None:
        unified = [line.split(':', 2)[2] for line in membership.splitlines()
                   if line.startswith('0::')]
        if len(unified) != 1 or '..' in Path(unified[0]).parts:
            result['errors'].append('unified cgroup membership unavailable/unsafe')
        else:
            cg = cgroup_root / unified[0].lstrip('/')
            result['cgroup']['path'] = str(cg)
            for name in ('memory.current', 'memory.peak', 'memory.stat', 'memory.events'):
                result['cgroup'][name] = read(cg / name)
    result['snapshot_complete'] = not result['errors']
    return result


def paired_observations(before, after):
    return {'before_hash': before, 'after_hash': after,
            'post_hash_mem_available_bytes': after.get('mem_available_bytes'),
            'required_observations_complete': bool(before.get('snapshot_complete')
                                                   and after.get('snapshot_complete'))}


def should_stop(sample, next_allocation_bytes=0):
    return (sample['mem_available_bytes'] - next_allocation_bytes <= WATCHDOG_AVAILABLE
            or sample['accounted_pressure_bytes'] + next_allocation_bytes >= WATCHDOG_PRESSURE)


def build_prediction(command, model_root=DEFAULT_MODEL, bounds_path=None, observations=None):
    """Build prediction; persisted bounds are source-bound and fail closed."""
    bounds_path = Path(bounds_path or HERE / 'memory-bounds.json')
    bound = json.loads(bounds_path.read_text())
    config, tensors, metadata = read_metadata(model_root)
    identity = launch_identity([str(x) for x in command])
    tp = identity['tensor_parallel_size']
    parameters = planned_parameters(config, tensors, tp)
    selected, pins_per_rank = select_offload(parameters, identity['cpu_offload_bytes_per_rank'])
    rank_pins = [pins_per_rank] * tp
    placement_census = None
    if identity.get('placement'):
        placement_path = HERE / 'placement-certified-v5.json'
        if sha256(placement_path) != bound['placement_sha256']:
            raise ValueError('placement identity drift')
        placement_census = storage_plan(config, tensors, json.loads(placement_path.read_text()))
        rank_pins = [r['pinned_bytes'] for r in placement_census]
        selected = [{'name': b['name'], 'bytes': b['bytes'], 'kind': 'v5-final'}
                    for b in placement_census[0]['buffers']]
    pins = sum(rank_pins)
    # Count only unambiguously loaded weight tensors for the LOWER bound.
    # Exclude biases, buffers and every scale (even device-resident scales),
    # avoiding assumptions about ignored optional checkpoint suffixes.
    weight_names = [n for n in tensors if n.endswith('.weight')
                    and not any(skip in n for skip in ('hashstats_', 'token_lookup',
                                                       'hyper_connection_mixer.block_inject_weight'))
                    and (identity['mtp_depth'] or not n.startswith('mtp.'))]
    total_weights = sum(tensors[n]['bytes'] for n in weight_names)
    if config['text_config'].get('mtp_use_dedicated_embeddings', True):
        raise ValueError('MTP shared-embedding alias assumption changed')
    if any(n.startswith(('mtp.embed_tokens.', 'mtp.shared_head.')) for n in tensors):
        raise ValueError('unexpected dedicated MTP embedding/head requires alias census')
    # A LOWER bound only: all tensors optimistically TP-sharded except the
    # source-proven replicated HC matrices. Includes vision and draft bytes,
    # counts shared target embedding/head once. Biases/scales/buffers are omitted
    # deliberately from the lower bound; complete Vpeak remains unknown.
    replicated = sum(t['bytes'] for n, t in tensors.items()
                     if n.endswith(('input_mix_weight_up.weight', 'input_mix_weight_down.weight'))
                     and (identity['mtp_depth'] or not n.startswith('mtp.')))
    floors = [math.ceil((total_weights + replicated * (tp - 1)) / tp) - pin + identity['kv_bytes_per_rank'] for pin in rank_pins]
    scenario = bound['illustrative_assumptions']
    overhead = sum(scenario[k] for k in ('private_runtime_and_retention_bytes', 'active_files_bytes', 'other_host_and_driver_bytes'))
    illustration = pins + overhead + CHUNK_BYTES
    refusal = []
    if metadata['config_sha256'] != bound['model_config_sha256'] or metadata['index_sha256'] != bound['model_index_sha256']:
        refusal.append('model config/index identity differs from phase manifest')
    overlay_manifest = HERE / 'overlay-manifest.json'
    overlay_identity = sha256(overlay_manifest)
    if bound.get('qualified', False) and bound.get('qualified_overlay_manifest_sha256') != overlay_identity:
        refusal.append('qualified phase bound does not match overlay manifest identity')
    source_root = Path(bound['source_root'])
    for rel, digest in bound['source_sha256'].items():
        try:
            if sha256(source_root / rel) != digest:
                refusal.append(f'source drift: {rel}')
        except OSError:
            refusal.append(f'missing source identity: {rel}')
    phases = {}
    vram_phases = {}
    required = ('construction', 'pinning', 'checkpoint_copy', 'postprocessing',
                'mtp_load', 'kv_allocation', 'compilation_capture', 'serving')
    for phase in required:
        row = bound['phases'].get(phase)
        if row is None or any(row.get(k) is None for k in ('other_host', 'private_per_rank', 'copies_per_rank', 'retained_per_rank', 'active_files', 'driver', 'safety')):
            phases[phase] = None
        else:
            phases[phase] = host_phase(row['other_host'], rank_pins,
                                       row['private_per_rank'], row['copies_per_rank'],
                                       row['retained_per_rank'], row['active_files'], row['driver'], row['safety'])
        vram_phases[phase] = (row or {}).get('vram_peak_per_rank') or [None] * tp
    observed = observations or {}
    result = gate_arithmetic(phases, vram_phases, bound['physical_vram_bytes_per_rank'],
                             observed.get('post_hash_mem_available_bytes'),
                             bound.get('remaining_committed_growth_bytes'))
    refusal.extend(result.pop('refusal_reasons'))
    if bound.get('qualified', False) and bound.get('qualified_launch_sha256') != identity['command_sha256']:
        refusal.append('qualified bound does not match exact launch flags/environment')
    if not bound.get('qualified', False):
        refusal.append('runtime retention/workspace/lifetime bounds are unqualified; scenario is not admission evidence')
    if not observed.get('required_observations_complete', False):
        refusal.append('required pre/post-hash, cgroup and process observations absent/incomplete')
    if illustration > HOST_LIMIT and (not bound.get('qualified', False) or result['host_peak_bytes'] is None):
        refusal.append(f'note-based conservative scenario exceeds host ceiling: {illustration} bytes (assumed overhead)')
    pin_ceiling = HOST_LIMIT - overhead - CHUNK_BYTES
    joint_floor = math.ceil((total_weights - pin_ceiling + replicated * (tp - 1)) / tp) + identity['kv_bytes_per_rank']
    sweep = []
    for quarter in range(48, 73):
        budget = quarter * GIB // 4
        chosen, pin_count = select_offload(parameters, budget)
        lower = math.ceil((total_weights - pin_count * tp + replicated * (tp - 1)) / tp) + identity['kv_bytes_per_rank']
        sweep.append({'budget_gib_per_rank': quarter / 4, 'final_pins_bytes': pin_count * tp,
                      'scenario_host_peak_bytes': pin_count * tp + overhead + CHUNK_BYTES,
                      'vram_lower_bound_bytes_per_rank': lower,
                      'reserve_upper_bound_at_nominal_32gib_bytes': 32 * GIB - lower,
                      'joint_scenario_possible': (pin_count * tp + overhead + CHUNK_BYTES <= HOST_LIMIT and lower <= 28 * GIB)})
    return {'schema': 'screen1b.host-memory-prediction.v1', 'status': 'REFUSED' if refusal else 'ADMITTED',
            'prediction_is_measurement': False, 'launch': identity, 'metadata': metadata,
            'source_sha256': bound['source_sha256'], 'overlay_manifest_sha256': overlay_identity,
            'phase_bounds_manifest_sha256': sha256(bounds_path),
            'physical_vram_bytes_per_rank': bound['physical_vram_bytes_per_rank'],
            'physical_vram_evidence': bound['physical_vram_evidence'],
            'selected_parameters_rank0': selected, 'final_pins_bytes_per_rank': rank_pins,
            'placement_census': placement_census,
            'calibration': bound.get('calibration'),
            'candidate_table': enumerate_candidates(config, tensors) if placement_census else [],
            'final_pins_total_bytes': pins, 'offload_budget_overshoot_bytes_per_rank': (None if placement_census else pins_per_rank - identity['cpu_offload_bytes_per_rank']),
            'checkpoint_weight_bytes': total_weights, 'checkpoint_total_bytes': sum(t['bytes'] for t in tensors.values()),
            'static_floor_excluded_nonweight_bytes': sum(t['bytes'] for t in tensors.values()) - total_weights,
            'replicated_hc_bytes': replicated,
            'vram_static_lower_bound_bytes_per_rank': floors,
            'host_phases_bytes': phases, 'vram_phases_bytes_per_rank': vram_phases, **result,
            'illustrative_host_peak_bytes': illustration,
            'illustrative_components': {'pins': pins, **scenario, 'concurrent_staging_bytes': CHUNK_BYTES},
            'joint_gate_obstruction': {'assumed_nonpin_host_bytes': overhead + CHUNK_BYTES,
                'maximum_total_pins_under_host_gate_bytes': pin_ceiling,
                'best_possible_vram_lower_bound_bytes_per_rank': joint_floor,
                'nominal_capacity_upper_bound_bytes': 32 * GIB,
                'cannot_fit_even_nominal_32gib': joint_floor > 28 * GIB,
                'meaning': 'sensitivity to the old 20 GiB allowance ONLY; no impossibility claim without measured overhead'},
            'generic_budget_sweep': sweep, 'refusal_reasons': refusal,
            'remaining_committed_growth_bytes': bound.get('remaining_committed_growth_bytes'),
            'unknowns': bound['unknowns'], 'observations': observed}


def enforce_prediction(prediction, require_post_hash=True):
    reasons = prediction['refusal_reasons']
    if not require_post_hash:
        reasons = [reason for reason in reasons if reason not in {
            'post-hash MemAvailable/remaining committed growth unknown',
            'required pre/post-hash, cgroup and process observations absent/incomplete',
        }]
        # A missing committed-growth bound is static and must never be waived.
        if prediction.get('remaining_committed_growth_bytes') is None:
            reasons = [*reasons, 'required remaining committed growth bound unknown']
    if reasons:
        raise RuntimeError('Memory admission refused: ' + '; '.join(reasons))


def format_table(prediction):
    lines = ['Screen 1b host-RAM prediction (GB=10^9; GiB=2^30; not measured):',
             f'{"Component":43} {"bytes":>16} {"GB":>10} {"GiB":>10}']
    for name, value in prediction['illustrative_components'].items():
        lines.append(f'{name:43} {value:16,d} {value/1e9:10.6f} {value/GIB:10.6f}')
    value = prediction['illustrative_host_peak_bytes']
    lines.append(f'{"Sensitivity peak (unqualified allowances)":43} {value:16,d} {value/1e9:10.6f} {value/GIB:10.6f}')
    lines.append(f'Qualified Hpred: {prediction["host_peak_bytes"]!r}; status: {prediction["status"]}')
    for rank, lower in enumerate(prediction['vram_static_lower_bound_bytes_per_rank']):
        lines.append(f'Rank {rank}: static VRAM LOWER bound {lower/GIB:.6f} GiB; complete Vpeak/reserve UNKNOWN')
    if prediction.get('candidate_table'):
        lines += ['V30 candidates: native host PLE, KV 376569856, FULL_DECODE_ONLY; no calibrated peak available.',
                  'Candidate             Mode    Pins GB   Nonpin room to 85 GB   Static reserve UPPER bound GiB (r0..r3)']
        for row in prediction['candidate_table']:
            reserves = '/'.join(f'{x:.3f}' for x in row['conditional_static_reserve_gib_per_rank'])
            lines.append(f'{row["name"]:21} MTP{row["mtp_depth"]} {row["pins_total"]/1e9:10.3f} {row["nonpin_allowance_under_85gb"]/1e9:21.3f}   {reserves}')
        lines.append('All complete peaks UNKNOWN; none qualifies. Capacity assumption: 34242297856 bytes each, historical rank0 only.')
    lines.extend('REFUSE: ' + x for x in prediction['refusal_reasons'])
    return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launch-json', type=Path, required=True)
    parser.add_argument('--model-root', type=Path, default=DEFAULT_MODEL)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    plan = build_prediction(json.loads(args.launch_json.read_text()), args.model_root)
    print(format_table(plan))
    if args.output:
        args.output.write_text(json.dumps(plan, indent=2) + '\n')
