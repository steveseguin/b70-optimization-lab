"""Pinned, CPU-only text chat codec. No model loading or tokenizer fallback.

Use the existing vllm-xpu Python environment (regex + jinja2). The constructor
reads only the pinned GGUF header; decode preserves every token and whitespace.
"""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import stat
import struct
from types import MappingProxyType, ModuleType

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
ORACLE = LAB / 'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle'
TOKENIZER = ORACLE / 'tokenizer.py'
HEADER_READER = HERE.parent / 'stage1/packet1b/loaders/headers.py'
IDENTITY = HERE.parent / 'stage2/packet181-session-swap-v3/one-card/tokenizer-identity.tsv'
TEMPLATE = HERE / 'chat_template-7c1460a9.jinja'
DEFAULT_GGUF = Path('/mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS/Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00003.gguf')
HEADER_BYTES = 10946618
HEADER_SHA = '7c1460a95eb2e95377c32b14deb92cf74fe504d4feb5a62a40d48f78e9e0dcb8'
TOKENIZER_SHA = '1c284c06b6a159c39cb9a00acd7cc411ed9adae87b4850e98da5dd4fd33543a7'
READER_SHA = '7503587cb34eb2ed5464ad78d429817e6abc4121c0db81ffc6011da58a54c9fa'
TEMPLATE_SHA = '12827f24b742ea4e80cdc12dbcf9622227056b9f797252a3149263d4f9aaadce'
IDENTITY_SHA = '5e88b69b8c30b6f79807bbbad23126e3262c5fd9be87e338b25e48bf7d15d32b'
VOCAB_SHA = '7a0e612475366f8d368dbfee6a0a01336f1059e71fa98d91300eb62abd996a64'
MAX_MESSAGES = 64
MAX_TEXT_BYTES = 65536
MAX_IDS = 32768


class CodecRefusal(ValueError):
    """Invalid caller text or a dependency outside the fixed codec identity."""


def _require(ok, reason):
    if not ok:
        raise CodecRefusal(reason)


def _pinned(path, digest, limit):
    with Path(path).open('rb') as stream:
        raw = stream.read(limit + 1)
    _require(len(raw) <= limit and hashlib.sha256(raw).hexdigest() == digest,
             'source pin mismatch: ' + str(path))
    return raw


def _module(path, digest):
    raw = _pinned(path, digest, 1024 * 1024)
    module = ModuleType('_pinned_chat_' + path.stem)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def _text(value):
    _require(type(value) is str, 'text must be a string')
    try:
        size = len(value.encode('utf-8'))
    except UnicodeEncodeError as exc:
        raise CodecRefusal('invalid Unicode scalar') from exc
    _require(size <= MAX_TEXT_BYTES, 'text byte bound')
    return size


