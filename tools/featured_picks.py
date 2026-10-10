"""Curated B70 picks; measurements are read from retained receipts, never copied.

Called by build-model-pages.py. This is editorial source, not a second catalog.
A scoped observation cannot fill a package's withheld headline.
"""
from html import escape as esc
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GITHUB = 'https://github.com/steveseguin/b70-optimization-lab/blob/main/'
START = '<!-- BEGIN GENERATED FEATURED PICKS -->'
END = '<!-- END GENERATED FEATURED PICKS -->'
PROFILE_DIR = 'data/profiles/2026-10-10/'


def read(path):
    return json.loads((ROOT / path).read_text())


def measurement(path, keys, label='One person', scope='', digits=1, scale=250):
    value = read(path)
    for key in keys:
        value = value[key]
    if not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f'Unmeasured featured value: {path} {keys}')
    return dict(value=value, evidence=path, label=label, scope=scope,
                digits=digits, scale=scale, unit='tok/s')


def package_pick(packages, package_id, name, status, why, *, research=False):
    p = packages[package_id]
    metric = p['library'].get('featured_metric')
    metrics = []
    if metric:
        metrics.append(dict(value=metric['value'], evidence=metric['evidence'],
                            label='One person', scope=metric['label'], digits=2,
                            scale=250, unit=metric['unit']))
    return dict(id=package_id, name=name, cards=p['hardware']['cards'],
                detail=f'models/{package_id}.html', guide=p['guide'],
                setup=p['library']['quantization'] + ' · ' + p['library']['runtime_label'],
                status=status, why=why, research=research, metrics=metrics,
                note='Expert recipe; clean-host certification pending.')


def use_profile(pick, label):
    path = PROFILE_DIR + label + '.json'
    profile = read(path)
    meta = read('tools/profiles-site-map.json')[label]
    # The package may include a second topology; use only this explicit profile.
    pick['cards'] = meta['cards']
    pick['metrics'] = [measurement(path, ['decode_1user', 'median_tps'],
                                   scope='October 10 speed check')]
    pick['metrics'].append(measurement(path, ['decode_nusers', 'aggregate_tps'],
                                      label=f"{profile['users']} people", digits=0,
                                      scope='combined, October 10', scale=1400))
    pre = profile['prefill']['2048']
    pick['metrics'].append(measurement(path, ['prefill', '2048', 'prompt_tps'],
                                      label='Reads a prompt', digits=0, scale=4200,
                                      scope=f"{pre['prompt_tokens']:,} input tokens / first-token wait"))
    pick['note'] = ('October 10 speed check: 300-token prompt, 256 output tokens; '
                    'reading speed is input tokens divided by time to first token. '
                    'Separate from package certification; clean-host replay pending.')
    return pick


