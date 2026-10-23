#!/usr/bin/env python3
"""Packet58-onecard-cache23 harness delta over the packet182 copy (Python/JSON; exact counted edits).

- screen/views.py: the view dimension is cache capacity (A = max, B = max23); kernel foreground I/O
  (spin-kio) fixed in every row; ALLOCATION_BYTES 23,049,601,024; USABLE per capacity.
- screen/suite_driver.py: --cache-bytes = the allocation; the boundary record must carry the view's
  capacity, the allocation and the usable bytes; verify_lookup_views checks kernel I/O in every view.
- screen/compare_bracket.py: max/max23 order + the s58c23 decision (screen winner, chain rule, kill rules).
- screen/mechanism.py: fills/token, MB/token and the miss-read regression per view (both views reported).
- screen/argument_gate.py, screen/startup_gate.py, screen/queue_runner.py, screen/window.py: literals,
  plan seconds, watchdog 3600.
- admission.json + memory_plan.py: the re-partitioned device plan (derive_plan.py -> memory-plan.json).
- tests: policy/bracket/capacity/admission tests follow the new policy (no stale carried failures).
- root chain harness (views.py, suite_driver.py, runtime-selection.json): the arena literal, so a
  later derived chain allocates the same arena (`--cache-bytes 23049601024 --cache-cap max|max23`).
Every literal changed is listed in README.md.
"""
import json
from pathlib import Path

P = Path(__file__).resolve().parent
ARENA, MAX = 23049601024, 21552729600
HOST_OLD, HOST_NEW = 98990252032, 100487123456
LOG = []


def sub(rel, old, new, count=1):
    f = P / rel
    text = f.read_text()
    assert text.count(old) == count, (rel, old[:80], text.count(old))
    f.write_text(text.replace(old, new))
    LOG.append(dict(file=rel, old=old[:120], new=new[:120], count=count))


def views():
    rel = 'screen/views.py'
    (P / rel).write_text('''"""Capacity changes between views; maintenance and kernel foreground I/O stay fixed (packet58-cache23)."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
VIEWS=('resident','smoke')
CAPACITIES=('max','max23')
DEFAULT_MAINTENANCE='overlap'
FOREGROUND='spin-kio'
# One arena per load (every view keeps the maximum allocation; the cap limits use, packet58x design).
ALLOCATION_BYTES=23049601024
USABLE={'max':21552729600,'max23':23049601024}
MAX_BYTES=ALLOCATION_BYTES
def validate(view):
    if view not in VIEWS:raise ValueError('unsupported capacity bracket view')
    row=json.loads((P/'selections/tile16.json').read_text())
    if row!=dict(schema='packet49d.selection.v1',decision=None,choices=dict(
        route='route-exp32-rank4',recurrence='rows4-shared',hc='production',down='down-tile16')):
        raise ValueError('immutable tile16 selection changed')
    return row
def selection(view):
    if view in CAPACITIES or view=='tile16':view='resident'
    validate(view);return P/'selections/tile16.json'
def digest(view):return hashlib.sha256(selection(view).read_bytes()).hexdigest()
def bracket(candidate):
    """(label, capacity) rows; the native bracket table also carries the fixed spin-kio arm."""
    if candidate=='smoke':return [('S0','max23')]
    if candidate!='resident':raise ValueError('max23 candidate required')
    # packet58-cache23: A = packet182c record line (max = 21,552,729,600 usable); B = max23 (the full 23,049,601,024-byte arena).
    return [('A0','max'),('B0','max23'),('A1','max'),('B1','max23'),('A2','max')]
def write_table(path,candidate,maintenance=DEFAULT_MAINTENANCE):
    if maintenance not in ('serial','overlap'):raise ValueError('unsupported maintenance')
    rows=bracket(candidate)
    path.write_text(''.join(f'{label} {selection(cap)} {digest(cap)} {maintenance} {cap} {FOREGROUND}\\n' for label,cap in rows))
    return rows
''')
    LOG.append(dict(file=rel, old='packet182 views (spin/spin-kio arms, MAX_BYTES 21552729600)', new='capacity views max/max23, ALLOCATION_BYTES 23049601024, USABLE'))


