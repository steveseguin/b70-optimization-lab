"""Stable UTF-8 prefixes from the actual pinned codec's token bytes.

No repeated full-decode prefix slicing: incomplete byte sequences remain in the
incremental decoder until more bytes or final flush. The full canonical decode
is used once at finish as a parity assertion, never to invent earlier deltas.
"""
from __future__ import annotations
import codecs
import hashlib
from pathlib import Path
import chat_codec as C

CODEC=Path(__file__).resolve().parents[1]/'chat_codec.py'
CODEC_SHA='20c0fac1f268eaa2f95b6c86a266e906b92008537f3de157a7e3279d3b74909b'
TOKENIZER_SHA='1c284c06b6a159c39cb9a00acd7cc411ed9adae87b4850e98da5dd4fd33543a7'
MAX_TOKEN_BYTES=128  # Exhaustive census of the pinned vocabulary, tested below.

class DecodeRefusal(ValueError):pass
def require(ok,message):
    if not ok:raise DecodeRefusal(message)

def verify_codec(codec):
    require(Path(C.__file__).resolve()==CODEC and hashlib.sha256(CODEC.read_bytes()).hexdigest()==CODEC_SHA,
            'canonical codec source changed')
    require(type(codec) is C.PinnedChatCodec,'exact canonical pinned codec required')
    require(hashlib.sha256(C.TOKENIZER.read_bytes()).hexdigest()==TOKENIZER_SHA and
            codec.provenance['tokenizer_source_sha256']==TOKENIZER_SHA,'tokenizer source changed')

def token_bytes(codec,token_id):
    require(type(token_id) is int and 0<=token_id<codec.vocab,'token outside admitted vocabulary')
    tokenizer=codec._tokenizer  # Exact private layout admitted by both source hashes.
    text=tokenizer.tokens[token_id]
    raw=text.encode('utf-8') if text in tokenizer.special else bytes(tokenizer.dec[c] for c in text)
    require(len(raw)<=MAX_TOKEN_BYTES,'token byte extent exceeds pinned vocabulary bound')
    return raw

class TokenDecoder:
    def __init__(self,codec,*,maximum_tokens=512):
        verify_codec(codec)
        require(type(maximum_tokens) is int and 1<=maximum_tokens<=512,'bounded completion required')
        self.codec,self.maximum=codec,maximum_tokens
        self._decode=codecs.getincrementaldecoder('utf-8')(errors='replace')
        self.tokens=[];self._pieces=[];self._terminal=False;self._finished=False;self.failure=None

    def _usable(self):
        require(self.failure is None,'decoder has failed')
        require(not self._finished,'decoder already finished')

    def feed(self,token_id):
        self._usable()
        try:
            require(not self._terminal,'token after terminal ID')
            require(len(self.tokens)<self.maximum,'completion token cap exceeded')
            raw=token_bytes(self.codec,token_id)
            self.tokens.append(token_id)
            self._terminal=token_id in self.codec.terminal_token_ids
            delta='' if self._terminal else self._decode.decode(raw,final=False)
            self._pieces.append(delta)
            return delta
        except BaseException as error:self.failure=error;raise

    def finish(self,expected_tokens):
        self._usable()
        try:
            require(type(expected_tokens) in (list,tuple) and all(type(t) is int for t in expected_tokens)
                    and list(expected_tokens)==self.tokens and self.tokens,
                    'native completion/token observer mismatch')
            tail=self._decode.decode(b'',final=True);self._pieces.append(tail)
            ids=self.tokens[:-1] if self._terminal else self.tokens
            require(''.join(self._pieces)==self.codec.decode(ids),'incremental/full decode parity failed')
            self._finished=True
            return tail
        except BaseException as error:self.failure=error;raise

    @property
    def text(self):return ''.join(self._pieces)