class PinnedChatCodec:
    def __init__(self, *, gguf_path=DEFAULT_GGUF):
        # All source executes from the same bytes whose hash was just verified.
        reader = _module(HEADER_READER, READER_SHA)
        tokenizer_module = _module(TOKENIZER, TOKENIZER_SHA)
        identity_bytes = _pinned(IDENTITY, IDENTITY_SHA, 16384)
        template_bytes = _pinned(TEMPLATE, TEMPLATE_SHA, 65536)
        path = Path(gguf_path)
        _require(path.is_absolute(), 'absolute GGUF path required')
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            _require(stat.S_ISREG(before.st_mode), 'GGUF must be regular')
            raw = stream.read(HEADER_BYTES)
            after = os.fstat(stream.fileno())
        _require((before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                 (after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'GGUF changed')
        _require(hashlib.sha256(raw).hexdigest() == HEADER_SHA, 'GGUF header pin mismatch')
        parsed = reader.gguf_header(io.BytesIO(raw), before.st_size)
        _require(parsed['header_bytes_read'] == HEADER_BYTES, 'header extent mismatch')
        meta = parsed['metadata']
        _require(meta['tokenizer.chat_template'].encode('utf-8') == template_bytes,
                 'header/template mismatch')
        _require(meta['tokenizer.ggml.pre'] == 'qwen35' and
                 meta['tokenizer.ggml.add_bos_token'] is False, 'tokenizer mode mismatch')
        self._tokenizer = tokenizer_module.Tokenizer(meta)
        self.vocab = len(self._tokenizer.tokens)
        _require(self.vocab == 248320, 'vocabulary size mismatch')
        # Reconstruct the exact native vocab.bin byte stream, without writing it.
        vocab_hash = hashlib.sha256()
        for token in self._tokenizer.tokens:
            b = (token.encode('utf-8') if token in self._tokenizer.special else
                 bytes(self._tokenizer.dec[c] for c in token))
            vocab_hash.update(struct.pack('<I', len(b)))
            vocab_hash.update(b)
        _require(vocab_hash.hexdigest() == VOCAB_SHA, 'decoded vocabulary pin mismatch')
        tsv = dict(line.split('\t', 1) for line in identity_bytes.decode().splitlines()
                   if line and not line.startswith('#'))
        expected = dict(format='ownrt.tokenizer-identity.v1', gguf_header_sha256=HEADER_SHA,
                        tokenizer_source_sha256=TOKENIZER_SHA, vocab_bin_sha256=VOCAB_SHA)
        _require(all(tsv.get(k) == v for k, v in expected.items()), 'native identity TSV mismatch')
        self.tokenizer_identity = MappingProxyType(dict(file_sha256=IDENTITY_SHA, **expected))
        _require(meta['tokenizer.ggml.eos_token_id'] == 248046 and
                 meta['tokenizer.ggml.bos_token_id'] == 248044 and
                 meta['tokenizer.ggml.padding_token_id'] == 248044, 'terminal header roles mismatch')
        for token_id, name in ((248044, '<|endoftext|>'), (248046, '<|im_end|>')):
            _require(self._tokenizer.tokens[token_id] == name and
                     meta['tokenizer.ggml.token_type'][token_id] == 3, 'terminal name/type mismatch')
        self.terminal_token_ids = frozenset({248044, 248046})
        self.terminal_metadata = MappingProxyType(dict(gguf_eos_id=248046,
            gguf_eos_name='<|im_end|>', gguf_bos_padding_id=248044,
            gguf_bos_padding_name='<|endoftext|>', gguf_header_sha256=HEADER_SHA))
        from jinja2.sandbox import ImmutableSandboxedEnvironment
        import jinja2
        import regex
        env = ImmutableSandboxedEnvironment()
        def refuse(message):
            raise CodecRefusal(str(message))
        env.globals['raise_exception'] = refuse
        self._template = env.from_string(template_bytes.decode('utf-8'))
        self.provenance = MappingProxyType(dict(header_reader_sha256=READER_SHA,
            template_sha256=TEMPLATE_SHA, tokenizer_source_sha256=TOKENIZER_SHA,
            gguf_header_sha256=HEADER_SHA, header_bytes_read=HEADER_BYTES,
            vocab_bin_sha256=VOCAB_SHA, jinja2_version=jinja2.__version__,
            regex_version=regex.__version__, thinking=False))

    def render(self, messages):
        _require(type(messages) is list and 1 <= len(messages) <= MAX_MESSAGES,
                 'messages must be a bounded nonempty list')
        copied, total = [], 0
        for message in messages:
            _require(type(message) is dict and set(message) == {'role', 'content'},
                     'each message requires only role/content')
            role = message['role']
            _require(type(role) is str and role in {'system', 'developer', 'user', 'assistant'},
                     'unsupported role')
            total += _text(message['content'])
            _require(total <= MAX_TEXT_BYTES, 'message byte bound')
            copied.append(dict(role=role, content=message['content']))
        result = self._template.render(messages=copied, add_generation_prompt=True,
                                       enable_thinking=False)
        _text(result)
        return result

    def encode(self, text):
        _text(text)
        ids = self._tokenizer.encode(text)
        _require(len(ids) <= MAX_IDS, 'encoded token bound')
        return ids

    def decode(self, token_ids):
        _require(type(token_ids) in (list, tuple) and len(token_ids) <= MAX_IDS,
                 'token IDs must be a bounded sequence')
        _require(all(type(x) is int and 0 <= x < self.vocab for x in token_ids),
                 'token ID outside vocabulary')
        # Raw oracle decode, including UTF-8 replacement for incomplete byte pieces.
        # Only the caller may remove a terminal ID; never strip rendered text.
        return self._tokenizer.decode(token_ids)