def suite_driver():
    rel = 'screen/suite_driver.py'
    sub(rel, 'from views import VIEWS,selection,digest,bracket,write_table,DEFAULT_MAINTENANCE,MAX_BYTES',
        'from views import VIEWS,selection,digest,bracket,write_table,DEFAULT_MAINTENANCE,ALLOCATION_BYTES,USABLE,FOREGROUND')
    sub(rel, '''    for label,view in bracket(candidate):
        boundary=read(out/'run'/label/'boundary.json')
        require(boundary.get('hc')=='p60fusion' and boundary.get('lookups')=='resident' and boundary.get('wait_policy')=='spin'
                and boundary.get('bracket_arm')==view and boundary.get('foreground_io')==('kernel' if view=='spin-kio' else 'copy'),'lookup/composition boundary differs')''',
        '''    for label,cap in bracket(candidate):
        boundary=read(out/'run'/label/'boundary.json')
        require(boundary.get('hc')=='p60fusion' and boundary.get('lookups')=='resident' and boundary.get('wait_policy')=='spin'
                and boundary.get('bracket_arm')==FOREGROUND and boundary.get('foreground_io')=='kernel'
                and boundary.get('cache_cap')==cap and boundary.get('cache_usable_bytes')==USABLE[cap],'lookup/composition/capacity boundary differs')''')
    sub(rel, '''    for label,view in bracket(candidate):
        boundary=read(out/'run'/label/'boundary.json')
        require(boundary.get('passed') is True and boundary.get('selection_sha256')==digest(view)
                and boundary.get('cache_maintenance')==maintenance and boundary.get('cache_cap')=='max'
                and boundary.get('cache_allocation_bytes')==MAX_BYTES and boundary.get('cache_started_empty') is True''',
        '''    for label,view in bracket(candidate):
        boundary=read(out/'run'/label/'boundary.json')
        require(boundary.get('passed') is True and boundary.get('selection_sha256')==digest(view)
                and boundary.get('cache_maintenance')==maintenance and boundary.get('cache_cap')==view
                and boundary.get('cache_allocation_bytes')==ALLOCATION_BYTES and boundary.get('cache_usable_bytes')==USABLE[view]
                and boundary.get('cache_started_empty') is True''')
    sub(rel, '''        # packet176: mechanism readout is kept on every outcome, including a loss.
        # The foreground-io identity of every view is enforced by verify_lookup_views first.
        import mechanism
        try:readout=mechanism.readout(out/'run',[v['label'] for v in views],[e['prompt_id'] for e in manifest['prompts']],decision['candidate_beats_all_controls'])
        except (OSError,ValueError,KeyError,TypeError,ZeroDivisionError) as error:readout=dict(available=False,error=f'{type(error).__name__}: {error}')
        decision=dict(decision,mechanism_readout=readout)''',
        '''        # packet176: mechanism readout is kept on every outcome, including a loss.
        # The capacity identity of every view is enforced by verify_lookup_views first.
        import mechanism
        try:readout=mechanism.readout(out/'run',[v['label'] for v in views],[e['prompt_id'] for e in manifest['prompts']],decision['candidate_beats_all_controls'])
        except (OSError,ValueError,KeyError,TypeError,ZeroDivisionError) as error:readout=dict(available=False,error=f'{type(error).__name__}: {error}')
        # packet58-cache23: the screen/chain/kill decision on every outcome (compare_bracket.s58c23_decision).
        from compare_bracket import s58c23_decision
        decision=dict(decision,mechanism_readout=readout,s58c23_decision=s58c23_decision(decision,readout))''')
    sub(rel, "        '--cache-bytes',str(MAX_BYTES),'--cache-cap','max',", "        '--cache-bytes',str(ALLOCATION_BYTES),'--cache-cap','max',")


