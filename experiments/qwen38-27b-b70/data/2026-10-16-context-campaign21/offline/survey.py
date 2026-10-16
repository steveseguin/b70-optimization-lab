import json, sys, collections
path=sys.argv[1]
last=None; n=0
with open(path) as f:
    for l in f:
        n+=1; last=l
d=json.loads(last); b=json.loads(d['body']); m=b['messages']
roles=collections.Counter(x.get('role') for x in m)
keys=collections.Counter(k for x in m for k in x.keys())
ctypes=collections.Counter(type(x.get('content')).__name__ for x in m)
parts=collections.Counter(p.get('type') for x in m if isinstance(x.get('content'),list) for p in x['content'] if isinstance(p,dict))
print(path.split('/')[-5], 'lines',n,'msgs',len(m), dict(roles), dict(keys), dict(ctypes), dict(parts), 'bodykeys', sorted(b.keys()))
