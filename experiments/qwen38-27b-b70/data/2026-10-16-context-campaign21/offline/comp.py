import json, sys, statistics as st
# usage: comp.py messages.json label ratio actual_cuts notes_chars
path, label, ratio, actual_cuts, notes_chars = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4], int(sys.argv[5])
d = json.load(open(path))
msgs = d['messages'] if isinstance(d, dict) else d
STUB = 120          # chars of the stub that replaces an old tool output
INPLACE = 15000     # ctxkeeper --inplace-tokens (recipe qwen/agent)
KEEP_TURNS = 3      # tool outputs older than this many assistant turns are stubbed
def text(c):
    if c is None: return ''
    if isinstance(c, str): return c
    if isinstance(c, list): return '\n'.join(str(p.get('text', '')) if isinstance(p, dict) else str(p) for p in c)
    return str(c)
def parts(m):
    """(visible chars, reasoning chars) of one message"""
    vis = len(text(m.get('content')))
    for tc in m.get('tool_calls') or []:
        fn = tc.get('function') or {}
        vis += len(str(fn.get('name', ''))) + len(str(fn.get('arguments', '')))
    r = m.get('reasoning_content') or m.get('reasoning') or ''
    if not r and m.get('reasoning_details'):
        r = '\n'.join(str(x.get('text', '')) for x in m['reasoning_details'] if isinstance(x, dict))
    return vis, len(str(r))
first_a = next(i for i, m in enumerate(msgs) if m.get('role') == 'assistant')
head = msgs[:first_a]
cat = {'system': 0, 'user_task': 0, 'user_later': 0, 'assistant_visible': 0, 'assistant_reasoning': 0, 'tool': 0}
tool_sizes = []
size = []           # per message: total chars (visible + reasoning: what the server re-reads when it is in view)
for i, m in enumerate(msgs):
    v, r = parts(m); role = m.get('role')
    if role in ('system', 'developer'): cat['system'] += v
    elif role == 'user': cat['user_task' if i < first_a else 'user_later'] += v
    elif role == 'assistant': cat['assistant_visible'] += v; cat['assistant_reasoning'] += r
    elif role == 'tool': cat['tool'] += v; tool_sizes.append(v)
    size.append(v + r)
total = sum(cat.values())
def q(a, p): a = sorted(a); return a[min(len(a) - 1, int(p * len(a)))]
res = {'label': label, 'messages': len(msgs), 'assistant_turns': sum(m.get('role') == 'assistant' for m in msgs),
       'tool_results': len(tool_sizes), 'total_chars': total, 'total_tok_at_3.5': round(total / 3.5),
       'share': {k: round(v / total, 3) for k, v in cat.items()},
       'tool_chars': {'median': st.median(tool_sizes), 'p90': q(tool_sizes, .9), 'max': max(tool_sizes), 'mean': round(st.mean(tool_sizes))},
       'tool_tok35': {'median': round(st.median(tool_sizes) / 3.5), 'p90': round(q(tool_sizes, .9) / 3.5), 'max': round(max(tool_sizes) / 3.5)}}
# assistant index positions
a_idx = [i for i, m in enumerate(msgs) if m.get('role') == 'assistant']
# number of assistant messages after message i (in the final history)
after = [0] * len(msgs); c = 0
for i in range(len(msgs) - 1, -1, -1):
    after[i] = c
    if msgs[i].get('role') == 'assistant': c += 1
