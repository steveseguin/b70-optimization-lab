#!/usr/bin/env python3
"""Aggregate retained authenticated target metadata; never open model files."""
import collections
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
SOURCE = ROOT / 'experiments/own-xpu-runtime/gsq-rco-iq3s/metadata/new-census.json'
PLAN = ROOT / 'experiments/own-xpu-runtime/gsq-rco-iq3s/loader/placement.tsv'
EXPECTED = 'b47eae82a10854f47f23acc96e44d920a8b04ea1511f100aa1395418c41ca8a1'
GROUPS = {'Q2_0': '2-bit', 'IQ2_S': '2-bit', 'IQ3_XXS': '3-bit', 'IQ3_S': '3-bit',
          'IQ4_XS': '4-bit', 'IQ4_NL': '4-bit', 'Q4_K': '4-bit', 'Q5_K': '5-bit',
          'Q6_K': '6-bit', 'Q8_0': '8-bit', 'BF16': 'float', 'F16': 'float', 'F32': 'float'}
raw = SOURCE.read_bytes()
assert hashlib.sha256(raw).hexdigest() == EXPECTED
census = json.loads(raw)
# Independent retained placement table must enumerate exactly the same tensors,
# storage types, lengths and dimensions. Placement replicas are not counted twice.
plan = {}
for line in PLAN.read_text().splitlines():
    f = line.split()
    assert f[1] not in plan
    plan[f[1]] = dict(type_id=int(f[3]), bytes=int(f[5]), dimensions=list(map(int, f[9:])))
assert set(plan) == set(census['tensors'])
individual = collections.defaultdict(lambda: dict(tensors=0, parameters=0, payload_bytes=0))
grouped = collections.defaultdict(lambda: dict(tensors=0, parameters=0, payload_bytes=0))
for name, tensor in census['tensors'].items():
    assert tensor['elements'] == math.prod(tensor['dimensions'])
    assert all(plan[name][key] == tensor[key] for key in plan[name])
    for row in (individual[tensor['type']], grouped[GROUPS[tensor['type']]]):
        row['tensors'] += 1
        row['parameters'] += tensor['elements']
        row['payload_bytes'] += tensor['bytes']
parameters = sum(row['parameters'] for row in individual.values())
payload = sum(row['payload_bytes'] for row in individual.values())
for collection in (individual, grouped):
    for row in collection.values():
        row['parameter_percent'] = row['parameters'] / parameters * 100
        row['payload_byte_percent'] = row['payload_bytes'] / payload * 100
        row['effective_stored_bits_per_parameter'] = row['payload_bytes'] * 8 / row['parameters']
result = dict(schema='ownrt.target-mixed-quantization.v1', model='SC117/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-GGUF',
    revision='eec4e10a2c29b440a2ae85591fa11569ce752963', label='IQ3_S mixed GSQ-RCO',
    scope='Target only, all stored tensor elements including embeddings/PLE; excludes separate official FP8 draft, runtime conversion, activations and KV.',
    source=str(SOURCE.relative_to(ROOT)), source_sha256=EXPECTED,
    crosscheck=str(PLAN.relative_to(ROOT)), crosscheck_sha256=hashlib.sha256(PLAN.read_bytes()).hexdigest(),
    model_payload_reads=0, tensor_count=len(census['tensors']), total_parameters=parameters,
    encoded_tensor_payload_bytes=payload, gguf_container_bytes=census['file_bytes'],
    gguf_structural_and_alignment_bytes=census['file_bytes']-payload,
    effective_payload_bits_per_parameter=payload*8/parameters,
    effective_container_bits_per_parameter=census['file_bytes']*8/parameters,
    groups=dict(sorted(grouped.items())), individual_types=dict(sorted(individual.items())),
    retained_header_authority=[{key:s[key] for key in ('header_sha256','header_bytes_read','tensor_count','data_start')} for s in census['shards']],
    definitions=['Parameter denominator is sum(product(dimensions)) over all1224 stored target tensors, not tensor count or active MoE parameters.',
                 'Nominal bit families group format names; actual stored bpw includes block scales and format metadata.',
                 'Percent by encoded bytes uses tensor payload, not container total, CPU RAM, VRAM or traffic.',
                 'Q2_0 id42 is retained custom2-bit format:64 elements per18 bytes; see metadata/census.py.',
                 'Q5_K is present and must not be omitted from a nominal2/3/4/6/8/float summary.'])
ple_name = 'per_layer_token_embd.weight'
ple = census['tensors'][ple_name]
assert (ple['elements'], ple['bytes'], ple['type']) == (51200245760, 28800138240, 'IQ4_NL')
remaining_parameters = parameters - ple['elements']
remaining_payload = payload - ple['bytes']
remaining = {}
for label, collection in (('groups', grouped), ('individual_types', individual)):
    reduced = {}
    for name, original in sorted(collection.items()):
        row = {key: original[key] for key in ('tensors', 'parameters', 'payload_bytes')}
        if name == (GROUPS[ple['type']] if label == 'groups' else ple['type']):
            row['tensors'] -= 1
            row['parameters'] -= ple['elements']
            row['payload_bytes'] -= ple['bytes']
        row['parameter_percent'] = row['parameters'] / remaining_parameters * 100
        row['payload_byte_percent'] = row['payload_bytes'] / remaining_payload * 100
        row['effective_stored_bits_per_parameter'] = row['payload_bytes'] * 8 / row['parameters']
        reduced[name] = row
    assert sum(row['parameters'] for row in reduced.values()) == remaining_parameters
    assert sum(row['payload_bytes'] for row in reduced.values()) == remaining_payload
    remaining[label] = reduced
result['excluding_PLE_table_view'] = dict(
    scope='All target tensors except exactly per_layer_token_embd.weight; other embeddings, experts and float tensors remain. Not active parameters per token.',
    removed_tensor=dict(name=ple_name, type=ple['type'], parameters=ple['elements'], payload_bytes=ple['bytes']),
    tensor_count=len(census['tensors'])-1, total_parameters=remaining_parameters,
    encoded_tensor_payload_bytes=remaining_payload,
    effective_payload_bits_per_parameter=remaining_payload*8/remaining_parameters,
    **remaining)
print(json.dumps(result, indent=2, ensure_ascii=False))
