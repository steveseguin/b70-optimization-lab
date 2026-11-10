import sys, json
from transformers import PreTrainedTokenizerFast
from jinja2 import Template
tdir = sys.argv[1]; doc = open(sys.argv[2]).read(); nchar = int(sys.argv[3]); out = sys.argv[4]
tok = PreTrainedTokenizerFast(tokenizer_file=tdir + '/tokenizer.json')
cfg = json.load(open(tdir + '/tokenizer_config.json'))
tmpl = open(tdir + '/chat_template.jinja').read()
msg = "Read this document and then list its five most important rules in one short sentence each.\n\n" + doc[:nchar]
from transformers.utils import chat_template_utils
text = tok.apply_chat_template([{"role": "user", "content": msg}], chat_template=tmpl, tokenize=False, add_generation_prompt=True) if hasattr(tok, 'apply_chat_template') else None
ids = tok(text, add_special_tokens=False)["input_ids"]
open(out, 'w').write('\n'.join(map(str, ids)) + '\n')
print(len(ids), 'ids; head:', text[:120].replace('\n', ' | '))
