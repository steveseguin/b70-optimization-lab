# mk_prompt_ids.py (repo engine/tools) + one planted fact: the needle sentence goes in after the first FRAC of the
# document text (at a paragraph break), the request asks for it first. Same tokenizer files and chat template.
import sys, json
from transformers import PreTrainedTokenizerFast
tdir, docp, nchar, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
frac = float(sys.argv[5]) if len(sys.argv) > 5 else 0.02
doc = open(docp).read()[:nchar]
needle = "\n\nNote for the reader: the access code for the archive room is 7194-KESTREL. Keep it safe.\n\n"
k = doc.find("\n\n", int(len(doc) * frac))
doc = doc[:k] + needle + doc[k:]
tok = PreTrainedTokenizerFast(tokenizer_file=tdir + '/tokenizer.json')
tmpl = open(tdir + '/chat_template.jinja').read()
msg = ("Read this document. First state the access code for the archive room that the document mentions, then list "
       "its five most important rules in one short sentence each.\n\n" + doc)
text = tok.apply_chat_template([{"role": "user", "content": msg}], chat_template=tmpl, tokenize=False, add_generation_prompt=True)
ids = tok(text, add_special_tokens=False)["input_ids"]
open(out, 'w').write('\n'.join(map(str, ids)) + '\n')
print(len(ids), 'ids; needle at char', k, 'of', len(doc), '; head:', text[:100].replace('\n', ' | '))