old_final = sum(max(0, size[i] - STUB) for i, m in enumerate(msgs) if m.get('role') == 'tool' and after[i] > KEEP_TURNS)
res['final_history_old_tool_removable_share'] = round(old_final / sum(size), 3)
res['final_history_reasoning_share'] = round(cat['assistant_reasoning'] / total, 3)
# ---------------- simulation of the proxy view over the requests ----------------
# request k is sent just before assistant message a_idx[k]; its history is msgs[:a_idx[k]]
tok = lambda ch: ch / ratio
head_ch = sum(size[:first_a]); notes_ch = notes_chars
def simulate(prepass):
    cut = first_a; cuts = 0; view_tok = []; old_in_view = []; reread_extra = 0; stub_events = 0
    inc = 0; postcut = 0; prev_end = None
    stubbed = set()
    for k, a in enumerate(a_idx):
        hist_end = a
        # assistant turns before this request, counted from each message
        n_after = {}
        cnt = 0
        for i in range(hist_end - 1, cut - 1, -1):
            n_after[i] = cnt
            if msgs[i].get('role') == 'assistant': cnt += 1
        def eff(i):
            if prepass == 'rolling' and msgs[i].get('role') == 'tool' and n_after.get(i, 0) >= KEEP_TURNS:
                return min(size[i], STUB)
            if prepass == 'atcut' and i in stubbed:
                return min(size[i], STUB)
            return size[i]
        # newest exchange: last assistant message before hist_end and everything after it
        j = max((i for i in range(cut, hist_end) if msgs[i].get('role') == 'assistant'), default=None)
        if j is not None and j > cut:
            noted_tok = tok(sum(eff(i) for i in range(cut, j)))
            if noted_tok > INPLACE and prepass == 'atcut':
                # CPU pre-pass first: stub the old tool outputs of the turns in view; cut only if still over
                newly = [i for i in range(cut, j) if msgs[i].get('role') == 'tool' and n_after.get(i, 0) >= KEEP_TURNS and i not in stubbed]
                if newly:
                    first_changed = min(newly)
                    stubbed.update(newly); stub_events += 1
                    reread_extra += tok(sum(eff(i) for i in range(first_changed, hist_end)))   # everything after the first change is read again
                    noted_tok = tok(sum(eff(i) for i in range(cut, j)))
            if noted_tok > INPLACE:
                cut = j; cuts += 1
                postcut += tok(notes_ch + sum(eff(i) for i in range(cut, hist_end)))
                prev_end = None
        if prepass == 'rolling':
            # the tool output that became old at this request breaks the cache from that point on
            newly = [i for i in range(cut, hist_end) if msgs[i].get('role') == 'tool' and n_after.get(i, 0) == KEEP_TURNS]
            if newly:
                reread_extra += tok(sum(eff(i) for i in range(min(newly), hist_end)))
        if prev_end is not None:
            inc += tok(sum(eff(i) for i in range(prev_end, hist_end)))
        prev_end = hist_end
        body = sum(eff(i) for i in range(cut, hist_end))
        v = tok(head_ch + (notes_ch if cut > first_a else 0) + body)
        old = tok(sum(max(0, size[i] - STUB) for i in range(cut, hist_end) if msgs[i].get('role') == 'tool' and n_after.get(i, 0) >= KEEP_TURNS))
        view_tok.append(v); old_in_view.append(old if prepass is None else 0)
    return {'cuts': cuts, 'view_tok_sum': round(sum(view_tok)), 'view_tok_mean': round(st.mean(view_tok)), 'view_tok_max': round(max(view_tok)),
            'old_tool_tok_in_view_sum': round(sum(old_in_view)), 'old_tool_share_of_view': round(sum(old_in_view) / sum(view_tok), 3),
            'extra_reread_tok': round(reread_extra), 'stub_events': stub_events,
            'incremental_new_tok': round(inc), 'postcut_reread_tok': round(postcut)}
res['actual_cuts'] = actual_cuts
res['sim_baseline'] = simulate(None)
res['sim_rolling_prepass'] = simulate('rolling')
res['sim_prepass_at_cut'] = simulate('atcut')
# whole history every call (no proxy): what share of all prompt chars is old tool output
tot = 0; old = 0
for k, a in enumerate(a_idx):
    cnt = 0; n_after = {}
    for i in range(a - 1, -1, -1):
        n_after[i] = cnt
        if msgs[i].get('role') == 'assistant': cnt += 1
    tot += sum(size[:a]); old += sum(max(0, size[i] - STUB) for i in range(a) if msgs[i].get('role') == 'tool' and n_after[i] >= KEEP_TURNS)
res['whole_history_calls'] = {'prompt_chars_sum': tot, 'old_tool_share': round(old / tot, 3)}
print(json.dumps(res))