def compare():
    rel = 'screen/compare_bracket.py'
    sub(rel, "        if v.get('view')!=('spin-kio' if i%2 else 'spin'):\n            raise ValueError('lookup view order differs')",
        "        if v.get('view')!=('max23' if i%2 else 'max'):\n            raise ValueError('capacity view order differs')")
    sub(rel, "spin_beats_each_warm_control=neutral,", "max23_beats_each_warm_control=neutral,")
    sub(rel, "readiness_policy='packet182 (re-bracket of packet176): both kernel-foreground-io views >=+0.5% over every warm spin-parent control; the win-path chain additionally needs >=+2%',",
        "readiness_policy='packet58-cache23: both max23 views >=+0.5% over every warm max (packet182c record line) control, drift <=3%, 60/60 exact; chain rule >=+2% over every max view and >=36.645',")
    (P / rel).write_text((P / rel).read_text() + '''

# packet58-cache23 decision (coordinator ruling, one-card synthesis 1). Kept on every outcome.
RECORD_TOK_S = 35.926720          # packet182c chain WS128, LocalMaxxing cmvjejvoi03qcrf0138emu5a6
CHAIN_BAR_TOK_S = 36.645          # +2 % over the record
WARM_FLOOR_TOK_S = 35.2           # below this the host is disturbed (A arm = the 35.93 record line)
FILL_REDUCTION_REQUIRED = 0.08    # max23 fills/token must be >= 8 % below max

def s58c23_decision(comparison, readout):
    """screen winner iff both max23 >= 1.005 x every warm max, 60/60 exact (compare() raised otherwise),
    drift <= 3 %; chain rule iff also >= 1.02 x EVERY max view (A0 included) and >= 36.645 tok/s.
    Kill rules: DRM > 30.5 GB is the native/supervisor guard (the window refuses before this runs);
    max23 fills/token not >= 8 % below max -> capacity closed at 23 GB; warm max < 35.2 or drift > 3 %
    -> host disturbed, no automatic rerun. Fills/token, MB/token and the miss-read regression are
    reported for both views from the mechanism readout."""
    rates = [Decimal(str(r)) for r in comparison['rates']]
    maxes, max23s = rates[0::2], rates[1::2]
    warm = rates[2::2]
    drift = Decimal(str(comparison['control_drift_fraction']))
    kills = []
    if drift > Decimal('.03'):
        kills.append('control drift > 3 %: host disturbed; report, no automatic rerun')
    if any(a < Decimal(str(WARM_FLOOR_TOK_S)) for a in warm):
        kills.append(f'warm max view below {WARM_FLOOR_TOK_S} tok/s: host disturbed; report, no automatic rerun')
    per_view = {}
    views = (readout or {}).get('views') or {}
    for label, v in views.items():
        per_view[label] = dict(fills_per_token=v.get('fills_per_token'), fill_mb_per_token=v.get('fill_mb_per_token'),
                               miss_read_regression=v.get('miss_read_regression'))
    fills_ok = None
    a_fills = [views[l]['fills_per_token'] for l in ('A1', 'A2') if l in views and views[l].get('fills_per_token') is not None]
    b_fills = [views[l]['fills_per_token'] for l in ('B0', 'B1') if l in views and views[l].get('fills_per_token') is not None]
    if a_fills and b_fills:
        fills_ok = all(b <= (1 - FILL_REDUCTION_REQUIRED) * a for b in b_fills for a in a_fills)
        if not fills_ok:
            kills.append('max23 fills/token not >= 8 % below max: capacity closed at 23 GB regardless of speed')
    else:
        kills.append('fills/token unavailable for both arms: readout failed; report')
    screen_winner = bool(comparison['candidate_beats_all_controls']) and not kills
    chain = screen_winner and all(b >= a * Decimal('1.02') for a in maxes for b in max23s) and all(b >= Decimal(str(CHAIN_BAR_TOK_S)) for b in max23s)
    return dict(schema='packet58cache23.decision.v1', screen_winner=screen_winner, chain_rule=chain, capacity_closed_at_23gb=fills_ok is False,
                kill_rules_fired=kills, record_tok_s=RECORD_TOK_S, chain_bar_tok_s=CHAIN_BAR_TOK_S, warm_floor_tok_s=WARM_FLOOR_TOK_S,
                fill_reduction_required=FILL_REDUCTION_REQUIRED, max_views=list(map(float, maxes)), max23_views=list(map(float, max23s)),
                minimum_gain_vs_every_max_view=float(min(max23s) / max(maxes) - 1), fills_reduced_8pct=fills_ok, per_view=per_view,
                drm_guard='native after-load + supervisor refuse DRM total-vram0 > 30,500,000,000 B before any view (unchanged, never lowered)',
                rule='screen winner iff both max23 >= 1.005 x every warm max, 60/60 exact, drift <= 3 %; chain iff also >= 1.02 x every max view and >= 36.645; '
                     'no automatic rerun on any kill')
''')
    LOG.append(dict(file=rel, old='-', new='s58c23_decision appended'))


