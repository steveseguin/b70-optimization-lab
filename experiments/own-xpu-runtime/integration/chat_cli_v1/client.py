"""Bounded attach-only HTTP client. No native imports, owner control or retry.

SSE parser adapted from packet201/client_pilot.py; see README for exact pin.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import http.client
import json
import re
import sys
import time
from urllib.parse import urlsplit

SSE_LIMIT = 128 * 1024
HISTORY_LIMIT = 65536

class Refusal(ValueError):
    pass

class HTTPFailure(RuntimeError):
    def __init__(self, status, body):
        super().__init__('HTTP ' + str(status) + ': ' + str(body)[:2048])
        self.status, self.body = status, body

def require(ok, reason):
    if not ok:
        raise Refusal(reason)

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result

def parse_json(raw):
    return json.loads(raw.decode('utf-8', errors='strict'), object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(Refusal('nonfinite JSON')))

def address(endpoint):
    parsed = urlsplit(endpoint)
    require(parsed.scheme == 'http' and parsed.hostname == '127.0.0.1' and
            parsed.username is None and parsed.password is None and
            parsed.path in ('', '/') and not parsed.query and not parsed.fragment and
            parsed.port is not None and 1 <= parsed.port <= 65535,
            'explicit http://127.0.0.1:PORT endpoint required')
    return parsed.hostname, parsed.port

def validate_completion(body, model, maximum):
    require(type(body) is dict and set(body) == {'id','object','created','model','choices','usage'},
            'completion fields differ')
    require(body['object'] == 'chat.completion' and body['model'] == model and
            type(body['id']) is str and re.fullmatch(r'chatcmpl-h[0-9a-f]{32}-[0-9a-f]{16}',body['id']) and
            type(body['created']) is int and 0 <= body['created'] < 2**63, 'completion identity differs')
    choices = body['choices']
    require(type(choices) is list and len(choices) == 1 and type(choices[0]) is dict and
            set(choices[0]) == {'index','message','finish_reason'}, 'completion choice differs')
    choice = choices[0]
    require(type(choice['index']) is int and choice['index'] == 0 and
            choice['finish_reason'] in ('stop','length') and type(choice['message']) is dict and
            set(choice['message']) == {'role','content'} and choice['message']['role'] == 'assistant' and
            type(choice['message']['content']) is str, 'completion message differs')
    choice['message']['content'].encode('utf-8', errors='strict')
    usage = body['usage']
    require(type(usage) is dict and set(usage) == {'prompt_tokens','completion_tokens','total_tokens'} and
            all(type(n) is int and n >= 0 for n in usage.values()), 'integer usage required')
    require(0 < usage['completion_tokens'] <= maximum and 0 < usage['prompt_tokens'] and
            usage['total_tokens'] == usage['prompt_tokens'] + usage['completion_tokens'] and
            usage['total_tokens'] <= 4096, 'usage exceeds admitted context or completion cap')
    require(choice['finish_reason'] != 'length' or usage['completion_tokens'] == maximum,
            'length finish differs from completion cap')
    return body

def read_sse(reply, *, maximum, receive_socket, model, on_delta, deadline):
    """Consume bounded actual frames incrementally; clocks describe receipt only.

    No frame timing is called token-generation latency. Raw bytes (base64) and
    monotonic receive offsets survive parser failure on the original exception.
    EOF is required after the one final marker, with no trailing bytes.
    """
    raw=bytearray();pending=bytearray();times=[];events=[];started=time.monotonic_ns();deadline=deadline
    identity=None;pieces=[];finish=None;usage=None;done=False
    def deadline_guard():
        remaining=deadline-time.monotonic()
        require(remaining>0,'SSE receive deadline exceeded')
        require(receive_socket is not None,'retained response socket required')
        receive_socket.settimeout(min(900,remaining))
    def read_line():
        while b'\n' not in pending:
            require(len(pending)<=8192,'SSE line evidence bound exceeded')
            deadline_guard()
            chunk=reply.read1(min(4096,SSE_LIMIT-len(raw)+1))
            extent=len(raw)+len(chunk)
            raw.extend(chunk[:max(0,SSE_LIMIT-len(raw))])
            require(extent<=SSE_LIMIT,'SSE response evidence bound exceeded')
            pending.extend(chunk)
            if not chunk:
                line=bytes(pending);pending.clear();return line
        end=pending.index(b'\n')+1
        require(end<=8192,'SSE line evidence bound exceeded')
        line=bytes(pending[:end]);del pending[:end]
        return line
    def evidence():
        return dict(raw_sse_base64=base64.b64encode(raw).decode('ascii'),raw_sha256=digest(raw),
                    received_frames=times,elapsed_ns=time.monotonic_ns()-started,
                    timing_scope='client observed complete-frame receipt; not native token-generation latency')
    try:
        require(reply.getheader('Content-Type') == 'text/event-stream; charset=utf-8','SSE content type differs')
        while True:
            line=read_line()
            require(line and line.startswith(b'data: ') and line.endswith(b'\n') and b'\r' not in line,
                    'strict LF data frame required; premature EOF refused')
            require(read_line()==b'\n','exact SSE blank delimiter required')
            times.append([time.monotonic_ns()-started,len(raw)])
            require(len(times)<=maximum+4,'SSE frame count exceeds token cap')
            payload=line[6:-1]
            if payload==b'[DONE]':
                require(finish is not None and not done,'DONE before terminal or repeated')
                done=True
                require(not pending,'trailing bytes after DONE')
                deadline_guard()
                trailing=reply.read1(1)
                if trailing:raw.extend(trailing[:max(0,SSE_LIMIT-len(raw))])
                require(not trailing,'trailing bytes after DONE')
                break
            require(not done and finish is None,'frame after terminal')
            def pairs(items):
                result={}
                for key,value in items:
                    require(key not in result,'duplicate SSE JSON key');result[key]=value
                return result
            event=json.loads(payload.decode('utf-8',errors='strict'),object_pairs_hook=pairs,
                             parse_constant=lambda _:(_ for _ in ()).throw(RuntimeError('nonfinite SSE JSON')))
            require(type(event) is dict and set(event)<= {'id','object','created','model','choices','usage'} and
                    {'id','object','created','model','choices'} <= set(event), 'SSE chunk fields differ')
            require(event['object']=='chat.completion.chunk' and event['model']==model and
                    type(event['created']) is int and 0<=event['created']<2**63 and
                    type(event['id']) is str and re.fullmatch(r'chatcmpl-h[0-9a-f]{32}-[0-9a-f]{16}',event['id']),
                    'SSE chunk identity differs')
            current=(event['id'],event['model'],event['created'])
            if identity is None:identity=current
            require(current==identity,'SSE identity changed between frames')
            choices=event['choices']
            require(type(choices) is list and len(choices)==1 and type(choices[0]) is dict and
                    set(choices[0])=={'index','delta','finish_reason'} and type(choices[0]['index']) is int and
                    choices[0]['index']==0,'SSE choice shape differs')
            choice=choices[0];delta=choice['delta'];reason=choice['finish_reason']
            if not events:
                require(delta=={'role':'assistant','content':''} and reason is None and 'usage' not in event,
                        'initial assistant role frame required')
            elif reason is None:
                require(type(delta) is dict and set(delta)=={'content'} and type(delta['content']) is str and
                        bool(delta['content']) and 'usage' not in event,'SSE content-only delta required')
                delta['content'].encode('utf-8',errors='strict')
                pieces.append(delta['content'])
                on_delta(delta['content'])
            else:
                require(reason in ('stop','length') and delta=={} and type(event.get('usage')) is dict,
                        'one terminal usage frame required')
                require(set(event['usage'])=={'prompt_tokens','completion_tokens','total_tokens'} and
                        all(type(n) is int and n>=0 for n in event['usage'].values()),'integer SSE usage required')
                finish=reason;usage=event['usage']
            events.append(event)
        require(done and identity is not None and finish is not None,'incomplete SSE terminal sequence')
        return dict(status=reply.status,body=dict(id=identity[0],object='chat.completion',created=identity[2],model=identity[1],
            choices=[dict(index=0,message=dict(role='assistant',content=''.join(pieces)),finish_reason=finish)],usage=usage),
            sse_validated=True,done=True,**evidence())
    except BaseException as error:
        error.client_partial_response=dict(status=reply.status,sse_validated=False,done=False,partial_text=''.join(pieces),**evidence())
        raise

class DeadlineResponse(http.client.HTTPResponse):
    """Absolute deadline and aggregate 64KiB cap for status/header reads.

    HTTPResponse's ordinary readline can otherwise outlive a socket timeout
    when bytes trickle. Header reads consume one byte, leaving the original
    buffered reader and all body bytes available to the unchanged body parser.
    """
    def __init__(self, sock, *args, deadline, **kwargs):
        self.receive_socket, self.deadline = sock, deadline
        super().__init__(sock, *args, **kwargs)

    def begin(self):
        response = self
        original = self.fp
        class Headers:
            remaining_bytes = 65536
            def readline(self, limit=-1):
                line = bytearray()
                while limit < 0 or len(line) < limit:
                    remaining = response.deadline - time.monotonic()
                    require(remaining > 0, 'HTTP header deadline exceeded')
                    require(self.remaining_bytes > 0, 'HTTP aggregate header byte bound exceeded')
                    response.receive_socket.settimeout(remaining)
                    byte = original.read1(1)
                    if not byte:
                        break
                    self.remaining_bytes -= len(byte)
                    line.extend(byte)
                    if byte == b'\n':
                        break
                return bytes(line)
            def close(self):
                original.close()
        headers = Headers()
        self.fp = headers
        try:
            super().begin()
            require(not self.headers.get_all('Transfer-Encoding'),
                    'Transfer-Encoding refused; admitted server is unchunked')
        finally:
            if self.fp is headers:
                self.fp = original


def exchange(endpoint, payload, session, on_delta, *, timeout=900):
    host, port = address(endpoint)
    require(type(timeout) in (int, float) and 0 < timeout <= 900, 'timeout must be in (0,900] seconds')
    wire = json.dumps(payload, ensure_ascii=False, separators=(',',':')).encode('utf-8')
    require(len(wire) <= 65536, 'encoded request exceeds HTTP byte bound; history unchanged')
    deadline = time.monotonic() + timeout
    connection = http.client.HTTPConnection(host, port, timeout=timeout)
    connection.response_class = lambda *args, **kwargs: DeadlineResponse(*args, deadline=deadline, **kwargs)
    response = None
    failure = None
    partial = {}
    raw = bytearray()
    try:
        connection.request('POST', '/v1/chat/completions', body=wire,
            headers={'Content-Type':'application/json', 'X-Ownrt-Session':session})
        receive_socket = connection.sock  # Retain before HTTP/1.0 getresponse detaches it.
        require(receive_socket is not None, 'response socket required')
        remaining = deadline - time.monotonic()
        require(remaining > 0, 'HTTP deadline exceeded')
        receive_socket.settimeout(remaining)
        response = connection.getresponse()
        if response.status == 200 and payload['stream']:
            require(not response.headers.get_all('Content-Length'),
                    'SSE must use admitted close-delimited framing')
            result = read_sse(response, maximum=payload['max_tokens'], receive_socket=receive_socket,
                              model=payload['model'], on_delta=on_delta, deadline=deadline)
            body = result['body']
            partial = result | {'partial_text':body['choices'][0]['message']['content']}
            try:
                validate_completion(body, payload['model'], payload['max_tokens'])
            except BaseException as error:
                error.client_partial_response = result | {'partial_text':body['choices'][0]['message']['content'],
                    'sse_validated':False}
                raise
            return body
        while True:
            remaining = deadline - time.monotonic()
            require(remaining > 0, 'HTTP deadline exceeded')
            receive_socket.settimeout(remaining)
            chunk = response.read1(min(4096, 65537 - len(raw)))
            raw.extend(chunk)
            require(len(raw) <= 65536, 'HTTP response exceeds byte bound')
            if not chunk or response.isclosed():
                break
        body = parse_json(raw)
        if response.status != 200:
            raise HTTPFailure(response.status, body)
        require(response.getheader('Content-Type') == 'application/json; charset=utf-8',
                'ordinary JSON content type differs')
        validate_completion(body, payload['model'], payload['max_tokens'])
        partial = {'partial_text':body['choices'][0]['message']['content']}
        return body
    except BaseException as error:
        failure = error
        if not hasattr(error, 'client_partial_response'):
            error.client_partial_response = {'partial_text':'', 'raw_base64':base64.b64encode(raw).decode('ascii')}
        raise
    finally:
        cleanup_failure = None
        for label, resource in (('response',response), ('connection',connection)):
            if resource is None:
                continue
            try:
                resource.close()
            except BaseException as error:
                if failure is None and cleanup_failure is None:
                    cleanup_failure = error
                else:
                    try:
                        (failure or cleanup_failure).add_note('HTTP '+label+' close also failed: '+str(error)[:1024])
                    except BaseException:
                        pass
        if failure is None and cleanup_failure is not None:
            cleanup_failure.client_partial_response = partial
            raise cleanup_failure


class Conversation:
    """One serial conversation. Only complete successful replies enter history.

    A failed attempted exchange halts this client: an ambiguous request is never
    automatically repeated. Validation refusals before exchange leave it usable.
    Context token admission belongs to the server; no approximate token count.
    """
    def __init__(self, endpoint, *, model, session, maximum=128, stream=True, timeout=900):
        address(endpoint)
        require(type(model) is str and 0 < len(model.encode('utf-8')) <= 256, 'bounded explicit model required')
        require(type(session) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',session) and
                not session.endswith('.lock'), 'invalid session ID')
        require(type(maximum) is int and 1 <= maximum <= 512, 'max_tokens must be 1..512')
        require(type(stream) is bool, 'stream must be bool')
        require(type(timeout) in (int,float) and 0 < timeout <= 900, 'timeout must be in (0,900]')
        self.endpoint, self.model, self.session = endpoint, model, session
        self.maximum, self.stream, self.timeout = maximum, stream, timeout
        self._history = []
        self.turns = 0
        self.failure = None
        self._active = False

    @property
    def history(self):
        return [dict(row) for row in self._history]

    def ask(self, text, *, on_delta=lambda text:None):
        require(self.failure is None, 'conversation halted after failed exchange; no automatic retry')
        require(not self._active, 'conversation request already active')
        require(self.turns < 16, 'client sixteen-turn bound reached')
        require(type(text) is str and bool(text), 'nonempty user text required')
        messages = self.history + [{'role':'user','content':text}]
        require(len(messages) <= 64 and sum(len(m['content'].encode('utf-8')) for m in messages) <= HISTORY_LIMIT,
                'conversation history byte/message bound reached; no truncation')
        payload = {'model':self.model, 'messages':messages, 'max_tokens':self.maximum, 'stream':self.stream}
        # Validate encoded bound before intake, including worst-case JSON escaping.
        require(len(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode('utf-8')) <= 65536,
                'encoded request exceeds HTTP byte bound; history unchanged')
        self._active = True
        try:
            result = exchange(self.endpoint, payload, self.session, on_delta, timeout=self.timeout)
            content = result['choices'][0]['message']['content']
            candidate = messages + [{'role':'assistant','content':content}]
            require(sum(len(m['content'].encode('utf-8')) for m in candidate) <= HISTORY_LIMIT,
                    'completed response exceeds retained history bound; no truncation')
            if not self.stream:
                on_delta(content)
            self._history = candidate
            self.turns += 1
            return result
        except BaseException as error:
            self.failure = error
            if not hasattr(error, 'client_partial_response'):
                error.client_partial_response = {'partial_text':locals().get('content','')}
            raise
        finally:
            self._active = False


def main(argv=None, *, stdin=None, stdout=None, stderr=None):
    stdin, stdout, stderr = stdin or sys.stdin, stdout or sys.stdout, stderr or sys.stderr
    parser = argparse.ArgumentParser(description='Attach-only experimental chat client; never launches an owner.')
    parser.add_argument('--endpoint', required=True, help='http://127.0.0.1:PORT')
    parser.add_argument('--model', required=True)
    parser.add_argument('--session', required=True)
    parser.add_argument('--max-tokens', type=int, default=128)
    parser.add_argument('--ordinary', action='store_true')
    parser.add_argument('--prompt', help='one-shot text; otherwise one user turn per stdin line')
    args = parser.parse_args(argv)
    def display(text):
        stdout.write(text)
        stdout.flush()
    try:
        conversation = Conversation(args.endpoint, model=args.model, session=args.session,
                                    maximum=args.max_tokens, stream=not args.ordinary)
        while conversation.turns < 16:
            if args.prompt is not None:
                text = args.prompt
            else:
                if stdin.isatty():
                    stderr.write('you> '); stderr.flush()
                text = stdin.readline(HISTORY_LIMIT + 2)
                if not text:
                    break
                require(len(text) <= HISTORY_LIMIT + 1 and (text.endswith('\n') or len(text) <= HISTORY_LIMIT),
                        'stdin line exceeds bounded input')
                text = text.removesuffix('\n')
                if not text:
                    continue
            result = conversation.ask(text, on_delta=display)
            stdout.write('\n'); stdout.flush()
            stderr.write('['+result['choices'][0]['finish_reason']+'; '+
                         str(result['usage']['completion_tokens'])+' output tokens]\n')
            if args.prompt is not None:
                break
        return 0
    except BaseException as error:
        if isinstance(error, SystemExit):
            raise
        stderr.write('\nRequest failed: '+type(error).__name__+': '+str(error)[:2048]+
            '\nAny reply without a validated completion is partial/unconfirmed and is not added to history. No retry or owner action.\n')
        return 130 if isinstance(error, KeyboardInterrupt) else 1
