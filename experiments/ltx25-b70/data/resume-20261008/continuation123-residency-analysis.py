#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""CPU standard-library-only header/receipt analysis; no runtime/device import."""
import collections
import hashlib
import json
import math
from pathlib import Path
import re
import struct

HERE = Path(__file__).resolve().parent
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
RUN = ROOT / 'encoder-server-continuation-stream-121-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145'
WEIGHTS = Path('/mnt/fast-ai/llm-models/LTX-2.5-baseline')
GIB = 2**30
sources = {}


def read(p):
    raw = p.read_bytes()
    sources[str(p)] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    return json.loads(raw)


def header(p):
    with p.open('rb') as f:
        size = f.read(8)
        n, = struct.unpack('<Q', size)
        assert 0 < n < 16 * 1024 * 1024
        raw = f.read(n)
    sources[str(p)] = {'header_with_length_sha256': hashlib.sha256(size + raw).hexdigest(),
                       'header_bytes': n + 8, 'file_bytes': p.stat().st_size,
                       'payload_read': False}
    h = json.loads(raw)
    return {k: {'shape': v['shape'], 'dtype': v['dtype'],
                'checkpoint_bytes': v['data_offsets'][1] - v['data_offsets'][0],
                'bf16_runtime_bytes': math.prod(v['shape']) * 2}
            for k, v in h.items() if k != '__metadata__'}


def total(h, match=lambda k: True, kind='bf16_runtime_bytes'):
    return sum(v[kind] for k, v in h.items() if match(k))


