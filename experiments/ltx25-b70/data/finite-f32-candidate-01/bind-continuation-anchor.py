#!/usr/bin/env python3
"""Construct an inactive continuation graph with a concrete float-anchor node.

No Torch import, model load, endpoint call, runtime mutation or submission.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re


SCRIPTS = Path(__file__).resolve().parent
BASE_BUILDER = SCRIPTS / 'build-continuation-graph.py'
BASE_BUILDER_SHA256 = '22911dcda8ecad5f88b11d04521e777215ee9b96bfd7c3bcb1eb29f2e3dbe33d'
PROVIDER_ID = 'continuation_float_anchor'
PROVIDER_CLASS = 'LTXLoadFloatContinuationAnchor'


def load_builder():
    if hashlib.sha256(BASE_BUILDER.read_bytes()).hexdigest() != BASE_BUILDER_SHA256:
        raise ValueError('base continuation constructor changed; review and rebind')
    spec = importlib.util.spec_from_file_location('unbound_continuation_graph', BASE_BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_bound_chunk(chunk_index, run_name, seed=42, prompt=None,
                      predecessor_run=None, anchor_sha256=None):
    if not isinstance(run_name, str) or not re.fullmatch(r'continuation-[a-z0-9_-]+', run_name):
        raise ValueError('run_name must be a lowercase continuation capture identifier')
    builder = load_builder()
    subsequent = type(chunk_index) is int and chunk_index > 0
    if subsequent:
        if (not isinstance(predecessor_run, str)
                or not re.fullmatch(r'[a-z0-9_-]+', predecessor_run)
                or predecessor_run == run_name):
            raise ValueError('subsequent chunk requires a distinct predecessor capture identifier')
    elif predecessor_run is not None:
        raise ValueError('first chunk cannot name a predecessor capture')
    envelope = builder.build_chunk(chunk_index, run_name, seed, prompt,
                                  [PROVIDER_ID, 0] if subsequent else None,
                                  anchor_sha256)
    contract = envelope.pop('external_image_input')
    envelope['schema'] = 'ltx25.continuation-bound-graph.v1'
    envelope['anchor_input'] = None
    if subsequent:
        envelope['graph'][PROVIDER_ID] = {'class_type': PROVIDER_CLASS, 'inputs': {
            'predecessor_run': predecessor_run, 'expected_sha256': anchor_sha256}}
        builder.SPECS = copy.deepcopy(builder.SPECS)
        builder.SPECS[PROVIDER_CLASS] = ({'predecessor_run': 'STRING',
                                        'expected_sha256': 'STRING'}, ['IMAGE'])
        builder.validate_edges(envelope['graph'])
        contract['provider_implemented'] = True
        contract['provider_native_tensor_qualified'] = False
        contract['predecessor_lineage_verified'] = False
        contract['predecessor_run'] = predecessor_run
        contract['payload_hash_verified'] = False
        contract['verification_time'] = 'provider execution; no capture opened by this constructor'
        contract['lineage_requirement'] = ('future controller must bind completed predecessor chunk, '
            'prompt/seed schedule and model/runtime identity; filename and frame hash alone are insufficient')
        envelope['anchor_input'] = contract
    envelope['implementation'] = {
        'base_builder_sha256': BASE_BUILDER_SHA256,
        'source_sha256': {name: hashlib.sha256((SCRIPTS / name).read_bytes()).hexdigest()
                          for name in ('bind-continuation-anchor.py',
                                       'continuation_anchor_node.py', 'continuation_anchor_io.py')},
        'deployment': 'inactive; prepare and attest a separate runtime before submission',
    }
    return envelope


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chunk-index', type=int, required=True)
    parser.add_argument('--run-name', required=True)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--prompt')
    parser.add_argument('--predecessor-run')
    parser.add_argument('--anchor-sha256')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_bound_chunk(args.chunk_index, args.run_name, args.seed, args.prompt,
                                   args.predecessor_run, args.anchor_sha256)
        with args.output.open('x') as output:
            json.dump(result, output, indent=2, allow_nan=False)
            output.write('\n')
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
