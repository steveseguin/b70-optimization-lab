"""CPU-only chat request handling for the SC117 LAN service: pinned template, tokenizer, response shaping.

No model inference happens here. Rendering uses the exact GGUF chat template that
coverage/tokenizer.py verifies (same tokenizer.json, vocabulary, merges, template).
"""
import importlib.util, json, os, re, time, uuid
from pathlib import Path

P = Path(__file__).resolve().parent
LANE = P.parents[1]
EOS = (248044, 248046)  # <|endoftext|>, <|im_end|>
THINK_END = 248069      # </think>
# Engine context (prompt + output tokens). SC117_CONTEXT is read by this module and adapter6.py alike; the engine
# admits 4096 and 32768 for the 23/25 split with the draft on rank 0 (main.cpp), and its RoPE table ends at 32768.
CONTEXT = int(os.environ.get('SC117_CONTEXT', '4096'))
if CONTEXT not in (4096, 32768):
    raise RuntimeError('SC117_CONTEXT must be 4096 or 32768')
DEFAULT_MAX_TOKENS = 512
MODEL_ID = 'sc117-qwen3.8-flash-next-iq3s-ownrt'
ROLES = ('system', 'user', 'assistant', 'tool')


class RequestError(ValueError):
    """Client error: reported as HTTP 400 without touching the engine."""


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Chat:
    def __init__(self):
        T = _load(LANE / 'coverage/tokenizer.py', 'sc117_lan_tokenizer')
        # load() verifies the tokenizer file, full vocabulary/merges and template hashes.
        self.tok, single, self.authority = T.load()
        from jinja2.sandbox import ImmutableSandboxedEnvironment
        meta = json.loads(T.CENSUS.read_text())['metadata']
        env = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)

        def fail(message):
            raise RequestError('chat template: ' + str(message))
        env.globals['raise_exception'] = fail
        # The chat template renders tools and tool-call arguments with tojson. Use the Hugging Face definition (no
        # HTML escaping, keys in given order) that apply_chat_template and vLLM use, not Jinja's sorted, HTML-safe one.
        env.filters['tojson'] = lambda x, ensure_ascii=False, indent=None, separators=None, sort_keys=False: json.dumps(
            x, ensure_ascii=ensure_ascii, indent=indent, separators=separators, sort_keys=sort_keys)
        self.template = env.from_string(meta['tokenizer.chat_template']['value'])
        # The multi-message renderer must agree with the validated single-message renderer.
        probe = 'Explain why the sky looks blue in three short sentences.'
        if self.render([{'role': 'user', 'content': probe}], False) != single(probe):
            raise RuntimeError('multi-message renderer disagrees with pinned renderer')

    def render(self, messages, thinking, tools=None):
        return self.template.render(messages=messages, add_generation_prompt=True,
                                    enable_thinking=bool(thinking), tools=tools or None)

    def encode(self, text):
        return self.tok.encode(text, add_special_tokens=False).ids

    def decode(self, ids):
        return self.tok.decode(list(ids), skip_special_tokens=True)


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if not isinstance(part, dict) or part.get('type') != 'text' or not isinstance(part.get('text'), str):
                raise RequestError('only text content parts are supported (no images/audio)')
            parts.append(part['text'])
        return ''.join(parts)
    if content is None:
        return ''
    raise RequestError('message content must be a string or a list of text parts')


def _tool_list(body):
    tools = body.get('tools')
    if tools is None:
        return None
    if not isinstance(tools, list):
        raise RequestError('tools must be a list')
    for t in tools:
        f = t.get('function') if isinstance(t, dict) else None
        if not isinstance(t, dict) or t.get('type') != 'function' or not isinstance(f, dict) or not isinstance(f.get('name'), str) or not f['name']:
            raise RequestError('each tool must be {"type": "function", "function": {"name": ..., "parameters": ...}}')
    return tools or None


def _assistant_tool_calls(calls):
    """OpenAI tool_calls (arguments as a JSON string) -> the template's form (arguments as a mapping)."""
    if not isinstance(calls, list) or not calls:
        raise RequestError('tool_calls must be a non-empty list')
    out = []
    for c in calls:
        f = c.get('function') if isinstance(c, dict) else None
        if not isinstance(f, dict) or not isinstance(f.get('name'), str) or not f['name']:
            raise RequestError('each tool call needs function.name')
        args = f.get('arguments')
        if args is None or args == '':
            args = {}
        elif isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                raise RequestError(f'tool call {f["name"]}: arguments are not valid JSON')
        if not isinstance(args, dict):
            raise RequestError(f'tool call {f["name"]}: arguments must be a JSON object')
        out.append({'type': 'function', 'function': {'name': f['name'], 'arguments': args}})
    return out


