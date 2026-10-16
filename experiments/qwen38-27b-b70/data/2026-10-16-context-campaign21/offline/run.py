import json, sys, os, glob, statistics as st, datetime as dt, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import srvlog
A = json.loads(sys.argv[1])   # {label, state, requests?, traj?, agent_s, t0, t1, srvlog?, ratio?}
def q(a, p):
    a = sorted(a); return a[min(len(a) - 1, int(p * len(a)))] if a else None
out = {'label': A['label']}
# ---------- proxy state (all sessions) ----------
sess = []
if A.get('state'):
    for d in glob.glob(os.path.join(A['state'], '*', 'state.json')) + glob.glob(os.path.join(A['state'], 'state.json')):
        s = json.load(open(d)); sess.append((os.path.dirname(d), s))
sess.sort(key=lambda x: -(x[1].get('requests') or 0))
if sess:
    tot = collections.Counter()
    for _, s in sess:
        for k in ('requests', 'upstream_calls', 'upstream_s', 'handle_s'):
            tot[k] += s.get(k) or 0
    main_dir, s = sess[0]
    out['sessions'] = len(sess)
    out['proxy'] = {k: s.get(k) for k in ('requests', 'upstream_calls', 'upstream_s', 'handle_s', 'cuts', 'inplace_cuts', 'inplace_failed', 'inplace_reasks',
                    'notes_failed', 'recalls', 'recall_limit_hit', 'think_cap_full', 'empty_replies_retried', 'carried', 'repeats_broken', 'rules_put_back',
                    'notes_prompt_tokens', 'notes_cached_tokens', 'notes_written_tokens', 'ratio', 'largest_turn', 'cut')}
    out['proxy_all_sessions'] = {k: round(v, 1) for k, v in tot.items()}
    # events
    ev = [json.loads(l) for l in open(os.path.join(main_dir, 'events.jsonl'))] if os.path.exists(os.path.join(main_dir, 'events.jsonl')) else []
    out['events'] = dict(collections.Counter(e.get('event') for e in ev))
    reps = [e for e in ev if e.get('event') == 'in-place notes reply']
    out['notes_replies'] = len(reps)
    out['notes_attempts'] = dict(collections.Counter(e.get('attempt') for e in reps))
    out['notes_thinking'] = dict(collections.Counter(str(e.get('thinking')) for e in reps))
    out['notes_written_sum_events'] = sum(e.get('written') or 0 for e in reps)
else:
    reps = []
# ---------- client requests (bridge tap) ----------
req_t = []; req_n = []; last_body = None
if A.get('requests'):
    with open(A['requests']) as f:
        for l in f:
            d = json.loads(l)
            if d.get('path', '').endswith('/chat/completions'):
                req_t.append(d['t']); req_n.append(d.get('n_messages')); last_body = d['body']
            del d
    gaps = [b - a for a, b in zip(req_t, req_t[1:])]
    out['client_requests'] = len(req_t)
    out['span_first_to_last_request_s'] = round(req_t[-1] - req_t[0], 1)
    out['inter_arrival'] = {'median': round(st.median(gaps), 2), 'p90': round(q(gaps, .9), 2), 'max': round(max(gaps), 1), 'total': round(sum(gaps), 1)}
    # keeper (notes) time per request: from the request's arrival to the last notes-related timestamp before the next request
    import bisect
    marks = []
    for dd in [x[0] for x in sess]:
        for fn in ('events.jsonl', 'notes-history.jsonl'):
            p = os.path.join(dd, fn)
            if os.path.exists(p):
                for l in open(p):
                    e = json.loads(l)
                    if 'at' in e: marks.append((e['at'], e.get('event', 'notes applied'), e.get('written'), e.get('upto')))
    marks.sort()
    kt = {}
    for a, kind, w, up in marks:
        i = bisect.bisect_right(req_t, a) - 1
        if i < 0: continue
        kt[i] = max(kt.get(i, 0), a - req_t[i])
    out['keeper_requests'] = len(kt)
    out['keeper_time_s'] = round(sum(kt.values()), 1)
    out['keeper_time_per_request'] = {'median': round(st.median(kt.values()), 1) if kt else None, 'max': round(max(kt.values()), 1) if kt else None}
    out['notes_versions'] = sum(1 for m in marks if m[1] == 'notes applied')
    rest_after = [gaps[i] - kt[i] for i in kt if i < len(gaps)]
    out['gap_after_keeper_median'] = round(st.median(rest_after), 1) if rest_after else None
    # notes call durations: a notes call runs at the start of handling a request (keep() before the main call)
    import bisect
    durs = []; prev = None; per_cut = []
    for e in reps:
        a = e['at']
        if e.get('attempt') == 1:
            i = bisect.bisect_right(req_t, a) - 1
            d = a - req_t[i] if i >= 0 else None
            per_cut.append([i, d, e.get('written')])
        else:
            d = a - prev if prev else None
            if per_cut: per_cut[-1][1] = (per_cut[-1][1] or 0) + (d or 0); per_cut[-1][2] += e.get('written') or 0
        prev = a
        if d is not None: durs.append((d, e.get('written') or 0))
    out['notes_time_s'] = round(sum(d for d, _ in durs), 1)
    out['notes_calls_timed'] = len(durs)
    if durs:
        w = sum(x for _, x in durs); out['notes_tok_per_s'] = round(w / max(sum(d for d, _ in durs), 1e-9), 1)
        out['notes_call_s'] = {'median': round(st.median(d for d, _ in durs), 1), 'max': round(max(d for d, _ in durs), 1)}
    # gap of the request that carried a cut vs the others
    cut_idx = set(i for i, _, _ in per_cut)
    g_cut = [gaps[i] for i in cut_idx if i < len(gaps)]; g_other = [gaps[i] for i in range(len(gaps)) if i not in cut_idx]
    out['gap_cut_requests'] = {'n': len(g_cut), 'median': round(st.median(g_cut), 1) if g_cut else None, 'sum': round(sum(g_cut), 1)}
    out['gap_other_requests'] = {'n': len(g_other), 'median': round(st.median(g_other), 1), 'sum': round(sum(g_other), 1)}
    # the request right after a cut request (its main call already ran after the notes; the next one is ordinary)
# ---------- server log (uncached prompt and generated tokens in the run window) ----------
if A.get('srvlog'):
    rows = srvlog.parse(A['srvlog'])
    out['server_log_window'] = srvlog.window(rows, A['t0'], A['t1'])
# ---------- timing summary ----------
agent_s = A.get('agent_s')
if agent_s and sess:
    hs = out['proxy_all_sessions']['handle_s']; us = out['proxy_all_sessions']['upstream_s']
    out['timing'] = {'agent_s': agent_s, 'handle_s': hs, 'upstream_s': us, 'proxy_own_s': round(hs - us, 1),
                     'outside_proxy_s': round(agent_s - hs, 1), 'outside_share': round((agent_s - hs) / agent_s, 3),
                     'upstream_share': round(us / agent_s, 3)}
print(json.dumps(out))
if last_body is not None and A.get('dump_last'):
    with open(A['dump_last'], 'w') as f: f.write(last_body)
