#!/usr/bin/env python3
"""Derive shape and memory planning from admitted bytes, without device access."""
import collections
import json
import os
from pathlib import Path
import subprocess

from admit import HERE, REPO, guards, sha, utc, write


def main():
    settings = guards()
    admission = json.loads((HERE/'admission-receipt.json').read_text())
    census = json.loads((HERE/'tensor-census.json').read_text())
    samples = json.loads((HERE/'sample-receipt.json').read_text())
    repeat = json.loads((HERE/'sample-repeat-receipt.json').read_text())
    regression = json.loads((HERE/'loader-test-receipt.json').read_text())
    assert all(r['passed'] for r in [admission,census,samples,repeat])
    assert regression['passed'] and regression['failures'] == regression['errors'] == 0
    assert samples['content_sha256'] == repeat['content_sha256']
    for r in [admission,samples,repeat]:
        for p, expected in r['sources'].items():
            assert sha(REPO/p) == expected, p
    assert sha(HERE/'tensor-census.json') == admission['census_sha256']
    all_t = {t['name']:t for t in census['tensors']}
    projections = [t for t in all_t.values() if len(t['shape'])==2 and t['name'].endswith('.weight')
                   and t['component'] not in ['vision_unsupported','embedding']]
    shapes = []
    for t in projections:
        n,k = t['shape']
        sb = all_t[t['format']['scale_tensor']]['bytes'] if t['dtype']=='F8_E4M3' else 0
        for m in [1,2,6]:
            weights = t['bytes']+sb
            shapes.append({'tensor':t['name'],'component':t['component'],'M':m,'N':n,'K':k,
                           'stored_dtype':t['dtype'],'weight_bytes':t['bytes'],'scale_bytes':sb,
                           'weight_plus_scale_bytes':weights,'input_f16_bytes':m*k*2,'output_f16_bytes':m*n*2,
                           'minimum_logical_io_bytes':weights+2*m*(k+n),'dot_flops_2MNK':2*m*n*k,
                           'unfused_logical_calls_per_step':1,'measured_launch_count':None,
                           'measured_device_bytes':None,'measured_seconds':None,
                           'planning_weight_stream_seconds_at_507GBps':weights/507e9})
    groups = collections.defaultdict(list)
    for r in shapes:
        groups[(r['M'],r['N'],r['K'],r['stored_dtype'])].append(r['tensor'])
    write('shape-census.json', {'scope':'All text/MTP stored linear matrices, unfused; vision excluded; embedding gather listed separately.',
                               'census_sha256':sha(HERE/'tensor-census.json'),'projection_count':len(projections),
                               'rows':shapes,'unique_shapes':[{'M':m,'N':n,'K':k,'dtype':dt,'count':len(names),'tensors':names}
                                                           for (m,n,k,dt),names in sorted(groups.items())],
                               'embedding_gather':[{'rows':m,'columns':5120,'read_bytes':m*5120*2,'write_bytes':m*5120*2}
                                                   for m in [1,2,6]],
                               'limits':'B and F are logical arithmetic, not measured traffic. Scales, weight and minimal F16 IO included; cache, scratch, rereads, fused launches and native timings remain packet 4. No speed result.'})
    components = census['totals_bytes']['component']
    full_text = sum(v for k,v in components.items() if k!='vision_unsupported')
    excluding_embedding = full_text-components['embedding']
    runtime = [
        {'class':'target_fp16_kv','bytes':2*16*4*256*2*32768,'basis':'K+V × 16 layers × 4 heads × D256 × 2B × T32768'},
        {'class':'mtp_fp16_kv','bytes':2*1*4*256*2*32768,'basis':'one full-attention MTP layer; full T32768 conservatively retained'},
        {'class':'gdn_fp32_state','bytes':48*48*128*128*4,'basis':'48 layers × 48 value heads × V128 × K128 × 4B'},
        {'class':'gdn_conv_fp16_state','bytes':48*10240*3*2,'basis':'48 layers × 10240 channels × 3 prior taps × 2B'},
        {'class':'gdn_rollback_checkpoint','bytes':48*48*128*128*4+48*10240*3*2,
         'basis':'one full recurrent+conv checkpoint; actual replay allocation unmeasured'},
        {'class':'graph_static_and_activations','bytes':256*2**20,'basis':'provisional 256 MiB allowance, not an allocation measurement'},
        {'class':'kernel_workspace','bytes':512*2**20,'basis':'provisional 512 MiB allowance; no full dequantized checkpoint'},
        {'class':'bounded_device_upload_staging','bytes':128*2**20,'basis':'provisional one 128 MiB slab'},
        {'class':'allocator_driver_overhead','bytes':512*2**20,'basis':'provisional 512 MiB allowance; device capacity/overhead unqueried'},
    ]
    for row in runtime:
        row['status'] = 'ESTIMATED; not allocated or measured'
    rt = sum(r['bytes'] for r in runtime)
    def space(p):
        s = os.statvfs(p)
        return {'path':str(p),'available_bytes':s.f_bavail*s.f_frsize,'fragment_bytes':s.f_frsize}
    mem = {k:int(v.strip().split()[0])*1024 for k,v in (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())}
    root_space, model_space = space(REPO), space(Path(admission['model']))
    # No weights copied or mapped. Budget even a worst-case full page-cache population.
    cpu_budget = admission['bytes'] + 2*2**30
    host_reserve = 8*2**30
    root_reserve, artifact_budget = 50*2**30, 16*2**20
    usb_other_writer_allowance = 82_000_000_000
    cpu_ok = mem['MemAvailable'] >= cpu_budget+host_reserve
    disk_ok = root_space['available_bytes'] >= root_reserve+artifact_budget
    usb_ok = model_space['available_bytes'] >= root_reserve+usb_other_writer_allowance
    write('memory-admission.json', {
        'utc':utc(),'settings':settings,'source_census_sha256':sha(HERE/'tensor-census.json'),
        'resident_weight_bytes_by_component':components,'all_payload_bytes':sum(components.values()),
        'one_card_text_plus_mtp_all_weights_bytes':full_text,
        'one_card_text_plus_mtp_excluding_embedding_bytes':excluding_embedding,
        'embedding_host_uva_alternative_bytes':components['embedding'],
        'vision_not_admitted_bytes':components['vision_unsupported'],
        'stored_bf16_scale_bytes':sum(t['bytes'] for t in all_t.values() if t['format']['kind']=='block_scale'),
        'weight_note':'Exact stored bytes; no BF16/F16 size change, no full FP8 dequant expansion or second packed copy. Shared embedding/head counted once. UVA is an alternative, not an implemented placement.',
        'estimated_runtime_classes':runtime,'estimated_runtime_total_bytes':rt,
        'nominal_capacity_scenarios':[{'capacity_bytes':capacity,'label':label,
                                      'all_resident_estimated_total_bytes':full_text+rt,
                                      'all_resident_remaining_bytes':capacity-full_text-rt,
                                      'embedding_uva_estimated_total_bytes':excluding_embedding+rt,
                                      'embedding_uva_remaining_bytes':capacity-excluding_embedding-rt}
                                     for capacity,label in [(32*2**30,'32 GiB planning only'),(32_000_000_000,'32 GB decimal sensitivity only')]],
        'native_admission':'NOT ESTABLISHED: actual usable device capacity, graph/workspace/driver peaks, checkpoint counts, host shadows and embedding placement must be measured later. No launch authorization.',
        'cpu_packet_budget':{'model_page_cache_upper_bytes':admission['bytes'],'anonymous_allowance_bytes':2*2**30,
                             'total_bytes':cpu_budget,'reserve_bytes':host_reserve,'mem_available_bytes':mem['MemAvailable'],
                             'mem_total_bytes':mem['MemTotal'],'passed':cpu_ok,
                             'measured_hash_max_rss_kib':admission['max_rss_kib'],
                             'measured_sample_max_rss_kib':max(samples['max_rss_kib'],repeat['max_rss_kib']),
                             'future_native_host_classes':'file-backed pages, optional UVA embedding, pinned staging, driver shadows, graphs and repacking remain unmeasured'},
        'disk_budget':{'repository':root_space,'model_filesystem':model_space,'root_reserve_bytes':root_reserve,
                       'packet_artifact_allowance_bytes':artifact_budget,'model_write_bytes':0,'model_copy_bytes':0,
                       'other_download_full_size_allowance_bytes':usb_other_writer_allowance,
                       'repository_passed':disk_ok,'model_free_space_sensitivity_passed':usb_ok,
                       'note':'Read-only existing checkpoint. External free bytes change with the owner download; no space is reserved or modified.'},
        'cpu_disk_host_admitted':cpu_ok and disk_ok and usb_ok})
    # Preserve the small already-inspected source excerpt supporting multiplier semantics.
    source = json.loads((HERE.parent/'packet1b/source-evidence.json').read_text())['sources'][3]
    text = subprocess.check_output(['git','-C',source['repository_local_read_only'],'show',source['commit']+':'+source['path']])
    import hashlib
    assert hashlib.sha256(text).hexdigest() == source['sha256']
    lines = text.decode().splitlines()
    excerpts = []
    for first,last in [(29,36),(80,88),(119,126)]:
        excerpts.append({'first_line':first,'last_line':last,'text':'\n'.join(lines[first-1:last])})
    write('scale-source-evidence.json', {'source':source,'excerpts':excerpts,
                                        'interpretation':'Wrapper passes the stored scale directly as oneDNN weight scale, on both block axes; no reciprocal. Real shape ratios establish N,K 128x128 addressing. CPU scalar fixtures establish the declared multiplication/cast implementation, not fused oneDNN parity.'})
    passed = cpu_ok and disk_ok and usb_ok
    outputs = ['admission-receipt.json','tensor-census.json','sample-receipt.json','sample-repeat-receipt.json',
               'shape-census.json','memory-admission.json','scale-source-evidence.json','loader-test-receipt.json']
    write('exit-gate.json', {'schema':'own-xpu-runtime.packet2.exit.v1','utc':utc(),'verdict':'PASS' if passed else 'BLOCKED',
                            'scope':'Stage 1 packet 2 CPU weight/loader admission only; not native allocation, inference parity or performance',
                            'gates':{'complete_publisher_manifest':admission['passed'],'no_missing_duplicate_or_different_tensors':census['passed'],
                                     'exact_storage_scale_convention_and_cpu_known_values':samples['passed'],
                                     'fresh_cpu_process_exact':samples['content_sha256']==repeat['content_sha256'],
                                     'packet1b_regression_suite':regression['passed'],
                                     'full_M1_M2_M6_linear_shapes':len(shapes)==3*len(projections),
                                     'disk_host_cpu_budget_admitted':passed},
                            'sources':{str(p.relative_to(REPO)):sha(p) for p in [Path(__file__),HERE/'admit.py',HERE/'check_samples.py']},
                            'artifacts':{n:sha(HERE/n) for n in outputs}})
    print(json.dumps({'exit_gate':'PASS' if passed else 'BLOCKED','linear_matrices':len(projections),
                      'shape_rows':len(shapes),'unique_shapes':len(groups),'resident_bytes':full_text,
                      'excluding_embedding_bytes':excluding_embedding,'runtime_estimated_bytes':rt,
                      '32GiB_remaining_estimated_bytes':32*2**30-full_text-rt}))
    assert passed


if __name__ == '__main__':
    main()
