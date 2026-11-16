# mk1m.py: reproduce x700k-ids.txt from doc3.txt with the tokenizers library alone (template text taken from the
# decoded x700k ids), then build a longer prompt the same way. args: TOKDIR DOC NCHAR OUT [REF_IDS]
import sys
sys.path.append('/home/steve/.local/lib/python3.12/site-packages')
from tokenizers import Tokenizer
tdir, docp, nchar, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
tok = Tokenizer.from_file(tdir + '/tokenizer.json')
ref = [int(x) for x in open('/home/steve/dsv41-work/prompts/lc/x700k-ids.txt').read().split()]
d3 = open('/home/steve/dsv41-work/prompts/lc/doc3.txt').read()[:2390000]
needle = "\n\nNote for the reader: the access code for the archive room is 7194-KESTREL. Keep it safe.\n\n"
def plant(doc, frac=0.02):
    k = doc.find("\n\n", int(len(doc) * frac)); return doc[:k] + needle + doc[k:], k
d3n, _ = plant(d3)
t700 = tok.decode(ref, skip_special_tokens=False)
i = t700.index(d3n[:300]); j = t700.rindex(d3n[-300:]) + 300
assert t700[i:j] == d3n, 'doc span mismatch'
pre, suf = t700[:i], t700[j:]
chk = tok.encode(pre + d3n + suf, add_special_tokens=False).ids
assert chk == ref, f'x700k not reproduced ({len(chk)} vs {len(ref)})'
print('x700k reproduced:', len(ref), 'ids; prefix', repr(pre[:80]), '... suffix', repr(suf))
doc = open(docp).read()[:nchar]
dn, k = plant(doc)
ids = tok.encode(pre + dn + suf, add_special_tokens=False).ids
open(out, 'w').write('\n'.join(map(str, ids)) + '\n')
print(len(ids), 'ids; needle at char', k, 'of', len(doc))