def groups(catalog):
    pkgs = {p['id']: p for p in catalog['packages']}
    def pick(*args, **kwargs):
        return package_pick(pkgs, *args, **kwargs)
    ornith = pick('ornith-15-35b-a3b-q4km-b70', 'Ornith 1.5 35B-A3B Q4_K_M',
                  'Candidate · strict headline pending',
                  'The largest of these measured one-card models; about 3B parameters active per token. '
                  'The patch matched its control, but fresh servers did not reproduce complete answers.', research=True)
    ornith['metrics'] = [measurement(
        'experiments/ornith-15-b70/data/2026-08-23-ornith35b-shared-gate-residual-rms-summary.json',
        ['fresh_server', 'candidate_mean_of_run_medians_conventional_tok_s'],
        scope='two-server observation; not certified', digits=2)]
    nemotron = use_profile(pick('nemotron-35-lightning-30b-a3b-b70',
        'Nemotron 3.5 Lightning 30B-A3B', 'Candidate · strict headline pending',
        'A 30B model with about 3B parameters active per token. The October test had differing repeats '
        'and passed two of three answer checks. Quality work remains.', research=True),
        'nemotron-35-lightning-30b-a3b-nd9fee29e-16k-p4')
    int4 = use_profile(pick('qwen38-27b-autoround-int4-b70', 'Qwen3.8 27B AutoRound INT4',
        'Qualified package · one-card speed check',
        'A dense 27B chat and coding option. The package has exact-output gates; this one-card '
        'October test also repeated identically alone and with four users.'),
        'qwen38-27b-int4-fixed-k-one-gpu-p4')
    fp8 = use_profile(pick('qwen38-27b-fp8-vllm-tp1-b70', 'Qwen3.8 27B FP8',
        'Qualified lossless package · one-card speed check',
        'Choose this 27B setup for official FP8 weights and full 16-bit KV. Target-verified drafting '
        'passed the package’s exact-output checks. The tested profile serves one request at a time.'),
        'qwen38-27b-fp8-tp1-b70-recommended-p1')
    # A single-request-only profile has no meaningful many-user comparison.
    fp8['metrics'] = [m for m in fp8['metrics'] if m['label'] != '1 people']
    gemma = pick('gemma4-26b-a4b-q8-b70-125tps-20260701', 'Gemma 4 26B-A4B Q8',
        'Lab record · target-verified draft',
        'A 26B model with about 4B parameters active per token, using 8-bit weights. '
        'The cold-suite record passed its canaries. The separate shared-server test below '
        'uses no draft and can change answers when other users join.')
    gemma['note'] = 'Cold 12-prompt record, 512-token cap, MTP depth 3. Historical binary/draft pins and clean-host replay remain incomplete.'
    flash = pick('qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913',
        'Qwen3.8 Flash-Next 125B-A6B', 'Certified lossless result · four cards',
        'The large FP8 flagship, with about 6B parameters active per token. Accepted draft tokens '
        'are verified by the unchanged target. Exact-output and quality evidence are bound to the record.')
    flash['metrics'][0]['digits'] = 6
    flash['note'] = 'Cold realistic suite; one user, full BF16 KV. Certified result; expert lab replay, portable installer still incomplete.'
    shared = pick('qwen38-27b-fp8-vllm-tp2-asrock-b70', 'Qwen3.8 27B FP8 · shared chat',
        'Exact tested outputs · multi-user speed not certified',
        'For two cards and many people at once. The 64-user check matched the saved one-user answers '
        'on both passes. This is Qwen 27B, a separate model from Flash-Next.')
    shared_path = 'experiments/qwen38-27b-b70/data/2026-10-07-fp8-two-card-multi-user/summary.json'
    shared['metrics'] = [measurement(shared_path, ['strict', 'decode_tokens_s'], scope='single-user MTP5', digits=2),
        measurement(shared_path, ['multi_user', 'suites', 'short', 'passes', 4, 'tok_s_together'],
                    label='64 people', scope='combined; short prompts, MTP0', digits=0, scale=1400)]
    shared['note'] = '64-user passes: 875.31 and 875.05 tok/s, 128 output tokens per user, same server. No fresh-server speed certification; not long input for every user.'
    minimax = pick('minimax-m27-b70-89tps-20260520', 'MiniMax M2.7 · 229B INT4',
        'Historical quality-gated record · four cards',
        'A much larger mixture-of-experts model. Exact short-output checks, semantic tasks and '
        'arithmetic passed. The displayed speed is the historical short-context record.')
    minimax['note'] = 'Historical mean of four warm 512-input / 1,536-output runs at 2K context; not a cold-suite headline. The 32K recipe has a separate slower result.'
    laguna = pick('laguna-s-2.1-int4-b70-125tps-20260731', 'Laguna S 2.1 INT4',
        'Quality-checked lab record · four cards',
        'A coding model with a target-verified DFlash draft. The record keeps its exactness '
        'checks and test conditions in a replay packet.')
    laguna['note'] = '13 cold prompts on one server start; full BF16 KV. Historical lab replay; clean-host certification pending.'
    muse = pick('muse-glimmer-30b-q8-woq-b70-100tps-20260813', 'Muse Glimmer 30B Q8 WOQ',
        'Target-verified record · four cards measured',
        'The Q8 weights alone exceed one B70’s memory. This measured four-card setup uses '
        'a BF16 DFlash assistant; it is not a one-card recipe.')
    muse['note'] = 'Mean across two fresh three-prompt runs, 256 output tokens; not the full varied-suite median. Clean-host certification pending.'
    deepseek = dict(id='deepseek-v4-research', name='DeepSeek V4 Flash · 180B research', cards=4,
        detail='models/deepseek-v4.html', guide='repro/deepseek-v4-flash-k160-b70-80tps-20260718/README.md',
        setup='Community-trimmed FP8 / FP4 experts · FP8 KV · vLLM XPU',
        status='Experimental, lossy checkpoint · not a lossless recommendation',
        why='A separate research option. Exact checks apply only to this trimmed target; they do not '
            'prove equality to the original model. It also uses compressed KV.', research=True,
        metrics=[], note='Historical 128-token test; not eligible for a current lossless headline. See the full record and provenance limits.')
    # Preserve the observed range, not a hand-picked high, for the research arm.
    run = next(r for r in read('families/deepseek-v4.json')['run_measurements']
               if r['id'] == 'deepseek-v4-k160-tp4-ep-dspark7-strict')
    deepseek['observation'] = (f"{min(run['metrics']['decode_tok_s']):.2f}–{max(run['metrics']['decode_tok_s']):.2f} tok/s "
                               '(historical research observations)', run['evidence'])
    video = pick('ltx25-continuation-stream-b70-145f-20261010', 'LTX 2.5 · continuing video stream',
        'Byte-exact compared chunks · sustained speed pending',
        'A stream of generated video on four cards, designed to keep continuing around the clock. '
        'Compared frames, latents and audio match the reference bytes. Seam and audio acceptance remain open.', research=True)
    path = 'repro/ltx25-continuation-stream-b70-145f-20261010/evidence/pacing-snapshot.json'
    run = next(r for r in read(path)['runs'] if r['packet'] == '135' and r['work_dir'].endswith('/s135-live01'))
    raw = run['raw_statistics']['median_s'] / run['new_video_seconds_per_continuation']
    early = run['statistics']['median_s']
    video['observation'] = (f'{raw:.3f} seconds elapsed per second of video', path)
    video['note'] = (f'Recorded delivery cadence: {run["raw_statistics"]["median_s"]} seconds per six new video seconds '
                     f'over {run["raw_statistics"]["n"]} periods, including pacing. Early unthrottled window: '
                     f'{early} seconds over {run["statistics"]["n"]} periods. Neither proves sustained 24/7 uptime. '
                     'Lab replay; public runtime rebuild incomplete.')
    small = []
    for pid, name, profile, status, why in [
        ('qwen35-9b-w4a16-b70','Qwen3.5 9B INT4','qwen35-9b-w4a16-b70-one-gpu-p8',
         'Qualified package · October speed check','A compact chat option. Repeats and concurrent answers matched in this check; package exactness gates are separate.'),
        ('qwen35-9b-fp8-b70','Qwen3.5 9B FP8','qwen35-9b-fp8-b70-one-gpu-p8',
         'Qualified package · October speed check','The compact model with FP8 weights. Repeats and concurrent answers matched in this check.'),
        ('ornith-15-9b-q8-b70','Ornith 1.5 9B Q8','ornith-15-9b-q8-b70-nd9fee29e-16k-p4',
         'Strict headline withheld','Complete answers differed across fresh servers. The October check also had differing repeats and passed two of three answer checks.'),
        ('qwen35-4b-w4a16-b70','Qwen3.5 4B INT4','qwen35-4b-w4a16-b70-one-gpu-p8',
         'Qualified package · October speed check','A small model for lighter tasks. Repeats matched in the October test; answers changed with concurrent users.'),
        ('lfm25-26b-q8-b70','LFM2.5 2.6B Q8','lfm25-26b-q8-b70-nd9fee29e-16k-p4',
         'Qualified package · separate October check','A 2.6B model. The strict package passed its gates; the October setup failed its quick answer check and concurrent answers differed.'),
    ]:
        small.append(use_profile(pick(pid, name, status, why), profile))
    # One editorial role per featured setup; scores never clear quality gates.
    featured = [int4, gemma, fp8, laguna, shared, flash, video]
    roles = ['Everyday assistant', 'Fast single-user replies on one card',
             'Longer documents with official FP8 weights', 'Dedicated coding setup',
             'Many people at once', 'Larger model for demanding tasks',
             'Continuing video with audio']
    for p, role in zip(featured, roles):
        p['role'] = role
    int4['why'] = ('Start here for everyday chat and code on one card. A recent dense 27B model '
                   'from the widely used Qwen family, with an optimized INT4 recipe. '
                   'The one-card speed check repeated identically alone and with four users.')
    gemma['why'] = ('Our fast one-card pick among the larger, quality-gated packages: '
                   '26B total parameters, about 4B active, and 8-bit weights. '
                   'Its cold-suite record uses target-verified drafting; the table below uses a different, no-draft setup.')
    fp8['why'] = ('For longer documents on one card, with official FP8 weights and full 16-bit KV. '
                 'The package measures real inputs through 16K tokens; its configured 32K limit is not a measured 32K speed.')
    profile = next(p for p in pkgs[fp8['id']]['performance_profiles']
                   if p['id'] == 'decode-vs-context-recommended')
    point = next(p for p in profile['points'] if p['context_tokens'] == 16384)
    fp8['metrics'].append(dict(value=point['value'], evidence=profile['evidence'],
        label='After a long prompt', scope='16,384 input tokens; separate context test',
        digits=2, scale=250, unit='tok/s'))
    flash['why'] = ('For four-card owners who want a larger model for demanding reasoning and agent tasks. '
                    'The recent 125B-A6B Qwen has a certified lossless result here; '
                    'its capability standing comes from publisher evaluations, not our speed test.')
    return [('task-picks', 'Pick the job you want to do', featured),
            ('other-picks', 'Other models and research options',
             [minimax, muse, ornith, nemotron, deepseek] + small[:3]),
            ('small-quick', 'Small and quick · under 9B', small[3:])]


