"""s191_report on REAL device data, read where packet189/packet190 retained it (never copied; the analysis gate pins every file
it reads by sha256), plus the instrumented-view path on site rows in the ENGINE's own row format.

* The off (record-path) views: packet189 row 1's two measured k3x views (62.242 / 62.225 tok/s, 13/13 exact, lane B, 2026-10-22)
  are the off views of a packet191 bracket record; their receipts and rank-0 timing streams feed view_stats; packet190's
  record chain WS128 (the 12 real request streams) reproduces its hit/miss counts and the record metric 62.345282.
* The on (instrumented) views: no device run of the packet191 engine exists yet, so the site rows come from (a) the engine's own
  CPU format proof (v5/evidence/full-shape.json -> the shape archives of the sites loads: packet191.site.v1 rows written by the
  real attribution_row on the real production plan, both ranks, with 1-us synthetic timestamps) and (b) a generator that mirrors
  that row format on packet189's real receipts/timing streams with packet110's per-site call times as durations (the synthetic
  view directory symlinks the real receipts; nothing real is copied). The report must then reproduce packet110's class table
  (excess over packet110 ~ 0), flag the classes whose packet110 excess over the copy floor is >= 15.1 us on both ranks, name their
  closures, report no open mechanism, and pass the completeness rule against the real layer_body / half_completion streams.
* Kill rules on the real/synthetic record: drift, overhead (< 0.93 withholds the table; packet128's rule), missing site rows,
  inexact/changed proposals, class sums vs body > 10 % (events removed), unclassified labels.
"""
import copy, json, os, tarfile, tempfile, unittest
from pathlib import Path
import s191_report as s

P = Path(__file__).resolve().parent
STAGE = P.parents[1]
ROOT = STAGE.parents[2]
P189_ROW1 = STAGE / 'packet189-twocard-k3x/v5/evidence/device-row1-bracket-v3k-k3x-B-p189'
P189_ROW0 = STAGE / 'packet189-twocard-k3x/v5/evidence/device-row0-smoke-k3x-B-p189/bracket-summary.json'
P190_RUN = STAGE / 'packet190-record-bundle-k3x/build/device-cards01-p190-a/WS128/run/repeat-1'
P189_SHAPE = {0: STAGE / 'packet189-twocard-k3x/v5/evidence/shape-144edd56e5af65e90646cd131da083db058a94eedbedd68b88e9222c4f29b687.tar.gz',
              1: STAGE / 'packet189-twocard-k3x/v5/evidence/shape-95d873f2e739632eb5281be6147f779e6ba0fe1e5ec881b392ef4f7acda27aee.tar.gz'}
PROMPTS = ('incident-retrospective', 'code-review', 'customer-email', 'sql-debugging', 'release-plan', 'benchmark-analysis',
           'architecture-tradeoff', 'bug-report-synthesis', 'technical-guide', 'risk-register', 'performance-hypotheses', 'decision-memo')
READ = []
_LAUNCHES = {}
_SCRATCH = None


def read(path):
    READ.append(Path(path)); return json.loads(Path(path).read_text())


def launches(rank):
    """Rank's launch list (label, op) at the record selection from packet189's retained production-shape archive (k3x-first load)."""
    if rank not in _LAUNCHES:
        READ.append(P189_SHAPE[rank])
        with tarfile.open(P189_SHAPE[rank]) as t:
            rows = json.load(t.extractfile('launches-view0.json'))
        _LAUNCHES[rank] = [(x['label'], x['op']) for x in rows]
    return _LAUNCHES[rank]


def scratch():
    global _SCRATCH
    if _SCRATCH is None:
        _SCRATCH = tempfile.TemporaryDirectory(prefix='p191-s191-', dir=P / 'evidence')
    return Path(_SCRATCH.name)