def main():
    previous = read(HERE / 'continuation122-evidence.json')
    census = previous['census']
    run = previous['runs']['121_145_dg0']
    prep = read(RUN / 'stream-preparation.json')
    owner = read(RUN / 'host-components-01-control-result.json')['encoder_initial_ownership']['encoder']
    model = header(WEIGHTS/'diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors')
    up = header(WEIGHTS/'latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors')
    audio = header(WEIGHTS/'vae/ltx-2.5-audio-vae-bf16.safetensors')
    video = header(WEIGHTS/'vae/ltx-2.5-video-vae-bf16.safetensors')
    text = header(WEIGHTS/'text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors')
    block_bytes = {str(i): total(model, lambda k: 'transformer_blocks.%d.' % i in k) for i in range(48)}
    assert len(set(block_bytes.values())) == 1
    block = block_bytes['0']
    nonblock = total(model, lambda k: 'transformer_blocks.' not in k)
    text_resident = [0, 0]
    for kind in ('parameters', 'buffers'):
        for row in owner[kind]['records']:
            layer = re.search(r'\.layers\.(\d+)\.', row['name'])
            text_resident[int(bool(layer and int(layer[1]) >= 24))] += row['bytes']
    upbytes, audbytes = total(up), total(audio)
    assert upbytes == 995735808 and audbytes == 364666868
    assert all(v['dtype'] == 'BF16' for v in [*up.values(), *audio.values(), *video.values()])
    missing = prep['receipts'][0]['missing_tensor_bytes']
    resident = {
        'xpu:0': {'sampler_blocks': [0, 19], 'sampler_bf16_header_bytes': block*20+nonblock,
                  'sampler_actual_inventory_bytes': missing['xpu:0']-upbytes,
                  'sampler_constructor_extra_bytes': missing['xpu:0']-upbytes-block*20-nonblock,
                  'sampler_nonblock_bf16_header_bytes': nonblock, 'upsampler_bytes': upbytes},
        'xpu:1': {'sampler_blocks': [20, 47], 'sampler_bf16_header_bytes': block*28,
                  'sampler_actual_inventory_bytes': missing['xpu:1']},
        'xpu:2': {'text_layers': [0, 23], 'text_actual_inventory_bytes': text_resident[0]},
        'xpu:3': {'text_layers': [24, 47], 'text_actual_inventory_bytes': text_resident[1],
                  'video_encoder_header_bytes': total(video, lambda k: k.startswith('encoder.')),
                  'video_decoder_header_bytes': total(video, lambda k: k.startswith('decoder.')),
                  'video_statistics_header_bytes': total(video, lambda k: k.startswith('per_channel_statistics.')),
                  'audio_vae_header_bytes': total(audio, lambda k: k.startswith('audio_vae.')),
                  'vocoder_header_bytes': total(audio, lambda k: k.startswith('vocoder.')),
                  'video_plus_audio_actual_inventory_bytes': missing['xpu:3'],
                  'video_plus_audio_constructor_extra_bytes': missing['xpu:3']-total(video)-audbytes}}
    bases = {'xpu:0': missing['xpu:0'], 'xpu:1': missing['xpu:1'],
             'xpu:2': text_resident[0], 'xpu:3': text_resident[1]+missing['xpu:3']}
    for card in bases:
        resident[card]['static_inventory_bytes'] = bases[card]
        resident[card]['preparation_allocated_beyond_inventory_bytes'] = run['preparation']['peaks'][card]['allocated']-bases[card]
        resident[card]['preparation_allocator_reserved_bytes'] = run['preparation']['peaks'][card]['reserved']
    options = {}
    for name, delta in {
        'legacy': {},
        'two-way18-30': {'xpu:0': 2*block, 'xpu:1': -2*block},
        'two-way16-32': {'xpu:0': 4*block, 'xpu:1': -4*block},
        'upsampler-only-xpu2': {'xpu:0': upbytes, 'xpu:2': -upbytes},
        'audio-only-xpu2': {'xpu:3': audbytes, 'xpu:2': -audbytes},
        'upsampler-and-audio-xpu2': {'xpu:0': upbytes, 'xpu:3': audbytes, 'xpu:2': -upbytes-audbytes},
        'upsampler-and-video-encoder-xpu2': {'xpu:0': upbytes,
            'xpu:3': resident['xpu:3']['video_encoder_header_bytes'],
            'xpu:2': -upbytes-resident['xpu:3']['video_encoder_header_bytes']},
        'upsampler-and-text-layer24-xpu2': {'xpu:0': upbytes,
            'xpu:3': total(text, lambda k: k.startswith('model.layers.24.')),
            'xpu:2': -upbytes-total(text, lambda k: k.startswith('model.layers.24.'))},
    }.items():
        margins = {f: {c: [v+delta.get(c, 0)/GIB for v in band]
                          for c, band in census[f]['dg0_margin_gib'].items()} for f in ('145', '169')}
        options[name] = {'static_freed_bytes_by_card': delta, 'dg0_margin_gib': margins,
                         '169_static_scenario_clears_all_075': all(v[0] >= .75 for v in margins['169'].values()),
                         'credit_for_removed_workspace_bytes': 0}
    # Explicitly reserve 2 GiB on xpu:2 for the newly colocated native workspaces.
    aux = options['upsampler-and-audio-xpu2']
    aux['destination_extra_workspace_reserve_gib'] = 2.0
    aux['margin_after_workspace_reserve_gib'] = {f: {**m, 'xpu:2': [v-2 for v in m['xpu:2']]}
                                                for f, m in aux['dg0_margin_gib'].items()}
    replica = previous['runs']['120_121_dg1_replica']['replica']
    latentframes = 22
    audioframes = 176  # sealed formula at169
    result = {
        'schema': 'ltx.continuation123.residency-analysis.v1',
        'scope': 'CPU regular-file/header reads only; projections are not measurements or peak proofs',
        'resident': resident, 'sampler_runtime_block_bytes': block, 'sampler_checkpoint_header_block_bytes':
            total(model, lambda k: 'transformer_blocks.0.' in k, 'checkpoint_bytes'),
        'all_model_header_tensors': {'sampler': len(model), 'text': len(text), 'upsampler': len(up), 'video': len(video), 'audio': len(audio)},
        '145_phase_minima': run['phase_minima'], '145_allocator_high_water': run['allocator_high_water'],
        '145_preparation_free_bytes': run['preparation']['free'],
        '145_minimum_before_cone_free_bytes': run['minimum_before_cone_free_bytes'],
        'options': options,
        '169_copy_volumes': {'stage_a_f32_latent_bytes': 1*128*latentframes*4*4*4,
                            'stage_b_f32_latent_bytes': 1*128*latentframes*8*8*4,
                            'audio_f32_latent_bytes': 1*8*audioframes*16*4,
                            'audio_f32_waveform_bytes': 1*2*336480*4,
                            'new_video_seconds': 7.0,
                            'note': 'native paths already stage CPU->device and device->CPU; destination changes do not add a direct peer hop'},
        '169_prediction': {'sampler_a_s': [1.95, 2.15], 'sampler_b_s': [1.85, 2.05],
                           'cone_s': [.85, 1.10], 'other_chain_s': [1.10, 1.30],
                           'period_s': [5.95, 6.65], 'period_per_new_video_second': [5.95/7, 6.65/7],
                           'display_s': [2.72, 3.30], 'display_linear_frames_s': run['timings']['display']['median']*169/145,
                           'offchain_3s_proven': False,
                           'replica_transient_gib': census['169']['replica_growth_gib'],
                           'replica_budget_gib': 6.5,
                           'replica_plus_aux_margin_xpu2_before_extra_workspace_reserve_gib': replica['min_before_free_bytes']/GIB-2-6.5-(upbytes+audbytes)/GIB,
                           'replica_plus_aux_margin_xpu2_after_2gib_workspace_reserve_gib': replica['min_before_free_bytes']/GIB-2-6.5-(upbytes+audbytes)/GIB-2,
                           'replica_recommendation': 'not admitted before measured auxiliary workspace overlap; does not prove display <3s'},
        'limits': ['Allocator preparation residuals mix graph pools, static buffers, workspace and allocator overhead; receipts cannot split them exactly.',
                   'Header bytes are static payload; physical-free benefit of moving weights must be measured after new qualification.',
                   'No isolated audio/upsampler workspace peak exists; 2GiB reserve is an explicit planning assumption, not a measured bound.',
                   '169 xpu3 low margin .825GiB leaves only .075GiB over screening target, so all phase checks and retained-tail observations remain required.',
                   '145 dg1 replica remains inadmissible and is not a launch recommendation.'],
        'sources': sources}
    out = HERE/'continuation123-residency-analysis.json'
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({'resident': resident, 'options': options, 'prediction': result['169_prediction']}, indent=2))


if __name__ == '__main__': main()
