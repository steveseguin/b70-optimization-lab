#!/usr/bin/env python3
"""Exact packed-byte arithmetic plus explicitly provisional runtime budgets."""
from collections import defaultdict
import json
from pathlib import Path
from admit import HERE, ROOT, OWN, dump, source_hashes


def main():
    c = json.loads((HERE/'tensor-census.json').read_text())
    prior = json.loads((OWN/'stage2/packet1c/ud-census.json').read_text())['variants']['UD-IQ3_XXS']
    components = {}
    for name,v in c['components'].items():
        offloaded = name in ('embedding','ple_lookup')
        extra = sum(t['bytes'] for t in c['tensors'] if t['component']==name and t['hc_projection_replicated'])
        components[name] = dict(tensor_bytes=v['bytes'],offloaded_bytes=v['bytes'] if offloaded else 0,
                               extra_hc_copy_bytes=extra,resident_bytes=(0 if offloaded else v['bytes'])+extra)
    resident = sum(v['resident_bytes'] for v in components.values())
    offloaded = sum(v['offloaded_bytes'] for v in components.values())
    assert resident == 53_304_619_520
    assert all(v['tensor_bytes']==prior['components'][k]['bytes'] for k,v in components.items())
    capacity,kv,ple = 68_484_595_712,753_139_712,280
    official_path = OWN/'stage2/packet1/tensor-contract.json'
    official = json.loads(official_path.read_text())
    mtp = [t for t in official['tensors'] if t['component']=='native_mtp']
    mtp_bytes = sum(t['bytes'] for t in mtp)
    mtp_hc = [t for t in mtp if 'input_mix_weight_' in t['name']]
    mtp_extra = sum(t['bytes'] for t in mtp_hc)
    assert mtp_bytes == 2_698_026_496 and mtp_extra == 39_321_600
    historical = dict(capacity_bytes=capacity,capacity_status='historical two-card scenario; no device query',
        target_resident_bytes=resident,balanced_bytes_per_card=resident//2,
        target_weight_only_margin_bytes=capacity-resident,
        target_full16_kv_budget_bytes=kv,ple_control_metadata_bytes=ple,
        kv_status='historical 2 x 376569856 budget only, not derived TP2 allocation or a 32K estimate',
        target_margin_after_kv_and_metadata_bytes=capacity-resident-kv-ple,
        target_plus_one_stored_mtp_bytes=resident+mtp_bytes,
        mtp_weight_only_margin_bytes=capacity-resident-mtp_bytes,
        mtp_margin_after_target_kv_and_metadata_bytes=capacity-resident-mtp_bytes-kv-ple,
        mtp_extra_hc_replica_bytes=mtp_extra,
        target_plus_mtp_with_extra_hc_bytes=resident+mtp_bytes+mtp_extra)
    # Scenario only: one request at 32K, BF16 recurrence and full 16-bit KV.
    classes = {}
    def add(name,value,formula): classes[name]=dict(estimated_bytes=value,formula=formula,status='estimate; not allocated or measured')
    add('target_full16_kv',12*32768*2*2*256*2,'12 QSA layers * 32768 tokens * K/V * 2 heads * 256 width * 2 B; heads partitioned over TP2')
    add('target_bf16_gdn_state',36*48*128*128*2,'36 layers * 48 value heads * 128 * 128 * BF16 2 B; heads partitioned')
    add('target_bf16_gdn_conv',36*10240*3*2,'36 layers * 10240 channels * 3 history rows * 2 B; partitioned')
    add('target_bf16_ple_conv',10240*3*2,'one 10240-channel convolution * 3 history rows * 2 B; one logical copy')
    add('target_qsa_raw_index',12*32768*128*2,'12 layers * 32768 tokens * one 128-wide key * 2 B')
    add('target_qsa_pooled_index',12*(32768//4)*128*2,'12 layers * floor(32768/4) * 128 * 2 B')
    add('target_tp2_extra_index_copy',12*(32768+32768//4)*128*2,'one extra copy of raw+pooled single-head index for TP2')
    target_state = sum(x['estimated_bytes'] for x in classes.values())
    rollback = (36*48*128*128+36*10240*3+10240*3)*2
    add('one_target_rollback_checkpoint',rollback,'one full GDN+conv+PLE snapshot; append-only KV/index assumed cursor rollback, not proven')
    # Deliberately visible provisional reserves; no capacity qualification.
    for name in ('graphs_and_static_buffers','operator_scratch','allocator_and_driver_reserve'):
        add(name,2*1024**3,'planning allowance 1 GiB/card * 2; replace with native peak measurement')
    add('bounded_device_staging',2*256*1024**2,'planning allowance 256 MiB/card * 2; no full dequantized shadow admitted')
    runtime_total = sum(x['estimated_bytes'] for x in classes.values()) + ple
    mtp_state = 32768*2*2*256*2 + 2*(32768+32768//4)*128*2
    memory = dict(schema='qwen38-ud-iq3xxs.memory-arithmetic.v1',scope='exact stored weight sums under stated placement; ALL runtime memory classes are estimates; no native fit verdict',
        source_hashes=source_hashes([Path(__file__),HERE/'tensor-census.json',official_path,OWN/'STAGE2-PLAN.md',OWN/'stage2/packet1b/reference.py']),
        component_placement=components,total_tensor_bytes=c['tensor_bytes'],offloaded_bytes=offloaded,
        historical_plan_reconciliation=historical,
        optional_mtp=dict(repository='Qwen/Qwen3.8-Flash-Next-FP8',revision='bcd9f01ddc9cff2316eb84281bebcd5b058bddce',
            stored_bytes=mtp_bytes,extra_hc_replica_bytes=mtp_extra,hc_replica_tensors=[t['name'] for t in mtp_hc],
            payload_admitted_here=False,source='official retained tensor contract; no official payload read or download',
            configuration='separately pinned draft block with quantized target shared embedding/head; mixed checkpoint, every accepted token verified by unchanged quantized target; separate state and rollback required'),
        scenario_32k=dict(users=1,context_tokens=32768,classes=classes,
            target_live_state_bytes=target_state,estimated_runtime_total_bytes=runtime_total,
            target_with_estimates_bytes=resident+runtime_total,
            target_remaining_under_historical_capacity_bytes=capacity-resident-runtime_total,
            optional_mtp_additional_kv_and_index_bytes=mtp_state,
            mtp_additional_state_formula='one QSA block: T*K/V*2 heads*256*2 B + 2 TP copies*(T+T/4)*128*2 B',
            target_mtp_with_estimates_bytes=resident+mtp_bytes+mtp_extra+runtime_total+mtp_state,
            target_mtp_remaining_under_historical_capacity_bytes=capacity-resident-mtp_bytes-mtp_extra-runtime_total-mtp_state),
        uncounted=['additional router/norm/PLE and other replicas','native padding/alignment and quant repacks','scale widening or full/partial dequantization buffers','prefill activations and attention/indexer score temporaries beyond provisional scratch','extra MTP HC/hidden transaction snapshots and additional rollback versions','host driver shadows, mmap/page cache and pinned host staging'],
        host_placement='PLE 28800138240 B plus embedding 521472000 B off-device; logical file backing 29321610240 B is not a RAM reservation. Bounded file-backed lookup and I/O validation required on 15 GiB host; no full resident host-table claim.',
        device_fit='UNMEASURED')
    dump(HERE/'memory-admission.json',memory)
    admission=json.loads((HERE/'admission-receipt.json').read_text())
    samples=json.loads((HERE/'sample-receipt.json').read_text())
    repeat=json.loads((HERE/'sample-repeat-receipt.json').read_text())
    tests=json.loads((HERE/'loader-test-receipt.json').read_text())
    crosscheck=json.loads((HERE/'dequant-crosscheck.json').read_text())
    reconcile=json.loads((HERE/'reconciliation.json').read_text())
    passed=all([admission['passed'],samples['passed'],repeat['fresh_process_bit_exact'],tests['passed'],reconcile['passed'],crosscheck['passed']])
    dump(HERE/'exit-gate.json',dict(schema='qwen38-ud-iq3xxs.packet1-exit.v1',passed=passed,
        scope='CPU weight admission and bounded reference fixtures only',
        sources=source_hashes([HERE/n for n in ['admit.py','check_samples.py','summarize.py','admission-receipt.json','tensor-census.json','metadata.json','reconciliation.json','sample-receipt.json','sample-repeat-receipt.json','loader-test-receipt.json','memory-admission.json','admission-tests.log','dequant-crosscheck.json','range-tests.log','test_admission.py']]),
        inference_result='no result yet',native_fit='not measured',full_model_output_oracle='pending',
        next_packet='packet 2: quantized model tokenizer/shape/operator contract and complete CPU oracle preparation; native parity requires separately authorized window'))
    assert passed
    print(json.dumps(dict(passed=passed,resident_bytes=resident,types=c['types'],scenario_32k=memory['scenario_32k']),indent=2))


if __name__=='__main__': main()
