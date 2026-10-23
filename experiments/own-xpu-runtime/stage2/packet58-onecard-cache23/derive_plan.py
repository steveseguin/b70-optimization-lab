#!/usr/bin/env python3
"""Derive the re-partitioned device plan from packet182c's lifetime receipts (CPU only; read in place).

Coordinator ruling (one-card synthesis 1): driver allowance -> 671,088,640, device-owned bound ->
29,828,911,360, transient bounds 2,415,656,960 -> 784,567,808 (= 2.65x the measured live peak),
expert arena 21,552,729,600 -> 23,049,601,024, host backing +1,496,871,424. Every number below is
either a receipt value or an arithmetic consequence; the source receipt is named beside it.

Rules (any failure is a STOP: no build):
- the physical floor 32,000,000,000, the 1,500,000,000 device reserve and the 30,500,000,000 DRM
  guard are unchanged; the driver allowance is never below the measured lifetime driver overhead
  (DRM total-vram0 minus the census device total, max over every retained sample);
- every transient category bound stays >= its measured live peak in EVERY census;
- the fixed (non-transient) categories are unchanged and >= the census weights/KV/recurrent rows;
- allocate()/plan peaks after the arena growth fit the new bound; projected DRM after the growth
  fits the 30.5 GB guard, margin stated;
- the host admission grows by exactly the arena growth (full backing, packet58x rule).

Writes memory-plan.json. admission.json's `admission` block must equal the derived plan
(test_memory_plan.py checks it); nothing here lowers any allowance below a measurement.
"""
import hashlib, json, sys
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
CHAIN = ROOT / 'experiments/own-xpu-runtime/stage2/packet182c-chain/evidence/card0-182-a'
WINDOWS = ('KD', 'W2m', 'WS', 'WS128x', 'WS128')
FLOOR, RESERVE, DRM_GUARD = 32_000_000_000, 1_500_000_000, 30_500_000_000
OLD_DRIVER, NEW_DRIVER = 536_870_912, 671_088_640
OLD_ARENA, NEW_ARENA = 21_552_729_600, 23_049_601_024
OLD_BOUND = 29_963_128_848


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def drm_total(path):
    for line in Path(path).read_text().splitlines():
        if line.startswith('drm-total-vram0:'):
            value = line.split(':', 1)[1].strip()
            number, unit = value.split()
            return int(number) * {'KiB': 1024, 'MiB': 1024 ** 2}[unit]
    return None


def stop(message):
    print('STOP: ' + message, file=sys.stderr)
    raise SystemExit(2)


