"""Publisher GGUF vocabulary/merges and Qwen35 pretokenization, CPU only."""
import regex

PATTERN = r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?[\p{L}\p{M}]+|\p{N}| ?[^\s\p{L}\p{M}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+"


class Tokenizer:
    def __init__(self, meta):
        assert meta['tokenizer.ggml.pre'] == 'qwen35'
        self.tokens = meta['tokenizer.ggml.tokens']
        self.vocab = {s:i for i,s in enumerate(self.tokens)}
        self.ranks = {tuple(s.split(' ')):i for i,s in enumerate(meta['tokenizer.ggml.merges'])}
        bs = list(range(33,127))+list(range(161,173))+list(range(174,256))
        cs = list(bs)
        for b in range(256):
            if b not in bs:
                bs.append(b); cs.append(256+len(cs)-188)
        self.enc = dict(zip(bs,map(chr,cs)))
        self.dec = {v:k for k,v in self.enc.items()}
        self.special = {s:i for i,s in enumerate(self.tokens) if meta['tokenizer.ggml.token_type'][i] in (3,4)}
        self.split = regex.compile('('+'|'.join(regex.escape(s) for s in sorted(self.special,key=len,reverse=True))+')')

    def encode(self, text):
        ids = []
        for segment in self.split.split(text):
            if segment in self.special:
                ids.append(self.special[segment]); continue
            for match in regex.findall(PATTERN, segment):
                word = [self.enc[b] for b in match.encode('utf-8')]
                while len(word)>1:
                    rank,pos = min((self.ranks.get((a,b),10**12),j) for j,(a,b) in enumerate(zip(word,word[1:])))
                    if rank == 10**12: break
                    word[pos:pos+2] = [word[pos]+word[pos+1]]
                ids.extend(self.vocab[s] for s in word)
        return ids

    def decode(self, ids):
        out = bytearray()
        for i in ids:
            s = self.tokens[i]
            out.extend(s.encode() if s in self.special else bytes(self.dec[c] for c in s))
        return out.decode('utf-8',errors='replace')
