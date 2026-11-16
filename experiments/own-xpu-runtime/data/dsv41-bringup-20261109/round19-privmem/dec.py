# dec.py IDS N: decode the first N ids of an answer file with the model's tokenizer (tokenizers library only).
import sys
sys.path.append('/home/steve/.local/lib/python3.12/site-packages')
from tokenizers import Tokenizer
tok = Tokenizer.from_file('/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-tokenizer/tokenizer.json')
ids = [int(x) for x in open(sys.argv[1]).read().split()][:int(sys.argv[2])]
print(tok.decode(ids, skip_special_tokens=False))