def mechanism():
    rel = 'screen/mechanism.py'
    sub(rel, "        r['_fill_mb'] = (c['fill_bytes_total'] - p['fill_bytes_total']) / 1e6 if same_view else None",
        "        r['_fill_mb'] = (c['fill_bytes_total'] - p['fill_bytes_total']) / 1e6 if same_view else None\n"
        "        r['_fills'] = (c.get('fills_total', 0) - p.get('fills_total', 0)) if same_view else None")
    sub(rel, "        fill_tokens=len(filled), fill_mb_per_token=round(sum(r['_fill_mb'] or 0 for r in gen) / len(gen), 3),",
        "        fill_tokens=len(filled), fill_mb_per_token=round(sum(r['_fill_mb'] or 0 for r in gen) / len(gen), 3),\n"
        "        fills_per_token=round(sum(r['_fills'] or 0 for r in gen) / len(gen), 3),\n"
        "        miss_read_regression=miss_read_regression(gen),")
    sub(rel, "def _copies(r):", '''def miss_read_regression(gen):
    """packet58-cache23: the miss-read price. Wall outside the transfer window of UNFILLED decode tokens
    regressed on the NEXT fill boundary's MB (a proxy of the token's own miss intensity; packet182 control
    slope), and of filled tokens on their own fill MB. ms per MB of fill bytes; intercept in ms."""
    unfilled = [r for r in gen if r['_fill_mb'] == 0 and r['_next_fill_mb'] is not None]
    filled = [r for r in gen if r['_fill_mb'] is not None and r['_fill_mb'] > 0]
    other = lambda r: r['wall_ms'] - r['transfer_wall_ms']
    u_slope, u_int = _fit([r['_next_fill_mb'] for r in unfilled], [other(r) for r in unfilled])
    f_slope, f_int = _fit([r['_fill_mb'] for r in filled], [other(r) for r in filled])
    return dict(unfilled_tokens=len(unfilled), unfilled_ms_per_next_fill_mb=u_slope, unfilled_intercept_ms=u_int,
                filled_tokens=len(filled), filled_ms_per_fill_mb=f_slope, filled_intercept_ms=f_int,
                mean_fill_mb_per_filled_token=round(st.mean(r['_fill_mb'] for r in filled), 3) if filled else None)


def _copies(r):''')


def argument_gate():
    rel = 'screen/argument_gate.py'
    sub(rel, "                assert cmd[cmd.index('--cache-bytes')+1] == str(V.MAX_BYTES)", "                assert cmd[cmd.index('--cache-bytes')+1] == str(V.ALLOCATION_BYTES)\n                assert cmd[cmd.index('--cache-cap')+1] == 'max'")
    sub(rel, "                assert [x.split()[4] for x in bt]==['max']*len(V.bracket(candidate))\n                assert [x.split()[5] for x in bt]==[v for _,v in V.bracket(candidate)]",
        "                assert [x.split()[4] for x in bt]==[cap for _,cap in V.bracket(candidate)]\n                assert [x.split()[5] for x in bt]==[V.FOREGROUND]*len(V.bracket(candidate))")
    sub(rel, "    assert tag == 'v5', 'packet182 proposes only the one-load v5 row'", "    assert tag == 'v5', 'packet58-cache23 proposes only the one-load v5 row'")
    sub(rel, "            source='endpoint-free MemAvailable measured at the 2026-10-22 packet181 window '",
        "            source='endpoint-free MemAvailable measured at the 2026-10-22 packet181/182 windows (182c WS128 start: 120,821,522,432 B) '")


def startup_gate():
    sub('screen/startup_gate.py', "receipt['cache_allocation_bytes']==21552729600", "receipt['cache_allocation_bytes']==V.ALLOCATION_BYTES")
    sub('screen/startup_gate.py', "from views import P,VIEWS,write_table", "from views import P,VIEWS,write_table\nimport views as V")
    sub('screen/startup_gate.py', "        for view in VIEWS[1:]:", "        for view in VIEWS:")