def synthetic_on_view(name, source_view, scale=1.0, drop_site=None, bad_label=None, skip_rank1=False):
    """A view directory with packet189's REAL receipts/timing streams (symlinked) and generated packet191.site.v1 rows in the engine's
    format: every sampled half of the real stream (rank 0: speculative/corrected halves + boundaries; rank 1: halves + a draft), every
    site of every layer the real plan issues, durations = packet110's call time (x scale) with +-5 % per-layer jitter."""
    p110 = s.packet110_reference()
    dest = scratch() / name
    seen_labels = {0: set(), 1: set()}
    for prompt in PROMPTS:
        src = source_view / prompt
        (dest / prompt).mkdir(parents=True)
        os.symlink(src / 'receipt.json', dest / prompt / 'receipt.json')
        for rank in (0, 1):
            (dest / prompt / f'rank{rank}').mkdir()
            os.symlink(src / f'rank{rank}/timings.jsonl', dest / prompt / f'rank{rank}/timings.jsonl')
            os.symlink(src / 'rank1/draft-rows.jsonl', dest / prompt / 'rank1/draft-rows.jsonl') if rank == 1 else None
            if rank == 1 and skip_rank1:
                (dest / prompt / 'rank1/sites.jsonl').write_text('')
                continue
            timings = [json.loads(l) for l in (src / f'rank{rank}/timings.jsonl').read_text().splitlines() if l.strip()]
            halves = [x for x in timings if 'half_completion_ms' in x and x['fixture'] in s.SAMPLED]
            out, half_id, event, t = [], 0, 1, 10**12
            plan = launches(rank)

            def emit(label, phase, fixture, position, speculative, corrected, us):
                nonlocal event, t
                row = dict(schema='packet191.site.v1', diagnostic=True, rank=rank, half=half_id, phase=phase, fixture=fixture, position=position,
                           speculative=speculative, corrected=corrected, label=label, event=event, start_ns=t, end_ns=t + int(us * 1000))
                t += int(us * 1000) + 500; event += 1
                out.append(json.dumps(row))
                seen_labels[rank].add(label)

            def site_us(label, position):
                layer, site, g = s.classify(label)
                if layer is None:  # the 248,320-row head is 1.40 ms on the record line (lever synthesis 4); final norm/HC ~50 us
                    return 1400.0 if label == 'logits' else 50.0 if label.startswith('final.') else 3.0
                kind = 'QSA' if layer in s.QSA_LAYERS else 'GDN'
                ref = p110.get((kind, s.P110_SITE.get(site, site)))
                base = ref['measured_us'] if ref else 2.0
                jitter = 1 + 0.05 * (((layer * 7 + position) % 11) - 5) / 5
                return max(0.5, base * scale * jitter)

            for h in halves:
                half_id += 1
                phase = 'half'
                for label, op in plan:
                    layer = s.classify(label)[0]
                    if rank == 0 and layer is not None and layer >= 24:
                        continue  # stored moved layers never run in a rank-0 half
                    if rank == 1 and layer is not None and layer <= 26:
                        continue  # the k3x view: rank 1 starts at QSA layer 27
                    if h['fixture'] == 0 and (label.startswith('final.') or label in ('logits', 'argmax')):
                        continue
                    if drop_site and label.endswith(drop_site):  # drop_site: a tuple of site suffixes
                        continue
                    if op in ('check_status', 'begin', 'commit', 'broadcast'):
                        continue
                    emit(bad_label or label if bad_label and label.endswith('.gdn.z') else label, phase, h['fixture'], h['position'], bool(h['speculative']), bool(h.get('corrected')), site_us(label, h['position']))
                out.append(json.dumps(dict(schema='packet65.half.v1', half=half_id, rank=rank, fixture=h['fixture'], position=h['position'], speculative=bool(h['speculative']), cancelled=bool(h.get('cancelled')))))
                if rank == 0 and not h['speculative']:
                    half_id += 1
                    for label, op in plan:
                        layer = s.classify(label)[0]
                        if layer is not None and 24 <= layer <= 26:
                            emit(label, 'boundary', h['fixture'], h['position'], False, False, site_us(label, h['position']))
                if rank == 1:  # the draft shares the id of the half it follows (engine behaviour)
                    for _ in range(60):
                        emit('draft', 'draft', h['fixture'], h['position'], False, False, 20.0)
            (dest / prompt / f'rank{rank}/sites.jsonl').write_text('\n'.join(out) + '\n')
    return dest, seen_labels


