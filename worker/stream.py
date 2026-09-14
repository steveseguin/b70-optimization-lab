"""Thinking-aware worker SSE transport.

Adapted from check-fp8-practical-session.py; that frozen nonthinking parser is
unchanged. The model's template opens <think> before generation. Its literal
markers (token IDs 248068/248069, special=False) can span SSE content chunks.
Only answer_content may be passed to the worker action parser.
"""
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.request


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def consume_stream(lines, raw_file, started, timeout_seconds=180, clock=time.perf_counter):
    content, reasoning, content_spans = [], [], []
    ids, offsets, frames, finishes, response_ids = [], [], [], [], []
    usage = None
    done = False
    content_length = 0
    separated_seen = False

    def frame():
        nonlocal usage, done, content_length, separated_seen
        if not frames:
            return
        data = '\n'.join(frames)
        frames.clear()
        if data == '[DONE]':
            done = True
            return
        event = json.loads(data)
        if not isinstance(event, dict) or event.get('error'):
            raise ValueError('invalid/error SSE event: ' + repr(event))
        if event.get('id') and event['id'] not in response_ids:
            response_ids.append(event['id'])
        if event.get('usage') is not None:
            usage = event['usage']
        choices = event.get('choices', [])
        if not isinstance(choices, list) or len(choices) > 1:
            raise ValueError('expected at most one choice')
        for choice in choices:
            if not isinstance(choice, dict) or choice.get('index', 0) != 0:
                raise ValueError('unexpected choice')
            offset = clock() - started
            if choice.get('finish_reason') is not None:
                finishes.append(choice['finish_reason'])
            tokens = choice.get('token_ids')
            if tokens is not None:
                if not isinstance(tokens, list) or any(type(i) is not int or i < 0 for i in tokens):
                    raise ValueError('invalid token IDs')
                ids.extend(tokens)
                offsets.extend([offset] * len(tokens))
            delta = choice.get('delta') or {}
            if not isinstance(delta, dict):
                raise ValueError('invalid delta')
            text = delta.get('content')
            if text is not None:
                if not isinstance(text, str):
                    raise ValueError('non-text content')
                if text:
                    content.append(text)
                    content_spans.append((content_length, content_length + len(text), offset))
                    content_length += len(text)
            a, b = delta.get('reasoning'), delta.get('reasoning_content')
            if a is not None and b is not None and a != b:
                raise ValueError('conflicting reasoning fields')
            thought = a if a is not None else b
            if thought is not None:
                separated_seen = True
                if not isinstance(thought, str):
                    raise ValueError('non-text reasoning')
                if thought:
                    reasoning.append(thought)

    for raw in lines:
        raw_file.write(raw)
        raw_file.flush()
        if clock() - started > timeout_seconds:
            raise TimeoutError('request exceeded total stream limit')
        line = raw.decode('utf-8').rstrip('\r\n')
        if not line:
            frame()
            if done:
                break
        elif line.startswith('data:'):
            frames.append(line[5:].removeprefix(' '))
        elif line.startswith((':', 'event:', 'id:', 'retry:')):
            continue
        else:
            raise ValueError('unexpected non-SSE line')
    if frames:
        frame()
    if not done:
        raise ValueError('truncated stream: missing [DONE]')
    if finishes != ['stop']:
        raise ValueError('expected natural stop, received ' + repr(finishes))
    if not isinstance(usage, dict):
        raise ValueError('missing usage')
    prompt, output = usage.get('prompt_tokens'), usage.get('completion_tokens')
    if type(prompt) is not int or prompt < 1 or type(output) is not int or output < 1:
        raise ValueError('invalid prompt/output counts')
    details = usage.get('prompt_tokens_details')
    cached = details.get('cached_tokens') if isinstance(details, dict) else None
    if type(cached) is not int or cached != 0:
        raise ValueError('cached_tokens must be explicitly zero')
    if not ids or len(ids) != output:
        raise ValueError('full output token IDs are required')

    text = ''.join(content)
    if separated_seen:
        # Final fenced code may quote either marker. An inline boundary outside
        # those blocks plus separate reasoning is ambiguous and refused.
        outside_code = re.sub(r'```[^\n]*\n.*?```', '', text, flags=re.DOTALL)
        if '<think>' in outside_code or '</think>' in outside_code:
            raise ValueError('mixed inline and separated reasoning')
        thought, answer, answer_start, form = ''.join(reasoning), text, 0, 'separated'
    else:
        close = text.find('</think>')
        if close < 0:
            raise ValueError('missing inline reasoning closing marker')
        thought = text[:close]
        if thought.lstrip().startswith('<think>'):
            thought = thought.lstrip()[len('<think>'):]
        answer_start = close + len('</think>')
        answer, form = text[answer_start:], 'inline'
    if not answer.strip():
        raise ValueError('empty final answer')
    # Ignore separator whitespace; timestamp the chunk containing the first
    # actual final-answer character, not the first reasoning token.
    first_answer = answer_start + len(answer) - len(answer.lstrip())
    answer_ttft = next(t for start, end, t in content_spans if start <= first_answer < end)
    duration = offsets[-1] - offsets[0]
    rate = (len(ids) - 1) / duration if duration > 0 else None
    return {'text': text, 'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
            'answer_content': answer, 'reasoning_content': thought, 'reasoning_format': form,
            'token_ids': ids, 'token_ids_available': True, 'token_offsets_s': offsets,
            'content_chunk_offsets_s': [t for _, _, t in content_spans], 'usage': usage,
            'prompt_tokens': prompt, 'completion_tokens': output, 'cached_tokens': cached,
            'finish_reasons': finishes, 'response_ids': response_ids,
            'elapsed_s': clock() - started, 'http_ttft_s': offsets[0],
            'http_ttft_definition': 'request start to first token-ID chunk, including reasoning',
            'http_answer_ttft_s': answer_ttft,
            'decode_stream_proxy_tokens_s': rate,
            'decode_stream_proxy_definition': '(all output token IDs - 1) / (last minus first token-ID chunk arrival); includes reasoning; not server decode timing',
            'server_prefill_duration_s': None,
            'server_prefill_note': 'not exposed by this stream; HTTP TTFT is not server prefill'}


def request_one(base_url, payload, directory, opener=urllib.request.urlopen, timeout_seconds=180):
    directory = Path(directory)
    write_json(directory / 'request.json', payload)
    base = base_url.rstrip('/')
    url = base + ('/chat/completions' if base.endswith('/v1') else '/v1/chat/completions')
    request = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'}, method='POST')
    with (directory / 'response.sse').open('wb') as raw:
        started = time.perf_counter()
        try:
            with opener(request, timeout=timeout_seconds) as response:
                write_json(directory / 'response-headers.json', dict(response.headers))
                return consume_stream(response, raw, started, timeout_seconds)
        except urllib.error.HTTPError as exc:
            write_json(directory / 'response-headers.json', dict(exc.headers or {}))
            raw.write(exc.read())
            raise
