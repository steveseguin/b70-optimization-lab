"""Pure CPU accounting; timestamps in seconds, no target arithmetic or device imports."""
import hashlib,json,math,statistics
EOS=(248044,248046)
PROMPT_CLASSES={
 'incident-retrospective':'operations','code-review':'code','customer-email':'prose',
 'sql-debugging':'code','release-plan':'operations','benchmark-analysis':'analysis',
 'architecture-tradeoff':'analysis','bug-report-synthesis':'operations',
 'technical-guide':'documentation','risk-register':'structured-writing',
 'performance-hypotheses':'analysis','decision-memo':'prose'}
PRIMARY='median_of_prompt_class_medians_tok_s_1_100_intervals_after_ttft'

def admit_cap(manifest,count):
    if manifest.get('arithmetic')!='iq3-p17-detmath-v2' or manifest.get('token_cap') not in (64,128):
        raise ValueError('suite identity')
    if type(count) is not int or not 0<count<=manifest['token_cap']:
        raise ValueError('requested max-new exceeds admitted oracle cap')
    return manifest['token_cap']

def window(stamps,event_count):
    if len(stamps)<event_count:return dict(rate=None,event_count=len(stamps),interval_count=None,numerator=None,first=None,last=None,complete=False)
    points=stamps[:event_count]
    if not all(math.isfinite(t) for t in points) or not all(b>a for a,b in zip(points,points[1:])):
        raise ValueError('nonfinite or non-increasing token timestamps')
    return dict(rate=(event_count-1)/(points[-1]-points[0]),event_count=event_count,
        interval_count=event_count-1,numerator=event_count-1,first=points[0],last=points[-1],complete=True)

def median(values):
    values=[v for v in values if isinstance(v,(int,float)) and math.isfinite(v)]
    return statistics.median(values) if values else None

def stats(values):
    values=sorted(v for v in values if isinstance(v,(int,float)) and math.isfinite(v))
    if not values:return dict(median=None,mean=None,p10=None,count=0)
    at=(len(values)-1)*.1;lo=int(at);hi=min(lo+1,len(values)-1)
    return dict(median=statistics.median(values),mean=statistics.mean(values),p10=values[lo]+(values[hi]-values[lo])*(at-lo),count=len(values))

def request_metrics(result,prompt_tokens,cap,retain_steps,start=None,end=None,device=False):
    tokens=result.get('tokens',[]);stamps=[r['completed_monotonic'] for r in result.get('timing_rows',[])]
    if len(stamps)!=len(tokens):raise ValueError('token timestamp count differs from emitted tokens')
    if not all(math.isfinite(t) for t in stamps) or not all(b>a for a,b in zip(stamps,stamps[1:])):raise ValueError('nonfinite or non-increasing token timestamps')
    if start is not None and stamps and (not math.isfinite(start) or start>stamps[0]):raise ValueError('request start after first token')
    # Historical reference drops the final EOS event; submission window counts
    # generated events exactly, including EOS at event 100 if naturally reached.
    non_eos=stamps[:-1] if tokens and tokens[-1] in EOS else stamps
    reference=window(non_eos,min(64,len(non_eos))) if len(non_eos)>1 else window(non_eos,64)
    reference["requested_event_count"]=64
    reference["reached_64"]=len(non_eos)>=64
    fixed64=window(stamps,64)
    submission=window(stamps,100)
    full=window(non_eos,len(non_eos)) if len(non_eos)>1 else dict(rate=None)
    diagnostic=bool(result.get('diagnostic')) or retain_steps!='none'
    eligible_speed=bool(device and not diagnostic)
    ttft=(stamps[0]-start)*1000 if stamps and start is not None else result.get('prompt_wall_ms')
    wall=(stamps[-1]-start) if stamps and start is not None else None
    ended=bool(tokens and tokens[-1] in EOS)
    return dict(retain_steps=retain_steps,diagnostic=diagnostic,
        speed_evidence_eligible=eligible_speed,fixture_retention_is_instrumentation=True,
        token_timestamps=stamps,token_timestamp_unit='seconds, CLOCK_MONOTONIC',
        prompt_tokens=prompt_tokens,output_tokens=len(tokens),requested_max_new=cap,
        cached_tokens=0,usage={'prompt_tokens':prompt_tokens,'completion_tokens':len(tokens),'prompt_tokens_details':{'cached_tokens':0}},
        ttft_ms=ttft,wall_tok_s=(len(tokens)/wall if wall and wall>0 else None),
        full_natural_completion_tok_s=(full['rate'] if ended else None),
        full_cap_limited_tok_s=(full['rate'] if len(tokens)==cap and not ended else None),
        ended_early=len(tokens)<cap,early_end_before_100=len(tokens)<100,
        finish_reason='eos' if ended else 'length' if len(tokens)==cap else 'incomplete',
        output_token_sha256=hashlib.sha256(json.dumps(tokens,separators=(',',':')).encode()).hexdigest(),
        reference_table=reference,reference64=fixed64,submission100=submission,
        fixed64_tok_s=fixed64['rate'] if eligible_speed else None,
        reference64_formula='63 / (t64 - t1), seconds; first 64 generated events, including EOS if event64; null for fewer than64',
        reference_table_formula='(N-1) / (tN - t1), N=min(64, non-EOS generated events); 63/(t64-t1) at cap; null for N<2',
        submission100_formula='99 / (t100 - t1), seconds; first 100 generated events; includes natural EOS at event 100',
        decode_wall_ms=(reference['last']-reference['first'])*1000 if reference.get('first') is not None else 0.,
        decode_intervals=reference['interval_count'],decode_numerator=reference['numerator'],
        decode_event_count=reference['event_count'],decode_first_completed_monotonic=reference['first'],decode_last_completed_monotonic=reference['last'],
        decode_definition='(N-1)/(tN-t1), N=min(64, non-EOS events); seconds; null for N<2',
        decode_tok_s=reference['rate'] if eligible_speed else None,
        tok_s_1_100_intervals_after_ttft=submission['rate'] if eligible_speed else None,
        metric_window_eligible=eligible_speed and submission['complete'])