def real_summary():
    return read(P189_ROW1 / 'bracket-summary.json')


def bracket_from_packet189(on_dirs, on_scale=0.985, off_sites_rows=0):
    """packet191 bracket record: packet189's k3x views 01/03 as off views (0, 2) and 4 (03 again), synthetic on views 1 and 3."""
    summ = real_summary()
    k3x = [v for v in summ['views'] if v['variant'] == 'k3x']
    prompts = ['incident64', *PROMPTS]
    mk = lambda v, index, variant, rate, output, sites: dict(index=index, variant=variant, rate=rate, all_13_exact=v['all_13_exact'], exact_count=v['exact_count'],
                                                             draft_proposals=v['draft_proposals'], acceptance_counts=v['acceptance_counts'], interval_stats=v['interval_stats'],
                                                             sites_data=sites, output=str(output))
    off_sites = dict(variant='k3x-off', expected_present=False, rows_total=off_sites_rows, passed=off_sites_rows == 0)
    on_sites = lambda d: s.sites_census(d, PROMPTS, 'k3x-on')
    views = [mk(k3x[0], 0, 'k3x-off', k3x[0]['rate'], P189_ROW1 / 'run/views/01-candidate', off_sites),
             mk(k3x[0], 1, 'k3x-on', k3x[0]['rate'] * on_scale, on_dirs[0], on_sites(on_dirs[0])),
             mk(k3x[1], 2, 'k3x-off', k3x[1]['rate'], P189_ROW1 / 'run/views/03-candidate', off_sites),
             mk(k3x[1], 3, 'k3x-on', k3x[1]['rate'] * on_scale, on_dirs[1], on_sites(on_dirs[1])),
             mk(k3x[1], 4, 'k3x-off', k3x[1]['rate'], P189_ROW1 / 'run/views/03-candidate', off_sites)]
    return dict(kind='bracket', views=views)


SMOKE = dict(kind='smoke', passed=True, exact=True, sites_present=True)


class RealOffViews(unittest.TestCase):
    def test_packet189_k3x_views_are_exact_and_pinned(self):
        ref = s.packet189_k3x_reference()
        self.assertEqual(ref['rates'], [62.24199434282818, 62.22542821257332]); self.assertTrue(ref['read_in_place'])
        rec = s.packet190_record_reference(); self.assertEqual(rec['rate'], s.RECORD)

    def test_view_stats_on_real_packet189_k3x_views(self):
        for view in ('01-candidate', '03-candidate'):
            st_ = s.view_stats(P189_ROW1 / 'run/views' / view, list(PROMPTS), 'k3x-off')
            self.assertEqual(st_['intervals'], 1188); self.assertGreater(st_['hits'], 600); self.assertGreater(st_['misses'], 100)
            self.assertTrue(13.3 < st_['hit']['elapsed'] < 13.8 and 25.2 < st_['miss']['elapsed'] < 25.9, st_['hit'])
            self.assertTrue(1.4 < st_['hit']['Bd'] < 1.6 and 1.4 < st_['hit']['D'] < 1.7)
            env = st_['envelope']; self.assertTrue(11.4 < env['scopes_ms']['layer_body'] < 11.9 and env['scope_counts']['token_history'] == 0)
            for prompt in PROMPTS:  # an off view writes no site rows (packet189's k3x views are the record path)
                self.assertEqual(s.read_rows(P189_ROW1 / 'run/views' / view / prompt / 'rank0/sites.jsonl'), ([], []))
            census = s.sites_census(P189_ROW1 / 'run/views' / view, ['incident64', *PROMPTS], 'k3x-off')
            self.assertTrue(census['passed'] and census['rows_total'] == 0)

    def test_view_stats_on_real_packet190_record_chain(self):
        st_ = s.view_stats(P190_RUN, list(PROMPTS), 'k3x-off', require_exact=False)
        self.assertEqual((st_['hits'], st_['misses'], st_['intervals']), (932, 256, 1188))
        self.assertTrue(13.4 < st_['hit']['elapsed'] < 13.6 and 25.4 < st_['miss']['elapsed'] < 25.7)
        oracle = STAGE / 'packet49-integrate/oracle/results'
        for prompt in PROMPTS:
            r = read(P190_RUN / prompt / 'receipt.json'); self.assertEqual(r['tokens'], read(oracle / prompt / 'result.json')['tokens'][:len(r['tokens'])])

    def test_half_bodies_pair_layer_body_with_half_records(self):
        b0 = s.half_bodies(P189_ROW1 / 'run/views/01-candidate', 'decision-memo', 0)
        b1 = s.half_bodies(P189_ROW1 / 'run/views/01-candidate', 'decision-memo', 1)
        self.assertGreater(len(b0), 150); self.assertGreater(len(b1), 120)
        import statistics
        self.assertTrue(10 < statistics.median(b0.values()) < 14 and 10 < statistics.median(b1.values()) < 14)  # cancelled speculative halves are short
        spec = [k for k in b0 if k[2]]; corr = [k for k in b0 if k[3]]; self.assertTrue(spec and corr)