def parse(body, chat):
    """Validate an OpenAI-style chat request; return a plan dict for the engine."""
    if not isinstance(body, dict):
        raise RequestError('request body must be a JSON object')
    messages = body.get('messages')
    if not isinstance(messages, list) or not messages:
        raise RequestError('messages must be a non-empty list')
    clean = []
    for m in messages:
        if isinstance(m, dict) and m.get('role') == 'developer':
            m = dict(m, role='system')
        if not isinstance(m, dict) or m.get('role') not in ROLES:
            raise RequestError('each message needs role system, user or assistant')
        item = {'role': m['role'], 'content': _text(m.get('content'))}
        if m.get('tool_calls'):
            if m['role'] != 'assistant':
                raise RequestError('only assistant messages can carry tool_calls')
            item['tool_calls'] = _assistant_tool_calls(m['tool_calls'])
        clean.append(item)
    tools = _tool_list(body)
    choice = body.get('tool_choice')
    if choice not in (None, 'auto', 'none'):
        raise RequestError('tool_choice must be "auto" or "none" (forced or required calls are not supported)')
    if body.get('n') not in (None, 1):
        raise RequestError('only n=1 is supported')
    kwargs = body.get('chat_template_kwargs') or {}
    if not isinstance(kwargs, dict):
        raise RequestError('chat_template_kwargs must be an object')
    thinking = kwargs.get('enable_thinking', False)
    if not isinstance(thinking, bool):
        raise RequestError('enable_thinking must be boolean')
    stop = body.get('stop')
    if stop is None:
        stop = []
    elif isinstance(stop, str):
        stop = [stop]
    if not isinstance(stop, list) or len(stop) > 4 or not all(isinstance(s, str) and s for s in stop):
        raise RequestError('stop must be a string or up to 4 non-empty strings')
    rendered = chat.render(clean, thinking, tools)
    ids = chat.encode(rendered)
    room = CONTEXT - len(ids)
    if room < 1:
        raise RequestError(f'prompt is {len(ids)} tokens; context is {CONTEXT}')
    requested = body.get('max_completion_tokens', body.get('max_tokens'))
    if requested is None:
        max_new = min(DEFAULT_MAX_TOKENS, room)
    else:
        if isinstance(requested, float) and requested.is_integer():
            requested = int(requested)
        if type(requested) is not int or requested < 1:
            raise RequestError('max_tokens must be a positive integer')
        max_new = min(requested, room)  # clamp to the context instead of refusing
    ignored = sorted(k for k in ('temperature', 'top_p', 'top_k', 'seed', 'presence_penalty',
                                 'frequency_penalty', 'repetition_penalty', 'min_p')
                     if body.get(k) not in (None, 0, 1, 0.0, 1.0))
    return dict(prompt_ids=ids, max_new=max_new, thinking=thinking, stop=stop,
                tools=tools, parse_tool_calls=bool(tools) and choice != 'none',
                stream=bool(body.get('stream')), include_usage=bool((body.get('stream_options') or {}).get('include_usage')),
                ignored_sampling=ignored)


def shape(req, tokens, chat):
    """Split engine output into content/reasoning; apply stop strings."""
    finish = 'length'
    out = list(tokens)
    if out and out[-1] in EOS:
        out.pop()
        finish = 'stop'
    reasoning = None
    if req['thinking'] and THINK_END in out:
        cut = out.index(THINK_END)
        reasoning = chat.decode(out[:cut]).strip()
        out = out[cut + 1:]
    content = chat.decode(out)
    if req['thinking'] and reasoning is None and finish == 'length':
        # Ran out of tokens while still thinking.
        reasoning, content = content.strip(), ''
    content = content.lstrip('\n') if req['thinking'] else content
    for s in req['stop']:
        at = content.find(s)
        if at >= 0:
            content = content[:at]
            finish = 'stop'
    return content, reasoning, finish


_CALL = re.compile(r'<tool_call>\s*<function=([^>\n]+)>(.*?)</function>\s*</tool_call>', re.S)
_PARAM = re.compile(r'<parameter=([^>\n]+)>\n?(.*?)\n?</parameter>', re.S)


def _param_types(tools, name):
    for t in tools or ():
        f = t['function']
        if f['name'] == name:
            props = (f.get('parameters') or {}).get('properties') or {}
            return {k: (v or {}).get('type') for k, v in props.items() if isinstance(v, dict)}
    return {}


def tool_calls(req, content):
    """Split the template's XML tool-call format out of the content: (content or None, OpenAI tool_calls)."""
    if not req.get('parse_tool_calls') or '<tool_call>' not in content:
        return content, []
    calls = []
    for i, m in enumerate(_CALL.finditer(content)):
        name = m.group(1).strip()
        types = _param_types(req['tools'], name)
        args = {}
        for p in _PARAM.finditer(m.group(2)):
            key, raw = p.group(1).strip(), p.group(2)
            value = raw
            if types.get(key) != 'string':
                try:
                    value = json.loads(raw)
                except ValueError:
                    value = raw
            args[key] = value
        calls.append({'id': 'call_' + uuid.uuid4().hex[:24], 'type': 'function',
                      'function': {'name': name, 'arguments': json.dumps(args, ensure_ascii=False)}})
    if not calls:
        return content, []
    head = content[:content.index('<tool_call>')].rstrip()
    return (head or None), calls