def aggregate(rows):
    # Never pool repeats: each complete attempt has its own median. The top
    # level summarizes attempt 1; repeated requests do not become cold evidence.
    first=[r for r in rows if r.get('repeat',1)==1]
    valid=[r for r in first if r.get('passed')]
    grouped={}
    for row in valid:
        value=row.get('tok_s_1_100_intervals_after_ttft');kind=row.get('prompt_class')
        if value is not None and kind:grouped.setdefault(kind,[]).append(value)
    classes={k:median(v) for k,v in sorted(grouped.items())}
    return dict(fixed64_statistics=stats(r.get('fixed64_tok_s') for r in valid),reference64_statistics=stats(r.get('decode_tok_s') for r in valid),
        submission100_statistics=stats(r.get('tok_s_1_100_intervals_after_ttft') for r in valid),
        class_balanced_tok_s_1_100_intervals_after_ttft={**stats(classes.values()),'class_medians':classes,'aggregation':'median-of-prompt-class-medians'},
        primary_metric_name=PRIMARY,primary_metric_aggregation='median-of-prompt-class-medians',
        promptTokens=int(median(r['prompt_tokens'] for r in first)) if first and all('prompt_tokens' in r for r in first) else None,
        outputTokens=int(median(r['output_tokens'] for r in first)) if first and all('output_tokens' in r for r in first) else None,
        raw_payload_fields=dict(primaryMetricName=PRIMARY,primaryMetricAggregation='median-of-prompt-class-medians',
          primaryMetricAccounting='inter-token-intervals',metricWindowGeneratedTokens=100,metricWindowIntervals=99,
          realisticSuiteId='rapid-model-snapshots-b70-realistic-v1',realisticSuiteGatePassed=False,
          realisticSuiteCachedTokensAllZero=bool(first) and all(r.get('cached_tokens')==0 for r in first),
          realisticPromptTokenCounts=[r.get('prompt_tokens') for r in first],realisticOutputTokenCounts=[r.get('output_tokens') for r in first],
          realisticSuiteCachedTokens=[r.get('cached_tokens') for r in first],
          promptTokenSha256=[r.get('prompt_token_sha256') for r in first],outputTokenSha256=[r.get('output_token_sha256') for r in first],
          tokenTimestamps=[r.get('token_timestamps') for r in first],ttftMs=[r.get('ttft_ms') for r in first],
          wallTokS=[r.get('wall_tok_s') for r in first],endedEarly=[r.get('ended_early') for r in first],
          requestedMaxNew=[r.get('requested_max_new') for r in first],tokSOutMedian=median(classes.values()),
          promptClassMedians=classes),
        draft_statistics={key:stats(r.get('stats',{}).get(key) for r in valid if isinstance(r.get('stats'),dict)) for key in ('guesses','hits','misses','no_guess')},
        acceptance_statistics=stats(r.get('acceptance') for r in valid),
        hit_miss_cycle_statistics={kind:stats(r.get('hit_miss_cycles',{}).get(kind,{}).get('mean_ms') for r in valid if isinstance(r.get('hit_miss_cycles'),dict)) for kind in ('hit','miss')},
        ttft_statistics=stats(r.get('ttft_ms') for r in valid),wall_rate_statistics=stats(r.get('wall_tok_s') for r in valid),
        realistic_final_gate={'passed':False,'reason':'measurement preparation only; cap below fixed 512 and no promotion attestation; repeats/partial suites never qualify'},
        aggregation_scope='repeat 1 only; ordinary median across prompt rates; primary median across prompt-class medians; see per-repeat summaries')
