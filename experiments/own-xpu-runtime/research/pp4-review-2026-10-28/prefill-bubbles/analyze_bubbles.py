#!/usr/bin/env python3
"""CPU-only prefill bubble screen (2026-10-28). Reads retained gzip traces only.

Writes bubbles.json next to this file. No GPU, build, service or model access.
busy = command_end - command_began as recorded by
engine/planning/rolling_provider/dedicated_prefill_pipeline.py (controller
monotonic clock; host-observed command duration, not GPU utilisation).
"""
import gzip, hashlib, json, statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parent
NAMES = ['stage0', 'stage1', 'stage2', 'provider']
RUNS = {
    'control_3plus1_262k_cuts_0_17_33_48': ('equal16-topology-screen/control-r1-evidence/control-output', 4),
    'equal16_3plus1_262k_cuts_0_16_32_48': ('equal16-topology-screen/equal16-r1-evidence/equal16-output', 4),
    'historical_two_slots_3plus1_pre_aot': ('dedicated-gate/two-slots-control-long-r1-evidence/run/output', 2),
    'historical_four_slots_3plus1_pre_aot': ('dedicated-gate/four-slots-long-r1-evidence/run/output', 4),
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def r3(x):
    return round(x, 3)


def pipeline(path, slots):
    iss, comp = {}, {}
    for line in gzip.open(path, 'rt'):
        e = json.loads(line)
        (iss if e['event'] == 'issued' else comp)[(e['actor'], e['chunk'])] = e
    n = max(c for _, c in iss) + 1
    t0 = min(e['monotonic_s'] for e in iss.values())
    tend = max(e['monotonic_s'] for e in comp.values())
    span = tend - t0
    out = dict(chunks=n, span_s=r3(span), actors={})
    for a in range(4):
        b = [comp[(a, k)]['command_end'] - comp[(a, k)]['command_began'] for k in range(n)]
        dec = []
        for w in range(10):
            lo, hi = t0 + span * w / 10, t0 + span * (w + 1) / 10
            dec.append(round(100 * sum(max(0, min(hi, comp[(a, k)]['command_end']) - max(lo, comp[(a, k)]['command_began']))
                                       for k in range(n)) / (hi - lo), 1))
        out['actors'][NAMES[a]] = dict(
            busy_s=r3(sum(b)), idle_in_span_s=r3(span - sum(b)), busy_pct_of_span=round(100 * sum(b) / span, 2),
            steady_mean_ms=round(1000 * st.mean(b[1:-1]), 2), first_chunk_ms=round(1000 * b[0], 1),
            first_start_s=r3(comp[(a, 0)]['command_began'] - t0), last_end_s=r3(comp[(a, n - 1)]['command_end'] - t0),
            busy_pct_by_decile=dec)
    lease_n, lease_w, gap = 0, 0.0, 0.0
    for k in range(1, n):
        prev = comp[(0, k - 1)]['monotonic_s']
        gap += iss[(0, k)]['monotonic_s'] - prev
        if k >= slots and comp[(3, k - slots)]['monotonic_s'] > prev:
            lease_n += 1; lease_w += comp[(3, k - slots)]['monotonic_s'] - prev
    ev = sorted([(comp[(a, k)]['command_began'], 1) for a in range(4) for k in range(n)] +
                [(comp[(a, k)]['command_end'], -1) for a in range(4) for k in range(n)])
    cur, last, hist = 0, ev[0][0], {}
    for t, d in ev:
        hist[cur] = hist.get(cur, 0) + t - last; cur += d; last = t
    out.update(stage0_lease_bound_chunks=lease_n, stage0_lease_wait_s=r3(lease_w),
               stage0_issue_after_previous_completion_s=r3(gap),
               busy_actor_seconds_by_count={str(k): r3(v) for k, v in sorted(hist.items())},
               mean_busy_actors=r3(sum(k * v for k, v in hist.items()) / (ev[-1][0] - ev[0][0])),
               drain_after_stage0_last_end_s=r3(tend - comp[(0, n - 1)]['command_end']),
               t0=t0, tend=tend)
    return out


def main():
    result = dict(schema='ownrt.prefill-bubbles-screen.v1', date='2026-10-28',
                  scope='CPU parse of retained host-wall traces; no GPU/build/service/model access',
                  busy_definition='command_end-command_began from dedicated_prefill_pipeline.py lines34 and52-62; '
                                  'host-observed command duration (socket, native host work and device work), not GPU utilisation',
                  runs={}, inputs={})
    for name, (d, slots) in RUNS.items():
        p = R / d / 'dedicated-prefill-pipeline.jsonl.gz'
        result['inputs'][str(p.relative_to(R))] = sha(p)
        run = pipeline(p, slots)
        run['transport_slots'] = slots
        dr = R / d / 'driver-result.json.gz'
        res = json.load(gzip.open(dr, 'rt')) if dr.exists() else {}
        if 'lifecycle_phases' in res:
            result['inputs'][str(dr.relative_to(R))] = sha(dr)
            lp = res['lifecycle_phases']; ttft = res['emitted_elapsed_seconds'][0]
            s0 = run['actors']['stage0']
            run['ttft_s'] = ttft
            run['request_s'] = res['scheduler_wall_seconds']
            run['ttft_decomposition_s'] = dict(
                request_start_to_first_issue=r3(run['t0'] - lp['request_start']),
                stage0_command_work=s0['busy_s'],
                stage0_inter_command_host=r3(s0['last_end_s'] - s0['busy_s']),
                drain_last_chunk_stage1_stage2_provider=run['drain_after_stage0_last_end_s'],
                prefill_end_to_first_token=r3(lp['request_start'] + ttft - run['tend']))
            run['busy_pct_of_ttft'] = {k: round(100 * v['busy_s'] / ttft, 2) for k, v in run['actors'].items()}
            run['non_stage0_work_overhead_s'] = r3(ttft - s0['busy_s'])
        del run['t0'], run['tend']
        result['runs'][name] = run
    c = result['runs']['control_3plus1_262k_cuts_0_17_33_48']['actors']
    e = result['runs']['equal16_3plus1_262k_cuts_0_16_32_48']['actors']
    cb = [c[k]['busy_s'] for k in NAMES]; eb = [e[k]['busy_s'] for k in NAMES]
    l16, l32 = cb[0] - eb[0], eb[2] - cb[2]
    oc = result['runs']['control_3plus1_262k_cuts_0_17_33_48']['non_stage0_work_overhead_s']
    s1 = (cb[1] + l16, eb[1] + l32)
    lo, hi = max(eb[0], s1[0]) + oc, max(eb[0], s1[1]) + oc
    ctl = result['runs']['control_3plus1_262k_cuts_0_17_33_48']['ttft_s']
    result['derived'] = dict(
        balanced_three_target_bound_s=r3(sum(cb[:3]) / 3),
        balanced_three_target_bound_plus_control_overhead_s=r3(sum(cb[:3]) / 3 + oc),
        all_four_actor_work_over_four_s=r3(sum(cb) / 4),
        layer16_prefill_total_s_from_stage0_difference=r3(l16),
        layer32_prefill_total_s_from_stage2_difference=r3(l32),
        single_boundary_0_16_33_48=dict(stage0_s=eb[0], stage1_s_range=[r3(s1[0]), r3(s1[1])], stage2_s=cb[2],
                                        ttft_estimate_s=[r3(lo), r3(hi)],
                                        ttft_reduction_pct=[round(100 * (1 - hi / ctl), 2), round(100 * (1 - lo / ctl), 2)],
                                        method='bottleneck stage total + control non-work overhead; stage1 by two cross-run differences'))
    # stage0 profile: retained site sums + retained copy of that run's pipeline trace
    prof = R / 'reference-one-row/router-tie-candidate/planner-policy/prefill-profile-r1-evidence/output/stage0/native/prefill-profile.jsonl.gz'
    pipe = HERE / 'evidence/profile-run-dedicated-prefill-pipeline.jsonl.gz'
    result['inputs'][str(prof.relative_to(R))] = sha(prof); result['inputs'][str(pipe.relative_to(R))] = sha(pipe)
    dur = {}
    for line in gzip.open(pipe, 'rt'):
        x = json.loads(line)
        if x['event'] == 'completed' and x['actor'] == 0:
            dur[x['chunk']] = 1000 * (x['command_end'] - x['command_began'])
    rows = [json.loads(line) for line in gzip.open(prof, 'rt')]
    full = [p for p in rows if 1 <= p['chunk'] <= 5]
    sums = [sum(v['ms'] for v in p['sites'].values()) for p in full]
    moe = sum(v['ms'] for p in full for k, v in p['sites'].items()
              if k.startswith('routed_gemv') or k in ('moe_combine', 'expert_gather'))
    cmd = [dur[p['chunk']] for p in full]
    result['stage0_profile_chunks_1_to_5'] = dict(
        command_mean_ms=round(st.mean(cmd), 2), drained_site_sum_mean_ms=round(st.mean(sums), 2),
        outside_sites_mean_ms=round(st.mean(cmd) - st.mean(sums), 2),
        outside_sites_pct=round(100 * (1 - sum(sums) / sum(cmd)), 2),
        routed_combine_gather_pct_of_sites=round(100 * moe / sum(sums), 2),
        note='outside-site time holds lookup, uploads, readback, bank swap and RPC (prefill-attribution-hook.txt); unattributed')
    # historical PP4 two-chunk wave (idea 9 "two-chunk-control-tested-winner")
    pp4p = R / 'candidate-long/matched-result.json'; result['inputs'][str(pp4p.relative_to(R))] = sha(pp4p)
    pp4 = json.loads(pp4p.read_text())['candidate_prefill_timing']
    result['pp4_two_chunk_wave_historical'] = dict(
        prefill_wall_s=r3(pp4['total_wall_s']), target_work_s=r3(pp4['target_work_wall_s']),
        draft_work_s=r3(pp4['draft_replay_work_wall_s']),
        target_only_s=r3(pp4['target_only_phase_wall_s']), mixed_s=r3(pp4['mixed_phase_wall_s']),
        draft_only_s=r3(pp4['draft_only_phase_wall_s']),
        mean_target_stages_busy=r3(pp4['target_work_wall_s'] / pp4['total_wall_s']),
        mean_target_stages_busy_in_target_phases=r3(pp4['target_work_wall_s'] /
                                                    (pp4['target_only_phase_wall_s'] + pp4['mixed_phase_wall_s'])),
        mechanism='prefill.py run_pipeline: ThreadPoolExecutor(max_workers=2), phase barriers, 6 phases per 2 chunks; '
                  'draft-only phases are pure target bubbles. Not the current 3+1 path.')
    # decode-window command occupancy (why equal16 decode lost is not stage work)
    dec = {}
    for name in ('control_3plus1_262k_cuts_0_17_33_48', 'equal16_3plus1_262k_cuts_0_16_32_48'):
        p = R / RUNS[name][0] / 'commands.jsonl.gz'; result['inputs'][str(p.relative_to(R))] = sha(p)
        iss, per, allt = {}, {}, []
        for line in gzip.open(p, 'rt'):
            x = json.loads(line); k = (x.get('stage'), x['sequence'])
            if x['event'] == 'issued': iss[k] = x['monotonic_s']
            elif x['event'] == 'completed' and k in iss:
                t = iss.pop(k); s = 'provider' if x.get('stage') is None else 'stage%d' % x['stage']
                per[s] = per.get(s, 0) + x['monotonic_s'] - t; allt += [t, x['monotonic_s']]
        dec[name] = dict(window_s=r3(max(allt) - min(allt)), command_sum_s={k: r3(v) for k, v in sorted(per.items())})
    result['decode_command_occupancy'] = dec
    scr = json.loads((R / 'equal16-topology-screen/screen.json').read_text())
    result['inputs']['equal16-topology-screen/screen.json'] = sha(R / 'equal16-topology-screen/screen.json')
    mv = {m['layer']: dict(kind=m['kind'], device_named_bytes=m['device_named_bytes'],
                           recurrent_state_bytes=m['by_category']['recurrent-state'],
                           ring_image_delta_bytes=m['ring_image_delta_bytes']) for m in scr['moves']}
    inc = {t['stage']: t['incumbent_bytes'] for t in scr['targets']}
    gib30 = 30 * 2 ** 30
    result['moved_layers'] = dict(layers=mv, qsa_layers_per_stage=[t['qsa_layers'] for t in scr['targets']],
        stream_bytes_per_row=40960, chunk_hidden_copy_bytes=256 * 40960,
        single_boundary_stage1_projection_bytes=inc[1] + mv[16]['device_named_bytes'],
        single_boundary_stage1_margin_to_30GiB=gib30 - inc[1] - mv[16]['device_named_bytes'],
        phase_split_stage2_projection_bytes=inc[2] + mv[32]['device_named_bytes'],
        phase_split_handoff_bytes_max=mv[16]['recurrent_state_bytes'] + mv[32]['recurrent_state_bytes'],
        note='accounting projections from screen.json incumbent census plus moved named allocations; not native admission')
    walls = {}
    for p in ('reference-one-row/router-tie-candidate/planner-policy/mtp-gate-r1-evidence/completed-dedicated/dedicated-output/terminal.json.gz',
              'reference-one-row/router-tie-candidate/planner-policy/prefill-profile-r1-evidence/output/terminal.json.gz',
              'equal16-topology-screen/control-r1-evidence/control-output/terminal.json.gz',
              'equal16-topology-screen/equal16-r1-evidence/equal16-output/terminal.json.gz'):
        walls[p] = r3(json.load(gzip.open(R / p, 'rt'))['wall_seconds'])
    result['device_time_evidence_wall_s'] = walls
    result['mechanism_citations'] = {
        'engine/planning/rolling_provider/dedicated_prefill_pipeline.py:17': 'slots=plan dedicated_prefill_slots (2 default; 4 in control)',
        'engine/planning/rolling_provider/dedicated_prefill_pipeline.py:90-93': 'one command per actor; actor a needs chunk k from a-1; '
            'stage0 admits k only if <slots leases and parity k%slots free',
        'engine/planning/rolling_provider/dedicated_prefill_pipeline.py:84-85': 'lease released only on provider full ACK',
        'engine/planning/rolling_provider/prefill.py:14-16': 'geometry allows only 2 or 4 slots (header 4096/8192)',
        'engine/planning/rolling_provider/prefill.py:175-206': 'PP4 two-chunk six-phase wave, max_workers=2'}
    result['missing_evidence'] = [
        'No GPU event timelines: busy is host-observed command time, not device utilisation.',
        'Native per-chunk prefill-timings.jsonl are empty for these runs (OP15 bypasses that logger); per-layer prefill cost on stage1/stage2 is not retained.',
        'Stage0 outside-site time (~31 ms/chunk: lookup, uploads, readback, bank swap, RPC) is unattributed.',
        'Cause of the equal16 decode loss is not established; decode for 0/16/33/48 is unmeasured.',
        'Cut 0/16/33/48 has no plan, admission census or run; its TTFT is an estimate.']
    sb = result['derived']['single_boundary_0_16_33_48']
    ctl_req = result['runs']['control_3plus1_262k_cuts_0_17_33_48']['request_s']
    e16 = result['runs']['equal16_3plus1_262k_cuts_0_16_32_48']['ttft_s']
    result['verdict'] = dict(
        bubbles_material=False,
        bottleneck='stage0 (layers 0-16 plus embedding/PLE lookup); its own command work sets TTFT',
        ideal_wall_perfect_fill_s=c['stage0']['busy_s'],
        actual_ttft_s=r3(ctl),
        pipeline_overhead_pct_of_ttft=round(100 * oc / ctl, 2),
        not_material_now=['more chunks in flight / wider waves (0 lease-bound chunks)',
                          'draft replay decoupling (provider 68% busy, only last chunk in drain)',
                          'host waits (0.027 s issue gaps, 0.622 s total stage0 handoff)'])
    result['proposal'] = dict(
        change='Prefill rebalancing: move GDN layer 16 off stage0 for prompt reading.',
        exact_because='contiguous cut change only; same per-layer arithmetic, chunk order and wire; equal16 passed the canonical '
                      'target/draft/pair/output proof with this kind of change',
        first_form=dict(cuts=[0, 16, 33, 48], ttft_estimate_s=sb['ttft_estimate_s'],
                        ttft_reduction_pct=sb['ttft_reduction_pct'], decode='unmeasured; final owner unchanged',
                        backlog='idea 1 next_topology_treatment.single_boundary_followup (new, unmeasured)'),
        fallback_form=dict(name='phase-specific cuts (backlog idea 12, new-unmeasured)',
                           prefill_cuts=[0, 16, 32, 48], decode_cuts=[0, 17, 33, 48],
                           measured_prefill_ttft_s=r3(e16),
                           derived_request_s=r3(e16 + ctl_req - ctl),
                           handoff_bytes_max=result['moved_layers']['phase_split_handoff_bytes_max'],
                           needs='owners holding both layer ranges, a GDN state handoff command, new native code'),
        limits=['integer cuts: balanced bound %.3f s work, about %.1f s TTFT' % (sum(cb[:3]) / 3, sum(cb[:3]) / 3 + oc),
                'stage0 carries extra non-layer work (equal16 at 16 layers each: %.2f vs %.2f/%.2f ms per chunk)'
                % (e['stage0']['steady_mean_ms'], e['stage1']['steady_mean_ms'], e['stage2']['steady_mean_ms']),
                'KV append order and QSA placement unchanged: both moved layers are GDN, four QSA layers per stage',
                'transport slots and activation buffers unchanged; stage1 ring image +31,421,460 B for layer 16 at depth 3',
                'stage1 projection 24,995,465,228 B (7.22 GB to 30 GiB) is accounting, not native admission'],
        prior_coverage='No DO-NOT-REPEAT row or closed result covers prefill cut rebalancing or phase-specific topology. '
                       'equal16 is a measured mixed result (prefill win, decode loss), not a closed negative.')
    result['device_test'] = dict(
        binary='native 339b75 (same as control), reference_route_tie_sort true, adapter plan unchanged',
        config='clone equal16-topology-screen/control-r1-evidence/control-config.json.gz (build receipt engine-build-reference-route-mtp-20261028-r1) '
               'changing only boundaries to [0,16,33,48] and a fresh exclusive output root; not the older candidate-config.json.gz (different build receipt)',
        plan='engine/tools/pipeline_driver.py CPU plan; read actual planner floors and allocation census before launch',
        gate='existing 3+1/262K 1677-prompt/32-output full-state gate: 2065 target, 73 draft sources, 1707 pairs, 32 outputs',
        timing='one first-inference 121854/512 run against the retained control (TTFT 250.842 s, all511 48.515 tok/s)',
        expected_device_wall_s=dict(gate=walls['reference-one-row/router-tie-candidate/planner-policy/mtp-gate-r1-evidence/'
                                                'completed-dedicated/dedicated-output/terminal.json.gz'],
                                    long512=[walls['equal16-topology-screen/equal16-r1-evidence/equal16-output/terminal.json.gz'],
                                             walls['equal16-topology-screen/control-r1-evidence/control-output/terminal.json.gz']]),
        control_repeatability='retained 3+1/262K runs: TTFT 250.742 s (aot-cold-gate/3plus1-262k-long512-r1-evidence/summary.json) '
                              'vs 250.842 s (control)')
    (HERE / 'bubbles.json').write_text(json.dumps(result, indent=1) + '\n')


if __name__ == '__main__':
    main()
