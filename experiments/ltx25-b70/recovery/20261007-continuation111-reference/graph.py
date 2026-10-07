"""Inactive native continuation modules from sealed110; never a /prompt body.

The IMAGE edge is deliberately external. No provider is registered and no111
runtime, authority, encoding-memory admission or launch contract exists here.
"""
import ast
import copy
import json
import os
from pathlib import Path
import stat

import anchor

PACKET = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-duration-full-110')
MANIFEST_SHA = 'bfa78fcf6af59acc3d63318ca97c61846b3a9b80999f6f17cb4c4d3651f2ad09'
PLAN_FILE_SHA = 'fdfa389c12730659ff5ab067361ef06b3923f446db6f9ed16ef2d00f5aa8ea22'
PLAN_SHA = 'cafb272fcb182d80022a0e73eff838dc7fd0aeb5001704d0b9ccbd37fadeccab'
BASE_GRAPH_SHA = '6bf2475c5b30461006993c4a2483503fc8e18474c2474ded8071112436e995bc'
MODEL_SHA = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
SEEDS = (42, 43, 44)
ANCHOR_EDGE = ['continuation111_anchor', 0]
SOURCE_PATHS = ('source/nodes.py', 'source/comfy_extras/nodes_custom_sampler.py',
    'source/comfy_extras/nodes_lt.py', 'source/comfy_extras/nodes_lt_audio.py',
    'source/comfy_extras/nodes_lt_upsampler.py', 'source/scripts/pipeline_node.py',
    'source/scripts/host_embedding_resident_node.py', 'source/scripts/graph_text_encoder_node.py',
    'source/scripts/ltx_output_size_98.py', 'source/scripts/capture_node.py')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _read(path, expected):
    path = anchor.safe_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        anchor.require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                       before.st_size <= 8*1024**2, 'Nonregular/linked/oversized source input')
        stream = os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise
    with stream:
        raw = stream.read(8*1024**2+1)
        anchor.require(len(raw) == before.st_size and
                       anchor.identity(before) == anchor.identity(os.fstat(fd)) == anchor.identity(path.lstat()),
                       'Source changed while reading')
    anchor.require(anchor.sha(raw) == expected, 'Sealed source changed: ' + str(path))
    return raw


def basis():
    manifest = anchor.strict_json(_read(PACKET/'manifest.json', MANIFEST_SHA))
    sources = {p: manifest['files'][p] for p in SOURCE_PATHS}
    raw_sources = {p: _read(PACKET/p, sources[p]) for p in SOURCE_PATHS}
    tree = ast.parse(raw_sources['source/comfy_extras/nodes_lt.py'])
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'LTXVImgToVideoInplace')
    execute = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == 'execute')
    anchor.require([a.arg for a in execute.args.args] == ['cls','vae','image','latent','strength','bypass'],
                   'Native image-conditioning API differs')
    anchor.require(b'return_dict.pop("noise_mask", None)' in raw_sources['source/comfy_extras/nodes_lt_upsampler.py'],
                   'Upsampler mask behavior requires new source review')
    envelope = anchor.strict_json(_read(PACKET/'resolution/candidate-plan.json', PLAN_FILE_SHA))
    anchor.require(envelope['plan_sha256'] == PLAN_SHA == anchor.sha(canonical(envelope['plan'])), 'Plan basis differs')
    row = envelope['plan']['requests'][0]
    anchor.require(row['fixture'] == 'boat' and row['phase'] == 'native-reference' and
                   row['graph_sha256'] == BASE_GRAPH_SHA == anchor.sha(canonical(row['graph'])), 'Native graph differs')
    return copy.deepcopy(row['graph']), sources


def design():
    base, sources = basis()
    contract = {'source_packet_manifest_sha256': MANIFEST_SHA, 'source_plan_sha256': PLAN_SHA,
        'base_graph_sha256': BASE_GRAPH_SHA, 'source_files': sources, 'model_verification_sha256': MODEL_SHA,
        'prompt': base['364']['inputs']['text'], 'seeds': list(SEEDS),
        'frame_count':49, 'output_size':'640x384', 'stage_steps':[8,3], 'precision':'unchanged BF16',
        'placement':'two-way20-28', 'window_encoder':'accepted graph-sharded window64',
        'conditioning':{'chunk0':'ordinary native', 'chunks1_2':'predecessor frame48 before both samplers',
                        'strength':1.0, 'bypass':False, 'image_shape':anchor.ANCHOR_SHAPE},
        'audio':'raw outputs unchanged; timeline unresolved; no trim/resample/crossfade/concatenation'}
    return {'schema':'ltx.continuation111.reference-design.v1', 'contract':contract,
        'prototype_plan_sha256':anchor.sha(canonical(contract)),
        'execution_order':[(p,c) for p in range(2) for c in range(3)],
        'new_video_frames_per_chunk':[49,48,48], 'unique_video_frames_per_chain':145,
        'replay_frames_are_not_new_content':True, 'ready_for_submission':False,
        'qualified':False, 'output_slicing_implemented':False,
        'six_full_capture_bound_bytes':6*146230536,
        'capture_bound_is_not_storage_admission':True}


def name(pass_index, chunk_index):
    anchor.require(type(pass_index) is int and pass_index in (0,1) and
                   type(chunk_index) is int and chunk_index in (0,1,2), 'Only two complete three-chunk passes')
    return 'continuation111-pass%d-chunk%d' % (pass_index, chunk_index)