def main():
    old = json.loads((P / 'admission.json').read_text())
    old_adm = old.get('parent_admission_packet58x') or old['admission']
    old_cat = old_adm['device_categories']
    assert sum(old_cat.values()) == OLD_BOUND == old_adm['device_owned_bound_bytes']
    sources, census_rows, drm = {}, {}, []
    transient_peak = {}
    for w in WINDOWS:
        c = CHAIN / w / 'run/run/census.json'
        rows = json.loads(c.read_text())
        assert len(rows) == 1
        sources[str(c.relative_to(ROOT))] = sha(c)
        dev = [r for r in rows[0]['allocations'] if r['memory'] == 'device']
        if any(not r['live'] for r in dev):
            stop('non-live device census row in ' + w)
        by = {}
        for r in dev:
            by.setdefault((r['category'], r['lifetime']), []).append(r)
        total = sum(r['bytes'] for r in dev)
        if total != rows[0]['totals']['device']:
            stop('census total differs in ' + w)
        scratch = [r for r in by.get(('workspace', 'transaction'), []) if r['label'] == 'card0:operator-scratch']
        other_ws = [r for r in by.get(('workspace', 'transaction'), []) if r['label'] != 'card0:operator-scratch']
        transfer = [r for r in dev if r['lifetime'] == 'transfer']
        row = dict(device_total=total,
                   weights_process=sum(r['bytes'] for r in by.get(('weights', 'process'), [])),
                   arena=next(r['bytes'] for r in dev if r['label'] == 'card0:immutable-expert-cache'),
                   kv_request=sum(r['bytes'] for r in by.get(('KV', 'request'), [])),
                   recurrent_request=sum(r['bytes'] for r in by.get(('recurrent-state', 'request'), [])),
                   workspace_transaction=sum(r['bytes'] for r in by.get(('workspace', 'transaction'), [])),
                   operator_scratch=sum(r['bytes'] for r in scratch), other_workspace=sum(r['bytes'] for r in other_ws),
                   device_transfer_lifetime=sum(r['bytes'] for r in transfer), categories=sorted(set(k[0] for k in by)))
        census_rows[w] = row
        for f in sorted((CHAIN / w / 'run/run').rglob('drm-memory-*.txt')):
            v = drm_total(f)
            if v is None:
                continue  # before_load samples are empty (no client yet)
            drm.append(dict(window=w, sample=str(f.relative_to(CHAIN)), bytes=v))
            sources[str(f.relative_to(ROOT))] = sha(f)
    census_live = max(r['device_total'] for r in census_rows.values())
    if len({r['device_total'] for r in census_rows.values()}) != 1:
        stop('device census differs between windows')
    loaded = [d for d in drm if not d['sample'].endswith('drm-memory-end.txt')]
    drm_peak = max(d['bytes'] for d in loaded)
    driver_measured = drm_peak - census_live
    if driver_measured > NEW_DRIVER:
        stop(f'measured driver overhead {driver_measured} exceeds the new allowance {NEW_DRIVER}')
    if driver_measured <= OLD_DRIVER:
        print('note: measured driver overhead fits the old allowance too', file=sys.stderr)
    # transient measured peaks (identical in every census; take the max anyway)
    scratch_peak = max(r['operator_scratch'] for r in census_rows.values())
    other_ws_peak = max(r['other_workspace'] for r in census_rows.values())
    transfer_peak = max(r['device_transfer_lifetime'] for r in census_rows.values())
    transient_live_peak = max(r['workspace_transaction'] + r['device_transfer_lifetime'] for r in census_rows.values())
    fixed_old = {k: v for k, v in old_cat.items() if k not in ('control_transaction_bound', 'workspace_bound', 'transfer_bound', 'expert_cache_arena')}
    new_bound = FLOOR - RESERVE - NEW_DRIVER
    assert new_bound == 29_828_911_360
    transient_total = new_bound - 240 - sum(fixed_old.values()) - NEW_ARENA
    if transient_total != 784_567_808:
        stop(f'transient allowance derived as {transient_total}, ruling says 784,567,808')
    transient = dict(transfer_bound=old_cat['transfer_bound'],                 # 268,435,456 unchanged (no device transfer-lifetime row measured)
                     control_transaction_bound=402_653_184)                   # 1.5 x the single 256 MiB operator-scratch transaction buffer
    transient['workspace_bound'] = transient_total - transient['transfer_bound'] - transient['control_transaction_bound']
    checks = dict(transfer_bound=(transient['transfer_bound'], transfer_peak),
                  control_transaction_bound=(transient['control_transaction_bound'], scratch_peak),
                  workspace_bound=(transient['workspace_bound'], other_ws_peak))
    for k, (bound, peak) in checks.items():
        if bound < peak:
            stop(f'{k} {bound} below its measured peak {peak}')
    if sum(transient.values()) < transient_live_peak:
        stop('transient allowance below the measured live transient peak')
    new_cat = dict(fixed_old, expert_cache_arena=NEW_ARENA, **transient)
    new_sum = sum(new_cat.values())
    if new_sum + 240 != new_bound:
        stop(f'category sum {new_sum} + 240 != bound {new_bound}')
    # fixed categories vs census
    ws = census_rows['WS128']
    if new_cat['target_4k_bf16_kv_index'] != ws['kv_request'] or new_cat['target_recurrent'] != ws['recurrent_request']:
        stop('KV/recurrent census differs from the fixed categories')
    weights_fixed = new_cat['target_nonexpert'] + new_cat['expert_pointer_generation_tables'] + new_cat['async_publication_staging'] + new_cat['exact_half_decode_table']
    if weights_fixed < ws['weights_process'] - ws['arena']:
        stop('non-arena weights exceed their fixed categories')
    # peaks after growth
    plan_path = CHAIN / 'WS128/run/run/plan.json'
    mp = json.loads(plan_path.read_text())['memory_plan']
    sources[str(plan_path.relative_to(ROOT))] = sha(plan_path)
    memory_path = CHAIN / 'WS128/run/run/memory.json'
    native_peak = json.loads(memory_path.read_text())['peak_device_bytes_per_owner']
    sources[str(memory_path.relative_to(ROOT))] = sha(memory_path)
    growth = NEW_ARENA - OLD_ARENA
    planned_new = mp['request_and_workspace_bytes_per_card'][0] + mp['resident_weights_per_card'][0] + growth
    allocate_new = native_peak + growth
    drm_new = drm_peak + growth
    for name, value, bound in (('planned peak', planned_new, new_bound), ('allocate() peak', allocate_new, new_bound), ('DRM lifetime peak', drm_new, DRM_GUARD)):
        if value > bound:
            stop(f'{name} after growth {value} exceeds {bound}')
    window_path = CHAIN / 'WS128/window.json'
    wj = json.loads(window_path.read_text())
    sources[str(window_path.relative_to(ROOT))] = sha(window_path)
    host_old = wj['memory_admission']['required_bytes']
    assert host_old == old_adm['host_required_available_bytes'] == 98_990_252_032
    host_new = host_old + growth
    plan = dict(
        schema='packet58cache23.memory-plan.v1', device_executed=False,
        ruling='One-card synthesis 1 (2026-10-22): cache_cap max23 = 23,049,601,024 B; driver allowance -> 671,088,640; bound -> 29,828,911,360; '
               'transient bounds 2,415,656,960 -> 784,567,808 (= 2.65x the measured live peak); host backing +1.5 GB',
        physical_capacity_floor_bytes=dict(value=FLOOR, source='unchanged packet58x floor'),
        device_reserve_bytes=dict(value=RESERVE, source='unchanged packet58x reserve (never reduced)'),
        drm_guard_bytes=dict(value=DRM_GUARD, source='unchanged native after-load guard + supervisor (floor - reserve); never lowered'),
        driver_overhead_measured_bytes=dict(value=driver_measured, source=f'max DRM total-vram0 over {len(loaded)} loaded samples ({drm_peak}) minus the census device total ({census_live}); packet182c chain KD/W2m/WS/WS128x/WS128'),
        driver_allowance_bytes=dict(value=NEW_DRIVER, old=OLD_DRIVER, margin_over_measured=NEW_DRIVER - driver_measured, source='ruling; >= measured 0.60 GB (old 0.54 GB allowance was below the measurement)'),
        device_owned_bound_bytes=dict(value=new_bound, old=OLD_BOUND, source='floor - reserve - driver allowance'),
        expert_cache_arena_bytes=dict(value=NEW_ARENA, old=OLD_ARENA, growth=growth, aligned_256=NEW_ARENA % 256 == 0, growth_fraction=round(growth / OLD_ARENA, 6), source='ruling: 23,049,601,024 (+6.95 %)'),
        transient_measured=dict(operator_scratch_peak=scratch_peak, other_workspace_peak=other_ws_peak, device_transfer_lifetime_peak=transfer_peak,
                                live_transient_peak=transient_live_peak, source='workspace/transaction device rows of every chain census (identical in all five)'),
        transient_bounds=dict(old=dict(control_transaction_bound=old_cat['control_transaction_bound'], workspace_bound=old_cat['workspace_bound'], transfer_bound=old_cat['transfer_bound'], total=2_415_656_960),
                              new=dict(transient, total=sum(transient.values())),
                              ratio_to_live_peak=round(sum(transient.values()) / transient_live_peak, 3),
                              split_rule='transfer_bound unchanged (no device transfer-lifetime allocation measured; an allowance is never reduced below a measurement, here 0); '
                                         'control_transaction_bound = 1.5 x the 268,435,456-byte operator-scratch transaction buffer; workspace_bound = remainder, '
                                         '>= 4x the other 1,952 workspace rows (gemv-workspace + controls/scores/snapshots)',
                              total_rule='bound - 240 B category margin - fixed categories - arena (the ruling total 784,567,808)'),
        fixed_categories=dict(fixed_old, source='unchanged packet58x categories; census WS128 KV/recurrent equal them exactly; non-arena weights 5,818,151,424 <= 5,819,331,072 fixed'),
        device_categories=new_cat, device_category_sum_bytes=new_sum, device_category_margin_bytes=new_bound - new_sum, physical_margin_bytes=FLOOR - new_bound - NEW_DRIVER - RESERVE,
        peaks_after_growth=dict(planned_peak_bytes=planned_new, planned_source='WS128 plan.json request_and_workspace 475,217,652 + resident_weights 27,366,424,576 + growth',
                                allocate_peak_bytes=allocate_new, allocate_source='WS128 memory.json peak_device_bytes_per_owner 27,841,904,372 + growth',
                                bound_margin_bytes=new_bound - allocate_new,
                                drm_projection_bytes=drm_new, drm_source=f'lifetime DRM peak {drm_peak} + growth', drm_guard_margin_bytes=DRM_GUARD - drm_new),
        host=dict(required_available_old=host_old, required_available_new=host_new, growth=growth, host_bound_new=old_adm['host_bound_bytes'] + growth,
                  source='WS128 window.json memory_admission.required_bytes (= packet58x admission) + full backing for the arena growth; 8 GiB reserve unchanged; '
                         'MemAvailable at the 182c WS128 start ' + str(wj['memory_admission']['available_bytes'])),
        census=census_rows, drm_samples=drm, sources=sources)
    (P / 'memory-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    print(json.dumps(dict(passed=True, bound=new_bound, driver_measured=driver_measured, transient=transient, allocate_peak=allocate_new, drm_projection=drm_new,
                          drm_margin=DRM_GUARD - drm_new, host_required=host_new, drm_samples=len(drm))))


if __name__ == '__main__':
    main()