class EngineFormat(unittest.TestCase):
    """The rows the real engine wrote on CPU (full-shape gate, sites loads) classify completely on both ranks."""
    def test_engine_rows_classify_and_cover_the_plan(self):
        shape = read(P / 'evidence/full-shape.json')
        fmt = shape['sites_format']
        self.assertEqual(set(fmt), {'k3x-off-first-rank0', 'k3x-off-first-rank1', 'k3x-on-first-rank0', 'k3x-on-first-rank1'})
        for key, row in fmt.items():
            self.assertGreater(row['rows'], 400); self.assertNotIn('unknown', row['groups'])
            self.assertEqual(row['phases'], ['boundary', 'half'] if key.endswith('rank0') else ['draft', 'half'])
        for run in shape['runs']:
            if run['load'] in ('k3x-off-first', 'k3x-on-first'):
                art = ROOT / run['artifact']['path']; READ.append(art)
                with tarfile.open(art) as t:
                    rows = [json.loads(l) for name in t.getnames() if name.endswith('sites.jsonl') for l in t.extractfile(name).read().decode().splitlines() if l.strip()]
                rows = [r for r in rows if r.get('schema') == 'packet191.site.v1']
                halves = s.group_halves(rows, run['rank'])
                self.assertTrue(all(s.classify(r['label'])[2] != 'unknown' for r in rows))
                half = next(h for h in halves.values() if h['phase'] == 'half')
                expected = list(range(0, 24)) if run['rank'] == 0 else list(range(27, 48))
                self.assertEqual(sorted(half['layers']), expected)
                self.assertTrue(all('ffn.combine' in half['layers'][k] for k in expected))
                groups = {s.classify(f'blk.{k}.{site}')[2] for k in expected for site in half['layers'][k]}
                self.assertEqual(groups >= {'experts', 'dense', 'qsa_attention', 'recurrence', 'hc', 'norms', 'route_small'}, True, groups)