def completion(req, tokens, result, chat):
    content, reasoning, finish = shape(req, tokens, chat)
    content, calls = tool_calls(req, content)
    message = {'role': 'assistant', 'content': content}
    if calls:
        message['tool_calls'] = calls
        finish = 'tool_calls'
    if reasoning is not None:
        message['reasoning_content'] = reasoning
    return {
        'id': 'chatcmpl-' + uuid.uuid4().hex, 'object': 'chat.completion', 'created': int(time.time()),
        'model': MODEL_ID,
        'choices': [{'index': 0, 'message': message, 'finish_reason': finish}],
        'usage': {'prompt_tokens': len(req['prompt_ids']), 'completion_tokens': len(tokens),
                  'total_tokens': len(req['prompt_ids']) + len(tokens),
                  # Conversation continuation reuses the held state for this many prompt tokens (0 = fresh request).
                  'prompt_tokens_details': {'cached_tokens': int((result or {}).get('continued_from') or 0)}},
        'ownrt': result,
    }


def chunks(full):
    """Whole-response SSE chunks (the engine returns at completion; no per-token streaming)."""
    base = {k: full[k] for k in ('id', 'created', 'model')}
    base['object'] = 'chat.completion.chunk'
    msg = full['choices'][0]['message']
    delta = {'role': 'assistant', 'content': msg['content']}
    if msg.get('tool_calls'):
        delta['tool_calls'] = [dict(c, index=i) for i, c in enumerate(msg['tool_calls'])]
    if 'reasoning_content' in msg:
        delta['reasoning_content'] = msg['reasoning_content']
    yield dict(base, choices=[{'index': 0, 'delta': delta, 'finish_reason': None}])
    yield dict(base, choices=[{'index': 0, 'delta': {}, 'finish_reason': full['choices'][0]['finish_reason']}])


class Streamer:
    """Incremental text deltas from confirmed token IDs.

    Emits only text that can no longer change: withholds a trailing incomplete
    UTF-8 character and any tail that could begin a stop string. finish() sends
    whatever completes the exact final text from shape(), so the concatenated
    deltas always equal the non-streaming response.
    """

    def __init__(self, req, chat):
        self.req, self.chat = req, chat
        self.ids = []
        self.sent = {'content': '', 'reasoning_content': ''}
        self.stopped = False
        self.mismatch = False

    def _views(self):
        out = [t for t in self.ids if t not in EOS]
        if self.req['thinking']:
            if THINK_END in out:
                cut = out.index(THINK_END)
                reasoning = self.chat.decode(out[:cut]).strip()
                content = self.chat.decode(out[cut + 1:]).lstrip('\n')
                return reasoning, content, True
            return self.chat.decode(out).lstrip(), '', False
        return '', self.chat.decode(out), True

    @staticmethod
    def _stable(text):
        return text[:-1] if text.endswith('�') else text

    def _safe_content(self, text):
        text = self._stable(text)
        for s in self.req['stop']:
            at = text.find(s)
            if at >= 0:
                self.stopped = True
                return text[:at]
        safe = len(text)
        for s in self.req['stop']:
            for k in range(min(len(s) - 1, len(text)), 0, -1):
                if text.endswith(s[:k]):
                    safe = min(safe, len(text) - k)
                    break
        return text[:safe]

    def _delta(self, field, text):
        prev = self.sent[field]
        if not text.startswith(prev):
            self.mismatch = True
            return None
        if len(text) > len(prev):
            self.sent[field] = text
            return text[len(prev):]
        return None

    def feed(self, token):
        if self.stopped:
            return []
        self.ids.append(token)
        reasoning, content, answering = self._views()
        out = []
        if self.req['thinking']:
            # reasoning is strip()ed at the end: withhold trailing whitespace until it is followed.
            r = self._stable(reasoning) if not answering else reasoning
            d = self._delta('reasoning_content', r.rstrip() if not answering else r)
            if d:
                out.append(('reasoning_content', d))
        if answering and not self.req.get('parse_tool_calls'):
            d = self._delta('content', self._safe_content(content))
            if d:
                out.append(('content', d))
        return out

    def finish(self, tokens):
        content, reasoning, finish = shape(self.req, tokens, self.chat)
        content, calls = tool_calls(self.req, content)
        out = []
        for field, final in (('reasoning_content', reasoning or ''), ('content', content or '')):
            prev = self.sent[field]
            if final.startswith(prev):
                if len(final) > len(prev):
                    out.append((field, final[len(prev):]))
            else:
                self.mismatch = True
        if calls:
            out.append(('tool_calls', [dict(c, index=i) for i, c in enumerate(calls)]))
            finish = 'tool_calls'
        return out, finish