def render_pick(pick, rank):
    research = ' research' if pick['research'] else ''
    metrics = []
    for m in pick['metrics']:
        # Each bar links to the source of its own value; no implied certification.
        width = 100 * m['value'] / m['scale']
        if width > 100:
            raise ValueError('Featured scale must include every measurement')
        metrics.append(f'<div class="pick-bar-row"><span class="pick-bar-label">{esc(m["label"])}</span>'
            f'<div class="pick-track" aria-hidden="true"><div class="pick-fill" style="width:{width:.2f}%"></div></div>'
            f'<span class="pick-val"><a href="{GITHUB}{esc(m["evidence"])}">{m["value"]:,.{m["digits"]}f} {esc(m["unit"])}</a>'
            f'<small>{esc(m["scope"])}</small></span></div>')
    if pick.get('observation'):
        label, evidence = pick['observation']
        metrics.append(f'<p class="pick-note"><a href="{GITHUB}{esc(evidence)}">{esc(label)}</a></p>')
    if not any(m['label'] == 'Reads a prompt' for m in pick['metrics']) and pick['id'] != 'ltx25-continuation-stream-b70-145f-20261010':
        metrics.append('<p class="pick-note">Prompt reading: not measured for this exact result.</p>')
    metrics.append(f'<p class="pick-note">{esc(pick["note"])}</p>')
    return f'''      <li class="pick-row{research}" data-pick-id="{esc(pick['id'])}">
        <div class="pick-head"><span class="pick-rank">{rank}</span><div>
          <p class="eyebrow">{esc(pick.get('role', 'Alternative setup'))}</p>
          <p class="eyebrow{research}">{esc(pick['status'])}</p>
          <h3><a href="{esc(pick['detail'])}">{esc(pick['name'])}</a> <span class="card-chip">{pick['cards']} card{'s' if pick['cards'] != 1 else ''}</span><small>{esc(pick['setup'])}</small></h3>
          <p class="pick-why">{esc(pick['why'])}</p>
        </div></div>
        <div class="pick-bars">{''.join(metrics)}</div>
        <div class="pick-links"><a class="button" href="{esc(pick['detail'])}">Details</a><a href="{GITHUB}{esc(pick['guide'])}">Setup guide and quality status</a></div>
      </li>'''