def queue_and_window():
    rel = 'screen/queue_runner.py'
    sub(rel, "planned_arm_seconds=[600,900] if view=='smoke' else [1200,1800], planned_bracket_seconds=[600,900] if view=='smoke' else [1200,1800], watchdog_seconds=7200, view_order=bracket(view), bracket_model_seconds=1560,",
        "planned_arm_seconds=[600,900] if view=='smoke' else [700,1200], planned_bracket_seconds=[600,900] if view=='smoke' else [700,1200], watchdog_seconds=3600, view_order=bracket(view), bracket_model_seconds=1200,")
    sub('screen/window.py', "CONFIG = {'K1': (20, 600), 'WSCREEN': (1560, 7200)}", "CONFIG = {'K1': (20, 600), 'WSCREEN': (1200, 3600)}")


def admission_and_plan():
    f = P / 'admission.json'
    old = json.loads(f.read_text())
    plan = json.loads((P / 'memory-plan.json').read_text())
    parent = old['admission']
    new = dict(parent)
    new.update(schema='packet58cache23.admission.v1', device_executed=False,
               device_categories=plan['device_categories'], cache_bytes=plan['expert_cache_arena_bytes']['value'],
               usable_cache_bytes=dict(max=MAX, max23=ARENA), old_cache_bytes=18000000000, extra_cache_bytes=ARENA - 18000000000,
               driver_allowance_bytes=plan['driver_allowance_bytes']['value'], driver_overhead_measured_bytes=plan['driver_overhead_measured_bytes']['value'],
               device_owned_bound_bytes=plan['device_owned_bound_bytes']['value'], device_category_margin_bytes=plan['device_category_margin_bytes'],
               physical_bound_with_driver_bytes=plan['device_owned_bound_bytes']['value'] + plan['driver_allowance_bytes']['value'],
               host_required_available_bytes=plan['host']['required_available_new'], host_bound_bytes=plan['host']['host_bound_new'],
               lifetime_proof=dict(source='packet182c chain KD/W2m/WS/WS128x/WS128 (2026-10-22): 5 censuses, 81 loaded DRM samples, plan.json, memory.json, window.json',
                                   drm_peak_bytes=plan['drm_samples'] and max(d['bytes'] for d in plan['drm_samples'] if not d['sample'].endswith('end.txt')),
                                   census_device_bytes=plan['census']['WS128']['device_total'], live_transient_peak_bytes=plan['transient_measured']['live_transient_peak'],
                                   peaks_after_growth=plan['peaks_after_growth'], memory_plan='memory-plan.json'),
               transient_policy='Re-partitioned against the measured lifetime: transfer 256 MiB unchanged, control transaction 384 MiB (1.5x operator-scratch), '
                                'workspace 113,479,168 (>= 4x the other workspace rows); every bound >= its measured peak; the 1.5 GB reserve and the 30.5 GB DRM guard unchanged; '
                                'the driver allowance raised to 671,088,640 (measured 604,827,916). Fills write inside the one arena.',
               windows=parent['windows'])
    assert sum(new['device_categories'].values()) + 240 == new['device_owned_bound_bytes']
    assert new['host_required_available_bytes'] == HOST_NEW
    out = dict(admission=new, parent_admission_packet58x=parent, **{k: v for k, v in old.items() if k != 'admission'})
    f.write_text(json.dumps(out, indent=2) + '\n')
    LOG.append(dict(file='admission.json', old='packet58x admission block', new='packet58cache23.admission.v1 (parent kept as parent_admission_packet58x)'))
    rel = 'memory_plan.py'
    sub(rel, "        budget['device_margin_bytes']=32_000_000_000-budget['device_owned_bound_bytes']-budget['driver_allowance_bytes']-1_500_000_000",
        "        # packet58-cache23: the bound is the exact physical remainder (floor - reserve - driver); the 240-byte\n"
        "        # margin sits between the category sum and the bound (memory-plan.json).\n"
        "        budget['physical_margin_bytes']=32_000_000_000-budget['device_owned_bound_bytes']-budget['driver_allowance_bytes']-1_500_000_000\n"
        "        require(budget['physical_margin_bytes']>=0,'device bound exceeds the physical floor')\n"
        "        budget['device_margin_bytes']=budget['device_owned_bound_bytes']-sum(budget['device_categories'].values())\n"
        "        require(budget['device_margin_bytes']==ADMISSION['device_category_margin_bytes'],'device category margin differs from the admitted plan')\n"
        "        require(budget['driver_allowance_bytes']>=ADMISSION['driver_overhead_measured_bytes'],'driver allowance below the measured lifetime overhead')")
    sub(rel, "PUBLICATION_DEVICE_BYTES=1179648\nEXTRA_HOST_BYTES=32*1024**2+PUBLICATION_DEVICE_BYTES+ADMISSION['extra_cache_bytes']+524288",
        "PUBLICATION_DEVICE_BYTES=1179648\nEXTRA_HOST_BYTES=32*1024**2+PUBLICATION_DEVICE_BYTES+ADMISSION['extra_cache_bytes']+524288\nUSABLE_CACHE_BYTES=dict(ADMISSION['usable_cache_bytes'])")
    sub(rel, "        budget['caveat']='One maximum allocation in every view; 18GB limits use, never admission. Live census, driver occupancy and host stops required.'",
        "        budget['caveat']='One 23,049,601,024-byte allocation in every view; max (21,552,729,600) and max23 limit use, never admission. Live census, driver occupancy and host stops required.'")