def predecessor_context(module):
    row = module['chunk']
    anchor.require(row['index'] in (0,1), 'Chunk2 is not a predecessor in this bounded design')
    return {'runtime_manifest_sha256':module['target_runtime_manifest_sha256'],
        'model_verification_sha256':MODEL_SHA, 'plan_sha256':module['prototype_plan_sha256'],
        'prompt_sha256':anchor.sha(module['graph']['364']['inputs']['text'].encode()),
        'pass_index':row['pass_index'], 'chunk_index':row['index'], 'seed':row['seed'],
        'graph_sha256':module['graph_sha256'], 'capture_name':row['name']}


def _edges(graph, external):
    visiting, done = set(), set()
    uses = []
    def visit(key):
        anchor.require(key not in visiting, 'Graph cycle')
        if key in done:
            return
        visiting.add(key)
        node = graph[key]
        anchor.require(set(node) == {'class_type','inputs'}, 'Unexpected graph fields')
        for field, value in node['inputs'].items():
            if isinstance(value, list):
                anchor.require(len(value) == 2 and isinstance(value[0], str) and type(value[1]) is int and value[1]>=0,
                               'Malformed graph edge')
                if external and value == ANCHOR_EDGE:
                    uses.append((key,field))
                else:
                    anchor.require(value[0] in graph, 'Dangling graph edge')
                    visit(value[0])
        visiting.remove(key); done.add(key)
    for key in graph:
        visit(key)
    anchor.require(sorted(uses) == ([('anchor_stage_a','image'),('anchor_stage_b','image')] if external else []),
                   'Anchor must feed both conditioning nodes only')


def build_chunk(pass_index, chunk_index, target_runtime_manifest_sha256, *, predecessor=None, binding=None):
    """Construct an inactive envelope; target runtime hash is an external future binding.

    Subsequent chunks require a previously constructed, validated module and a
    capture binding; building does not itself read or trust any tensor payload.
    load_image must verify that payload again under future execution authority.
    """
    run_name = name(pass_index, chunk_index)
    anchor.digest(target_runtime_manifest_sha256)
    graph, sources = basis()
    contract = design()
    prototype_sha = contract['prototype_plan_sha256']
    if chunk_index:
        anchor.require(predecessor is not None and binding is not None, 'Missing predecessor/anchor binding')
        anchor.require(type(predecessor) is dict and type(predecessor.get('chunk')) is dict and
                       predecessor['chunk'].get('pass_index') == pass_index and
                       predecessor['chunk'].get('index') == chunk_index-1 and
                       predecessor.get('target_runtime_manifest_sha256') == target_runtime_manifest_sha256,
                       'Predecessor replay order/runtime mismatch')
        validate_module(predecessor)
        expected = predecessor_context(predecessor)
        anchor.validate_binding(binding, expected)
    else:
        anchor.require(predecessor is None and binding is None, 'Chunk0 cannot consume an anchor')
    for node in graph.values():
        if 'run_name' in node['inputs']:
            node['inputs']['run_name'] = run_name
    for key in ('338','339'):
        graph[key]['inputs']['noise_seed'] = SEEDS[chunk_index]
    graph['364']['inputs']['clip_index'] = 99911000+pass_index*10+chunk_index
    graph['364']['inputs']['qualification_id'] = prototype_sha
    if chunk_index:
        for key, edge in (('anchor_stage_a',['356',0]),('anchor_stage_b',['348',0])):
            graph[key] = {'class_type':'LTXVImgToVideoInplace','inputs':{
                'vae':['420',2], 'image':list(ANCHOR_EDGE), 'latent':edge, 'strength':1.0, 'bypass':False}}
        graph['377']['inputs']['video_latent'] = ['anchor_stage_a',0]
        graph['340']['inputs']['video_latent'] = ['anchor_stage_b',0]
    _edges(graph, bool(chunk_index))
    return {'schema':'ltx.continuation111.native-module.v1', 'ready_for_submission':False,
        'source_packet_manifest_sha256':MANIFEST_SHA, 'source_files':sources,
        'target_runtime_manifest_sha256':target_runtime_manifest_sha256,
        'prototype_plan_sha256':prototype_sha, 'graph':graph, 'graph_sha256':anchor.sha(canonical(graph)),
        'chunk':{'pass_index':pass_index,'index':chunk_index,'name':run_name,'seed':SEEDS[chunk_index],
                 'raw_frames':49,'delivery_frame_start':int(chunk_index>0),'new_video_frames':48 if chunk_index else 49},
        'predecessor':copy.deepcopy(predecessor), 'anchor_binding':copy.deepcopy(binding),
        'external_image_input':list(ANCHOR_EDGE) if chunk_index else None,
        'provider_registered':False, 'runtime_admitted':False,
        'audio':'unchanged separate raw output; timeline unresolved'}


def validate_module(module):
    anchor.require(type(module) is dict and type(module.get('chunk')) is dict, 'Invalid module')
    row = module['chunk']
    expected = build_chunk(row['pass_index'], row['index'], module['target_runtime_manifest_sha256'],
                           predecessor=module.get('predecessor'), binding=module.get('anchor_binding'))
    anchor.require(module == expected, 'Continuation module changed from exact source construction')