def render(catalog):
    out = [START, '''<section id="featured">
  <div class="wrap">
    <h2 id="t-featured">What should I run?</h2>
    <p class="sub"><strong>1 card:</strong> Qwen 27B for everyday work, Gemma 26B for fast replies. <strong>2 cards:</strong> Qwen 27B shared chat. <strong>3 cards:</strong> use the tested two-card recipe; three-card scaling is not measured here. <strong>4 cards:</strong> Laguna for code, Flash-Next for demanding tasks, LTX for video.</p>
    <p class="sub">For owners of 32 GB Intel Arc Pro B70 cards. We weigh public interest in the model family, how recent and capable it is, and our optimization and quality evidence, then choose one setup per need. <a href="https://github.com/steveseguin/b70-optimization-lab/blob/main/notes/2026-10-10-neural-download-featured-ranking.md">Scores, sources and selection reasons</a>. A certified result does not mean a clean-host installer is ready.</p>
    <p class="sub">Writing speed is in tokens per second (tok/s); a token is about three quarters of a word. Bars compare speed, not capability. Use <a href="#uniform">Same test, every model</a> for the shared test conditions.</p>''']
    for group_id, title, picks in groups(catalog):
        if group_id in ('small-quick', 'other-picks'):
            out.append(f'<details id="{group_id}"><summary>{esc(title)}</summary>')
        else:
            out.append(f'<h3 id="{group_id}">{esc(title)}</h3>')
        out.append('<ol class="pick-list">')
        out.extend(render_pick(p, n) for n, p in enumerate(picks, 1))
        out.append('</ol>')
        if group_id in ('small-quick', 'other-picks'):
            out.append('</details>')
    out.extend(['''    <p class="pick-scale">Bars use fixed scales: one person 250 tok/s; combined users 1,400 tok/s; prompt reading 4,200 tok/s. User counts and tests differ; every value links to its receipt. Video has its own units and no token-speed bar.</p>
    <p class="research-links">All recipes and numbers remain in the tables below and the <a href="models/">model library</a>. H3 means MiniMax-H3, an audio/video generator. It has <a href="https://github.com/steveseguin/b70-optimization-lab/blob/main/experiments/minimax-h3-b70/README.md">public lab notes</a>, but no published site package yet.</p>
  </div>
</section>''', END])
    return '\n'.join(out)


def update(catalog):
    path = ROOT / 'index.html'
    source = path.read_text()
    if START in source:
        begin, finish = source.index(START), source.index(END) + len(END)
    else:
        begin = source.index('<section id="featured">')
        finish = source.index('</section>', begin) + len('</section>')
    expected = source[:begin] + render(catalog) + source[finish:]
    if source != expected:
        path.write_text(expected)
