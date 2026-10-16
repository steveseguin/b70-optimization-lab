import json, sys
path=sys.argv[1]; t=[]
for l in open(path):
    d=json.loads(l)
    if d.get('path','').endswith('/chat/completions'): t.append(d['t'])
g=[b-a for a,b in zip(t,t[1:])]
big=lambda x:[v for v in g if v>x]
print(json.dumps({'n':len(g),'>30s':len(big(30)),'>30s_sum':round(sum(big(30))),'>60s':len(big(60)),'>60s_sum':round(sum(big(60))),'>120s':len(big(120)),'>120s_sum':round(sum(big(120))),'total':round(sum(g)), 'top5':[round(v) for v in sorted(g)[-5:]]}))
