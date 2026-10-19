"""Rank packet173 levers from a packet168 census (CPU only; reads small JSON/CSV).

Usage: python3 -B rank_levers.py [--census DIR] [--scenario proxy|cold_weighted|expert_heavy]
DIR is the packet168 screen output containing census-report.json (and
run/census-input.json for the per-rank split). Without --census the prior
scenarios in lever-table.json are used; those are priors, never measurements.
Expected gain = packet160 exact interval replay with rank0 A and C reduced by
f*m_rank0 and rank1 B by f*m_rank1 (f = lever net fraction of its class).
"""
import argparse,csv,json,statistics as st
from pathlib import Path
P=Path(__file__).resolve().parent
CSV=P.parent/'packet160-critical-path/evidence/record-intervals.csv'
ROWS=list(csv.DictReader(CSV.open()))
def v(r,k):return float(r[k] or 0)
for r in ROWS:r['_G']=v(r,'elapsed_ms')-(max(v(r,'D'),v(r,'R')+v(r,'C'))+max(v(r,'B'),v(r,'A')+v(r,'spec_start_offset_ms')))
def metric(sa=0.,sb=0.,sc=0.):
    by={}
    for r in ROWS:
        C=v(r,'C');C=max(0.,C-sc) if C>0 else 0.
        T=max(v(r,'D'),v(r,'R')+C)+max(max(0.,v(r,'B')-sb),max(0.,v(r,'A')-sa)+v(r,'spec_start_offset_ms'))+r['_G']
        by.setdefault((r['prompt_class'],r['prompt_id']),[]).append(T)
    cls={}
    for (c,_),ts in by.items():cls.setdefault(c,[]).append(99000/sum(ts))
    return st.median(st.median(x) for x in cls.values())
BASE=metric();assert abs(BASE-58.798108759182306)<1e-9,BASE
def per_rank(census):
    """Median over prompts of per-rank median(control-arm); None if input absent."""
    path=census/'run/census-input.json'
    if not path.exists():return None
    doc=json.loads(path.read_text());out={}
    for row in doc['observations']:
        if not row.get('probes'):continue
        ranks={0:[],1:[]}
        for p in row['probes']:ranks[p['rank']].append(p['control_ms']-p['arm_ms'])
        out.setdefault(row['view'],{0:[],1:[]})
        for k in (0,1):out[row['view']][k].append(st.median(ranks[k]))
    return {c:{k:st.median(x) for k,x in d.items()} for c,d in out.items()}
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--census',type=Path);ap.add_argument('--scenario',default='proxy')
    a=ap.parse_args();table=json.loads((P/'lever-table.json').read_text())
    if a.census:
        rep=json.loads((a.census/'census-report.json').read_text())
        if not rep.get('passed'):raise SystemExit('census refused: '+str(rep.get('error')))
        summed={r['kernel_class']:r['measured_marginal_ms_per_body_pass'] for r in rep['ranked']}
        split=per_rank(a.census) or {c:{0:m/2,1:m/2} for c,m in summed.items()}
        source='measured census '+str(a.census)
    else:
        summed=table['prior_scenarios_dm_summed_ms'][a.scenario];split={c:{0:m/2,1:m/2} for c,m in summed.items()}
        source='PRIOR scenario '+a.scenario+' (not a measurement)'
    rows=[]
    for lever in table['levers']:
        c=lever['class']
        if c not in split:continue
        m0,m1=split[c][0],split[c][1];g={}
        for k,f in lever['f_net_prior'].items():g[k]=100*(metric(f*m0,f*m1,f*m0)/BASE-1)
        rows.append(dict(id=lever['id'],cls=c,m_summed=summed.get(c),m0=m0,m1=m1,gain=g,hours=lever.get('est_hours'),
          worth=g['mid']>=2.0,kill_floor=g['mid']>=0.5))
    rows.sort(key=lambda r:(r['gain']['mid'],r['gain']['high']),reverse=True)
    print('#',source,'| base',round(BASE,6))
    print('| rank | lever | class | m summed | rank0/rank1 | low/mid/high % | worth (+2% mid) | h |')
    for i,r in enumerate(rows,1):
        print(f"| {i} | {r['id']} | {r['cls']} | {r['m_summed']:.3f} | {r['m0']:.3f}/{r['m1']:.3f} | "
              f"{r['gain']['low']:.2f}/{r['gain']['mid']:.2f}/{r['gain']['high']:.2f} | {'YES' if r['worth'] else ('kill-test only' if r['kill_floor'] else 'no')} | {r['hours']} |")
    if a.census:print('# residual (not causally isolated):',rep['residual']['residual_ms_per_token'])
if __name__=='__main__':main()