class InstrumentedViews(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.on_a, cls.labels = synthetic_on_view('on-a', P189_ROW1 / 'run/views/01-candidate')
        cls.on_b, _ = synthetic_on_view('on-b', P189_ROW1 / 'run/views/03-candidate')
        cls.bracket = bracket_from_packet189([cls.on_a, cls.on_b])
        cls.report = s.decide(SMOKE, cls.bracket)

    @classmethod
    def tearDownClass(cls):
        global _SCRATCH
        if _SCRATCH is not None:
            _SCRATCH.cleanup(); _SCRATCH = None

    def test_measurement_completes_and_reproduces_packet110(self):
        r = self.report
        self.assertTrue(r['measurement_complete'] and r['table_admissible'] and not r['screen_winner'], r['outcome'])
        self.assertEqual(r['kill_rules']['fired'], []); self.assertIn('MEASUREMENT COMPLETE', r['outcome'])
        off, on = r['off_rates'], r['on_rates']; self.assertAlmostEqual(r['instrumented_over_control'], (sum(on) / 2) / (sum(off) / 3), places=12); self.assertTrue(0.984 < r['instrumented_over_control'] < 0.986)
        self.assertLess(r['control_drift_percent'], 0.1); self.assertTrue(r['off_timing_equivalent_to_packet189'])
        self.assertAlmostEqual(r['off_vs_packet189_k3x_percent'], 100 * ((62.24199434282818 + 2 * 62.22542821257332) / 3 / ((62.24199434282818 + 62.22542821257332) / 2) - 1), places=9)
        a, b = r['class_table']['rank0/speculative'], r['class_table']['rank1/half']
        for g in ('experts', 'dense', 'hc', 'recurrence', 'route_small', 'norms', 'qsa_attention'):
            for t in (a, b):
                self.assertIsNotNone(t[g]['us_per_gdn_layer'] if g != 'qsa_attention' else t[g]['us_per_qsa_layer'], g)
                if g != 'qsa_attention':
                    self.assertLess(abs(t[g]['excess_packet110_us_per_gdn_layer']), 0.06 * t[g]['packet110_us_per_gdn_layer'], (g, t[g]))
        self.assertTrue(95 < a['experts']['us_per_gdn_layer'] < 125 and 140 < a['dense']['us_per_gdn_layer'] < 170, (a['experts'], a['dense']))
        self.assertTrue(a['experts']['floor_coverage_gdn'] > 0.99 and a['recurrence']['floor_coverage_gdn'] > 0.99)
        self.assertTrue(60 < a['experts']['excess_floor_us_per_gdn_layer'] < 90)  # packet110: 74 us above the copy floor
        self.assertIn('rank0/boundary', r['class_table']); self.assertIn('rank0/corrected', r['class_table']); self.assertIn('draft', r['class_table']['rank1/draft'])
        self.assertEqual(sorted(r['class_table']['rank0/boundary']), ['dense', 'experts', 'hc', 'norms', 'recurrence', 'route_small'])
        self.assertTrue(r['class_table']['rank1/half']['head']['ms_per_half'] > 0)
        c = r['kill_rules']['completeness']; self.assertEqual(len(c), 6)  # 2 views x (rank0 speculative, rank0 corrected, rank1 half)
        self.assertTrue(all(x['deviation_pct'] <= 10 for x in c), c)

    def test_eligibility_flags_packet110_excess_and_names_closures(self):
        e = self.report['eligibility']
        # packet110's own above-floor numbers per GDN layer: experts 74, hc 55, norms 17, route_small ~35, recurrence 32, dense 20 (all >= 15.1); qsa_attention has no GDN layer
        self.assertEqual(self.report['chain_eligible_by_excess'], ['dense', 'experts', 'hc', 'norms', 'recurrence', 'route_small'])
        self.assertEqual(self.report['screen_eligible_by_excess'], self.report['chain_eligible_by_excess'])
        self.assertFalse(e['qsa_attention']['chain_eligible_by_excess'] or e['ple']['chain_eligible_by_excess'])
        self.assertFalse(self.report['open_mechanisms_remaining'])
        for g in ('experts', 'hc', 'recurrence', 'route_small', 'dense', 'norms'):
            self.assertTrue(e[g]['closures'] and not e[g]['open_mechanisms'])
            self.assertAlmostEqual(e[g]['gain_if_all_excess_removed_pct'], 1.32 * e[g]['min_over_ranks'] / 10, places=9)
        self.assertIn('NONE', self.report['outcome'])
        self.assertTrue(self.report['attribution'][0]['windows']['rank0/9-16']['halves'] > 0 and self.report['attribution'][0]['windows']['rank1/105-112']['halves'] > 0)
        self.assertIn('hit_A_ms', self.report['instrumentation_cost'])

    def test_overhead_below_0_93_withholds_the_table(self):
        r = s.decide(SMOKE, bracket_from_packet189([self.on_a, self.on_b], on_scale=0.92))
        self.assertFalse(r['table_admissible']); self.assertIn('TABLE INADMISSIBLE', r['outcome']); self.assertEqual(r['class_table'], {})
        self.assertIn('instrumented_over_control_min', r['kill_rules']['fired']); self.assertIn('packet128', r['kill_rules']['overhead_rule'])

    def test_drift_inexact_proposals_and_missing_rows_stop(self):
        b = bracket_from_packet189([self.on_a, self.on_b]); b['views'][2]['rate'] *= 1.006
        r = s.decide(SMOKE, b); self.assertIn('STOP', r['outcome']); self.assertIn('control_drift_pct', r['kill_rules']['fired'])
        b = bracket_from_packet189([self.on_a, self.on_b]); b['views'][1]['exact_count'] = 12
        self.assertIn('exact_or_proposals', s.decide(SMOKE, b)['kill_rules']['fired'])
        b = bracket_from_packet189([self.on_a, self.on_b]); b['views'][3] = copy.deepcopy(b['views'][3]); b['views'][3]['draft_proposals'] = {'x': 1}
        self.assertIn('exact_or_proposals', s.decide(SMOKE, b)['kill_rules']['fired'])
        b = bracket_from_packet189([self.on_a, self.on_b], off_sites_rows=5)  # an off view that wrote site rows: the record path leaked
        self.assertIn('sites_rows_presence', s.decide(SMOKE, b)['kill_rules']['fired'])
        self.assertEqual(s.decide_or_incomplete(dict(SMOKE, sites_present=False), b)['outcome'], 'INCOMPLETE: no report')
        self.assertEqual(s.decide_or_incomplete(dict(SMOKE, exact=False), b)['outcome'], 'INCOMPLETE: no report')
        b = bracket_from_packet189([self.on_a, self.on_b]); b['views'][1]['variant'] = 'k3x'
        self.assertEqual(s.decide_or_incomplete(SMOKE, b)['outcome'], 'INCOMPLETE: no report')

    def test_missing_events_fail_completeness_never_zero(self):
        dropped, _ = synthetic_on_view('on-drop', P189_ROW1 / 'run/views/01-candidate', drop_site=('.expsgate', '.expsdown', '.expsact'))  # the expert class removed (2 ms/half): sums fall > 10 % below the body
        r = s.decide(SMOKE, bracket_from_packet189([dropped, self.on_b]))
        self.assertIn('class_sum_vs_body_pct', r['kill_rules']['fired']); self.assertIn('STOP', r['outcome']); self.assertTrue(r['kill_rules']['completeness_failures'])
        bad, _ = synthetic_on_view('on-bad', P189_ROW1 / 'run/views/01-candidate', bad_label='blk.5.mystery')
        r = s.decide(SMOKE, bracket_from_packet189([bad, self.on_b]))
        self.assertIn('unclassified', r['kill_rules']['attribution_error']); self.assertIn('STOP', r['outcome'])
        skipped, _ = synthetic_on_view('on-skip', P189_ROW1 / 'run/views/01-candidate', skip_rank1=True)
        r = s.decide(SMOKE, bracket_from_packet189([skipped, self.on_b]))
        self.assertIn('sites_rows_presence', r['kill_rules']['fired'])


class Records(unittest.TestCase):
    def test_records_from_real_summaries(self):
        sm = s.smoke_record(read(P189_ROW0))  # packet189's k3x smoke: exact, but no site rows (it is not an instrumented view)
        self.assertTrue(sm['passed'] and sm['exact'] and not sm['sites_present'])
        b = s.bracket_record(real_summary()); self.assertEqual([v['variant'] for v in b['views']], ['v3k', 'k3x', 'v3k', 'k3x', 'v3k'])
        self.assertEqual(s.decide_or_incomplete(sm, b)['outcome'], 'INCOMPLETE: no report')  # neither the smoke nor the order is packet191's


if __name__ == '__main__':
    unittest.main()