def tests():
    sub('test_resident.py', "            self.assertEqual(b['device_categories']['expert_cache_arena'],21552729600)\n            self.assertEqual(b['host_bound_bytes'],90400317440)\n            self.assertEqual(b['host_required_available_bytes'],98990252032)",
        "            self.assertEqual(b['device_categories']['expert_cache_arena'],23049601024)\n            self.assertEqual(b['host_bound_bytes'],91897188864)\n            self.assertEqual(b['host_required_available_bytes'],100487123456)")
    sub('test_admission58e.py', "12*1024**3 if name.startswith('K1') else 98990252032", "12*1024**3 if name.startswith('K1') else 100487123456")
    sub('screen/test_admission58e.py', "self.assertEqual(M.window_plan('WS128')['host_required_available_bytes'], 98990252032)", "self.assertEqual(M.window_plan('WS128')['host_required_available_bytes'], 100487123456)")
    sub('screen/test_async_policy.py', "            self.assertEqual(p['host_required_available_bytes'],98990252032)", "            self.assertEqual(p['host_required_available_bytes'],100487123456)")
    sub('screen/test_async_policy.py', "        self.assertEqual(V.bracket('smoke'),[('S0','resident')])\n        self.assertEqual([v for _,v in V.bracket('resident')],['mapped','resident','mapped','resident','mapped'])\n        self.assertEqual(V.digest('mapped'),V.digest('resident'))",
        "        self.assertEqual(V.bracket('smoke'),[('S0','max23')])\n        self.assertEqual([v for _,v in V.bracket('resident')],['max','max23','max','max23','max'])\n        self.assertEqual(V.digest('max'),V.digest('max23'))")
    rel = 'screen/test_bracket.py'
    sub(rel, "            D.save(folder/'boundary.json',dict(passed=True,cache_maintenance=V.DEFAULT_MAINTENANCE,cache_cap=\"max\",hc=\"p60fusion\",lookups=view,cache_allocation_bytes=V.MAX_BYTES,cache_started_empty=True,selection_sha256=V.digest(view),allocation_ids_preserved=True,",
        "            D.save(folder/'boundary.json',dict(passed=True,cache_maintenance=V.DEFAULT_MAINTENANCE,cache_cap=view,hc=\"p60fusion\",lookups='resident',wait_policy='spin',bracket_arm=V.FOREGROUND,foreground_io='kernel',cache_allocation_bytes=V.ALLOCATION_BYTES,cache_usable_bytes=V.USABLE[view],cache_started_empty=True,selection_sha256=V.digest(view),allocation_ids_preserved=True,")
    sub(rel, "            D.save(folder/'lookup-backing.json',dict(resident=view=='resident',copies=dict(enabled=True,bytes=29321610240,tensors=[dict(source_sha256='a'*64,resident_sha256='a'*64)])))",
        "            D.save(folder/'lookup-backing.json',dict(resident=True,copies=dict(enabled=True,bytes=29321610240,tensors=[dict(source_sha256='a'*64,resident_sha256='a'*64)])))")
    sub(rel, "                interval=.04\n", "                interval=.04 if view=='max' else .039   # synthetic rates: B faster than A; never device data\n")
    sub(rel, "            for key,value in (('selection_sha256','bad'),('selection_sha256','mapped'),('cache_cap','18GB'),",
        "            for key,value in (('selection_sha256','bad'),('selection_sha256','mapped'),('cache_cap','18GB'),('cache_cap','max'),('cache_usable_bytes',21552729600),('cache_allocation_bytes',21552729600),")
    (P / 'screen/test_capacity.py').write_text('''"""packet58-cache23 capacity policy tests (CPU; no device data)."""
import json,tempfile,unittest
from pathlib import Path
import device_memory as D
import memory_plan as M
import views as V
P=Path(__file__).resolve().parent


class Capacity(unittest.TestCase):
    def test_maximum_retains_every_allowance(self):
        p=M.window_plan('WSCREEN');plan=json.loads((P/'memory-plan.json').read_text()) if (P/'memory-plan.json').exists() else json.loads((P.parent/'memory-plan.json').read_text())
        self.assertEqual(sum(p['device_categories'].values())+240,p['device_owned_bound_bytes'])
        self.assertEqual(p['device_categories'],plan['device_categories'])
        self.assertEqual(p['device_categories']['expert_cache_arena'],V.ALLOCATION_BYTES)
        self.assertEqual(V.ALLOCATION_BYTES,23049601024);self.assertEqual(V.ALLOCATION_BYTES%256,0)
        self.assertEqual(V.ALLOCATION_BYTES-V.USABLE['max'],1496871424)
        self.assertEqual(p['device_margin_bytes'],240);self.assertEqual(p['physical_margin_bytes'],0)
        self.assertEqual(p['device_owned_bound_bytes'],32_000_000_000-1_500_000_000-p['driver_allowance_bytes'])
        self.assertEqual(p['driver_allowance_bytes'],671088640)
        self.assertGreaterEqual(p['driver_allowance_bytes'],plan['driver_overhead_measured_bytes']['value'])
        t=plan['transient_measured'];c=p['device_categories']
        self.assertGreaterEqual(c['control_transaction_bound'],t['operator_scratch_peak'])
        self.assertGreaterEqual(c['workspace_bound'],t['other_workspace_peak'])
        self.assertGreaterEqual(c['transfer_bound'],t['device_transfer_lifetime_peak'])
        self.assertEqual(c['control_transaction_bound']+c['workspace_bound']+c['transfer_bound'],784567808)
        self.assertEqual(c['target_4k_bf16_kv_index'],116391936);self.assertEqual(c['target_recurrent'],59019280)
        self.assertLessEqual(plan['peaks_after_growth']['allocate_peak_bytes'],p['device_owned_bound_bytes'])
        self.assertLessEqual(plan['peaks_after_growth']['drm_projection_bytes'],30_500_000_000)

    def test_reserve_driver_and_guard_never_reduced(self):
        p=M.window_plan('WSCREEN')
        self.assertEqual(p['device_reserve_bytes'],1_500_000_000)
        self.assertGreater(p['driver_allowance_bytes'],536870912)
        self.assertTrue(D.observe([],Path('/nonexistent'))['passed'])
        self.assertEqual(D.observe([],Path('/nonexistent'))['reserve_bytes'],1_500_000_000)

    def test_admission_boundary(self):
        p=M.plan();required=p['host_required_available_bytes']
        self.assertEqual(required,100487123456)
        self.assertTrue(M.admit({'MemAvailable':required},p)['passed'])
        with self.assertRaises(ValueError):M.admit({'MemAvailable':required-1},p)
        self.assertEqual(M.window_plan('K1')['host_required_available_bytes'],12*1024**3)

    def test_fixed_maintenance_and_capacity_rows(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'views.tsv'
            for mode in ('serial','overlap'):
                V.write_table(p,'resident',mode)
                rows=[line.split() for line in p.read_text().splitlines()]
                self.assertEqual([r[0] for r in rows],['A0','B0','A1','B1','A2'])
                self.assertEqual([r[3] for r in rows],[mode]*5)
                self.assertEqual([r[4] for r in rows],['max','max23','max','max23','max'])
                self.assertEqual([r[5] for r in rows],['spin-kio']*5)
                self.assertEqual(len({r[1] for r in rows}),1);self.assertEqual(len({r[2] for r in rows}),1)
            with self.assertRaises(ValueError):V.write_table(p,'resident','unknown')
            with self.assertRaises(ValueError):V.bracket('mapped')

    def test_smoke_and_every_v5_view_default_to_overlap(self):
        self.assertEqual(V.DEFAULT_MAINTENANCE,'overlap')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'views.tsv'
            for candidate in ('smoke','resident'):
                V.write_table(p,candidate)
                rows=[line.split() for line in p.read_text().splitlines()]
                self.assertEqual([r[3] for r in rows],['overlap']*len(V.bracket(candidate)))
                self.assertEqual([r[4] for r in rows],[cap for _,cap in V.bracket(candidate)])

    def test_measured_live_accounting_bounds(self):
        import window as W
        p=M.plan();host=p['host_categories'];pinned=host['pinned_packed_experts']
        shadow=host['gpuactive_shadow_bound'];file=host['file_backed_nonexpert_and_lookup_bound']
        anon=p['host_bound_bytes']-pinned-shadow-file
        snapshot={'MemAvailable':M.HOST_RESERVE,'GPUActive':pinned+shadow}
        row=W.account_memory({'anonymous_bytes':anon},snapshot,0,pinned,p)
        self.assertEqual(row['host_accounted_bytes'],p['host_bound_bytes'])
        with self.assertRaisesRegex(ValueError,'combined host memory'):
            W.account_memory({'anonymous_bytes':anon+1},snapshot,0,pinned,p)
        with self.assertRaisesRegex(ValueError,'shadow exceeds'):
            W.account_memory({'anonymous_bytes':0},dict(snapshot,GPUActive=pinned+shadow+1),0,pinned,p)

    def test_drm_duplicate_fd_and_reserve(self):
        with tempfile.TemporaryDirectory() as d:
            proc=Path(d);fd=proc/'7/fdinfo';fd.mkdir(parents=True)
            template='drm-driver: xe\\ndrm-pdev: 0000:03:00.0\\ndrm-client-id: 9\\ndrm-total-vram0: {} KiB\\n'
            for n in ('1','2'):(fd/n).write_text(template.format(29_000_000))
            row=D.observe([{'pid':7}],proc)
            self.assertEqual(row['clients'],1);self.assertEqual(row['bytes'],29_000_000*1024)
            self.assertTrue(row['passed'])
            (fd/'2').write_text(template.format(30_000_000))
            self.assertFalse(D.observe([{'pid':7}],proc)['passed'])
            (fd/'2').write_text(template.replace('KiB','GB').format(1))
            with self.assertRaises(ValueError):D.observe([{'pid':7}],proc)

if __name__=='__main__':unittest.main()
''')
    LOG.append(dict(file='screen/test_capacity.py', old='packet58x/58aj capacity tests (stale mapped/resident rows)', new='packet58-cache23 policy tests'))


def root_chain_harness():
    sub('runtime-selection.json', '"cache_allocation_bytes": 21552729600,\n  "cache_bytes": 21552729600,', '"cache_allocation_bytes": 23049601024,\n  "cache_bytes": 23049601024,')
    sub('views.py', "cache_cap='max',cache_allocation_bytes=21552729600,cache_bytes=21552729600,", "cache_cap='max',cache_allocation_bytes=23049601024,cache_bytes=23049601024,")
    sub('suite_driver.py', "'--cache-bytes','21552729600'", "'--cache-bytes','23049601024'")
    sub('suite_driver.py', "cache_cap='max',cache_bytes=21552729600,", "cache_cap='max',cache_bytes=23049601024,")


if __name__ == '__main__':
    assert not (P / 'lineage/harness-delta.json').exists(), 'harness delta already applied'
    views(); suite_driver(); compare(); mechanism(); argument_gate(); startup_gate(); queue_and_window(); admission_and_plan(); tests(); root_chain_harness()
    (P / 'lineage/harness-delta.json').write_text(json.dumps(dict(schema='packet58cache23.harness-delta.v1', edits=LOG), indent=2) + '\n')
    print(json.dumps(dict(applied=True, edits=len(LOG))))
