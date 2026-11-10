# One user message -> chat-template token ids for own_run_v41 (OWN_PROMPT). Usage:
#   python mk_chat_ids.py <tokenizer dir> <message.txt> <out ids.txt>
import sys
from transformers import PreTrainedTokenizerFast
tdir, msgf, out = sys.argv[1], sys.argv[2], sys.argv[3]
tok = PreTrainedTokenizerFast(tokenizer_file=tdir + '/tokenizer.json')
tmpl = open(tdir + '/chat_template.jinja').read()
msg = open(msgf).read().strip()
text = tok.apply_chat_template([{"role": "user", "content": msg}], chat_template=tmpl, tokenize=False,
                               add_generation_prompt=True)
ids = tok(text, add_special_tokens=False)["input_ids"]
open(out, 'w').write('\n'.join(map(str, ids)) + '\n')
print(len(ids), 'ids:', out)
