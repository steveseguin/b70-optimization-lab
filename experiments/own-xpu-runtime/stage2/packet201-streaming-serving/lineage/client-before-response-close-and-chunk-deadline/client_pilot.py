#!/usr/bin/env python3
"""Fixed sixteen-turn HTTP exercise; no launch, retry or restoration path."""
from __future__ import annotations
import argparse
import base64
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

sys.dont_write_bytecode = True
P = Path(__file__).resolve().parent
ROOT = P.parents[3]
INTEGRATION = P.parents[1] / 'integration'
sys.path.insert(0, str(INTEGRATION))
from bounded_evidence import BoundedEvidence
from chat_codec import PinnedChatCodec

VECTORS = P / 'client-vectors.json'
PARENT_VECTORS = P.parent / 'packet199-chat-parking/vectors.json'
PARENT_SHA = '278c5ca8150ba3a67b2326a3e6418ee211d6b16455eaec3b666b2bcdf7c8060a'
STAGE = P / 'evidence/planned-a'
OUTPUT = P / 'evidence/client-a'
LIMIT = 1024**2
MODEL = 'qwen38-flash-next-ud-iq3-xxs-experimental'
P200 = P.parent/'packet200-bounded-serving'
P200_VECTORS_SHA = '4d7784788a9227d7825450adfe8585de6b0f495e35845ba8ab96866bc9ee8510'
SSE_NAMES = {'a-park','a-chat-append','a-chat-fresh','names','json','unicode','b-final'}
SSE_LIMIT = 128*1024
RECORD_LIMIT = 256*1024


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(row):
    return (json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n').encode()


def bounded_read(path, limit):
    path = Path(path)
    require(path.is_absolute() and path.resolve(strict=True) == path, 'real evidence path required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1
                and 0 < before.st_size <= limit, 'bounded regular evidence file required')
        data = b''
        while len(data) <= limit:
            chunk = os.read(fd, min(65536, limit + 1 - len(data)))
            if not chunk:
                break
            data += chunk
        signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(len(data) == before.st_size and signature(before) == signature(os.fstat(fd)) ==
                signature(path.stat()), 'evidence changed during read')
        return data
    finally:
        os.close(fd)


def plan():
    require(digest(PARENT_VECTORS.read_bytes()) == PARENT_SHA, 'parent message/oracle source changed')
    require(digest((P200/'client-vectors.json').read_bytes()) == P200_VECTORS_SHA, 'p200 vectors changed')
    parent_rows = json.loads((P200/'client-vectors.json').read_text())['rows']
    row = json.loads(VECTORS.read_text())
    require(row['p200_vectors_sha256'] == P200_VECTORS_SHA, 'p200 vector identity differs')
    for name, value in row['source_sha256'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and
                (ROOT/name).resolve().is_relative_to(P200/'evidence/client-a') and
                digest((ROOT/name).read_bytes()) == value, 'p200 baseline evidence changed')
    require(row['schema'] == 'packet201.client-vectors.v1' and row['parent_vectors_sha256'] == PARENT_SHA and
            row['model'] == MODEL and len(row['rows']) == 16 and
            sum(r['body']['max_tokens'] for r in row['rows']) == row['maximum_output_tokens'] == 1728,
            'fixed sixteen-turn vector contract changed')
    codec = PinnedChatCodec()
    names = set()
    expected_files = {str((P200/f'evidence/client-a/{index:02d}-{kind}.json').relative_to(ROOT))
                      for index in range(1,17) for kind in ('http','native')}
    require(set(row['source_sha256']) == expected_files, 'complete p200 baseline closure required')
    for index, request in enumerate(row['rows'],1):
        require(request['name'] not in names and re.fullmatch(r'[a-z0-9-]{1,40}', request['name']), 'unique fixed request names required')
        names.add(request['name'])
        body = request['body']
        prior = parent_rows[index-1]
        require(request['name'] == prior['name'] and request['session'] == prior['session'].replace('p200','p201') and
                dict(body,stream=False) == prior['body'] and request['prompt_tokens'] == prior['prompt_tokens'] and
                all(request.get(k) == prior.get(k) for k in ('expected_tokens','compare_tokens_to','expected_reuse')),
                'only preregistered stream/session delta allowed')
        require(body['model'] == MODEL and body['temperature'] == 0 and body['top_p'] == 1 and
                body['n'] == 1 and body['stream'] is (request['name'] in SSE_NAMES) and 0 < body['max_tokens'] <= 512,
                'fixed deterministic HTTP parameters required')
        require(codec.encode(codec.render(body['messages'])) == request['prompt_tokens'] and
                len(request['prompt_tokens']) + body['max_tokens'] <= 4096, 'rendered prompt/context changed')
        if 'expected_tokens' in request:
            require(len(request['expected_tokens']) == body['max_tokens'], 'full recorded oracle required')
        baseline = request['p200_baseline']
        native = json.loads((P200/f'evidence/client-a/{index:02d}-native.json').read_text())
        response = json.loads((P200/f'evidence/client-a/{index:02d}-http.json').read_text())['response']['body']
        require(baseline == dict(tokens=native['tokens'],input_tokens=native['native_input_tokens'],
            text=response['choices'][0]['message']['content'],usage=response['usage'],
            finish_reason=response['choices'][0]['finish_reason']), 'full p200 baseline binding differs')
        require(baseline['input_tokens'] == request['prompt_tokens'] and
                0 < len(baseline['tokens']) <= body['max_tokens'], 'p200 input/output baseline differs')
        terminal = baseline['tokens'][-1] in codec.terminal_token_ids
        require(codec.decode(baseline['tokens'][:-1] if terminal else baseline['tokens']) == baseline['text'] and
                baseline['finish_reason'] == ('stop' if terminal else 'length'), 'p200 baseline display differs')
    require(sum(r['body']['stream'] for r in row['rows']) == row['sse_requests'] == 7 and
            row['ordinary_requests'] == 9 and sum(len(r['p200_baseline']['tokens']) for r in row['rows']) ==
            row['baseline_output_tokens'] == 1484, 'fixed mixed-stream baseline changed')
    return row, codec


def read_sse(reply, *, maximum, receive_socket):
    """Consume bounded actual frames incrementally; clocks describe receipt only.

    No frame timing is called token-generation latency. Raw bytes (base64) and
    monotonic receive offsets survive parser failure on the original exception.
    EOF is required after the one final marker, with no trailing bytes.
    """
    raw=bytearray();times=[];events=[];started=time.monotonic_ns();deadline=time.monotonic()+900
    identity=None;pieces=[];finish=None;usage=None;done=False
    def deadline_guard():
        remaining=deadline-time.monotonic()
        require(remaining>0,'SSE receive deadline exceeded')
        require(receive_socket is not None,'retained response socket required')
        receive_socket.settimeout(min(900,remaining))
    def read_line():
        deadline_guard()
        line=reply.readline(8193)
        raw.extend(line[:max(0,SSE_LIMIT-len(raw))])
        require(len(line)<=8192 and len(raw)<SSE_LIMIT,'SSE line/response evidence bound exceeded')
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
                done=True;deadline_guard()
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
            require(event['object']=='chat.completion.chunk' and event['model']==MODEL and
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
        error.client_partial_response=dict(status=reply.status,sse_validated=False,done=False,**evidence())
        raise


def exchange(address, method, path, *, payload=None, session=None):
    require(type(address) in (tuple, list) and len(address) == 2 and address[0] == '127.0.0.1'
            and type(address[1]) is int and 1 <= address[1] <= 65535, 'literal loopback endpoint required')
    body = None if payload is None else encoded(payload)
    headers = {} if body is None else {'Content-Type': 'application/json', 'X-Ownrt-Session': session}
    connection = http.client.HTTPConnection(address[0], address[1], timeout=900)
    failure = None
    try:
        connection.request(method, path, body=body, headers=headers)
        receive_socket = connection.sock  # HTTP/1.0 may detach it in getresponse().
        reply = connection.getresponse()
        if payload is not None and payload.get('stream') is True and reply.status == 200:
            return read_sse(reply, maximum=payload['max_tokens'], receive_socket=receive_socket)
        raw = reply.read(65537)
        require(len(raw) <= 65536, 'HTTP response exceeds fixed evidence bound')
        return dict(status=reply.status, body=json.loads(raw), raw_sha256=digest(raw))
    except BaseException as error:
        failure = error
        raise
    finally:
        try:
            connection.close()
        except BaseException as close_error:
            if failure is None:
                raise
            failure.add_note('HTTP connection close failed: ' + str(close_error)[:1024])


def validate_turn(request, response, native, codec, earlier, *, input_tokens):
    require(response['status'] == 200, 'unexpected HTTP completion status')
    body = response['body']; tokens = native.get('tokens')
    require(native.get('passed') is True and native.get('request_front_scope') == 'experimental-postreply-owner-v2'
            and native.get('context') == 4096 and native.get('requested_max_new') == request['body']['max_tokens']
            and native.get('prompt_tokens') == len(request['prompt_tokens']), 'native request identity differs')
    require(input_tokens == request['prompt_tokens'], 'native consumed prompt token identity differs')
    require(type(tokens) is list and 0 < len(tokens) <= request['body']['max_tokens'] and
            all(type(t) is int and 0 <= t < 248320 for t in tokens), 'invalid native output tokens')
    terminal = tokens[-1] in codec.terminal_token_ids
    require(not any(t in codec.terminal_token_ids for t in tokens[:-1]) and
            (terminal or len(tokens) == request['body']['max_tokens']), 'native completion stop mismatch')
    expected_choice = dict(index=0, message=dict(role='assistant', content=codec.decode(tokens[:-1] if terminal else tokens)),
                           finish_reason='stop' if terminal else 'length')
    require(body.get('model') == MODEL and body.get('object') == 'chat.completion' and body.get('choices') == [expected_choice],
            'HTTP content/finish mapping differs from native tokens')
    require(body.get('usage') == dict(prompt_tokens=len(request['prompt_tokens']), completion_tokens=len(tokens),
            total_tokens=len(request['prompt_tokens']) + len(tokens)), 'HTTP usage differs from native tokens')
    if 'expected_tokens' in request:
        require(tokens == request['expected_tokens'], 'recorded output oracle mismatch')
    if 'compare_tokens_to' in request:
        require(tokens == earlier[request['compare_tokens_to']]['tokens'], 'resumed/fresh token mismatch')
    if 'expected_reuse' in request:
        require(native.get('session_reuse') is request['expected_reuse'], 'native restore/prefill selection differs')
    baseline = request['p200_baseline']
    require(tokens == baseline['tokens'] and input_tokens == baseline['input_tokens'] and
            body['choices'][0]['message']['content'] == baseline['text'] and body['usage'] == baseline['usage'] and
            body['choices'][0]['finish_reason'] == baseline['finish_reason'], 'p200 full native baseline mismatch')
    if request['body']['stream']:
        require(response.get('sse_validated') is True and response.get('done') is True, 'strict consumed SSE proof missing')
    return dict(name=request['name'], baseline_checked=True, streaming=request['body']['stream'], tokens=tokens, session_reuse=native.get('session_reuse'),
                finish_reason=expected_choice['finish_reason'], oracle_checked='expected_tokens' in request,
                pair_checked=request.get('compare_tokens_to'))


def exercise(address, vectors, codec, *, native_reader, guard, persist, transport=exchange):
    """One attempt per request. An unexpected result escapes before another call."""
    guard(); health = transport(address, 'GET', '/health')
    persist('health.json', health)
    require(health['status'] == 200 and health['body'].get('status') == 'ready', 'endpoint not ready')
    guard(); models = transport(address, 'GET', '/v1/models'); persist('models.json', models)
    require(models['status'] == 200 and [r.get('id') for r in models['body'].get('data', [])] == [MODEL], 'model route differs')
    invalid = dict(vectors['rows'][0]['body'], temperature=0.7)
    guard(); refused = transport(address, 'POST', '/v1/chat/completions', payload=invalid, session='p201-invalid')
    persist('expected-refusal.json', refused)
    require(refused['status'] == 400, 'invalid sampling request was not refused before RUN')
    earlier = {}; ids = set()
    for index, request in enumerate(vectors['rows'], 1):
        guard()
        try:
            response = transport(address, 'POST', '/v1/chat/completions', payload=request['body'], session=request['session'])
        except BaseException as error:
            try:
                persist(f'{index:02d}-http.json',dict(name=request['name'],partial_response=getattr(error,'client_partial_response',None),
                    error_type=type(error).__name__,error=str(error)[:2048]))
            except BaseException:
                pass  # Evidence failure never replaces the original transport/parser error.
            raise
        # Keep even a failed HTTP response before interpreting it.
        persist(f'{index:02d}-http.json', dict(name=request['name'], response=response))
        require(response['status'] == 200, 'unexpected HTTP status for ' + request['name'])
        request_id = response['body'].get('id', '').removeprefix('chatcmpl-')
        require(re.fullmatch(r'h[0-9a-f]{32}-[0-9a-f]{16}', request_id) and request_id not in ids,
                'native request identity invalid/repeated')
        ids.add(request_id)
        native, source_digest, input_tokens, input_digest = native_reader(request_id)
        result = validate_turn(request, response, native, codec, earlier, input_tokens=input_tokens)
        result.update(native_request_id=request_id, native_result_sha256=source_digest,
                      native_input_tokens=input_tokens, native_input_sha256=input_digest)
        persist(f'{index:02d}-native.json', result)
        earlier[request['name']] = result
        guard()
    return dict(passed=True, requests=len(earlier), controls_claimed=False,
        output_tokens=sum(len(r['tokens']) for r in earlier.values()), maximum_output_tokens=1728,
        exact_recorded_requests=sum(r['oracle_checked'] for r in earlier.values()),
        resumed_fresh_pairs=sum(r['pair_checked'] is not None for r in earlier.values()),
        p200_exact_requests=sum(r['baseline_checked'] for r in earlier.values()),
        sse_requests=sum(r['streaming'] for r in earlier.values()), ordinary_requests=sum(not r['streaming'] for r in earlier.values()),
        sse_terminal_sequences=sum(r['streaming'] for r in earlier.values()), observed_delivery_timing_only=True,
        native_device_execution_claim='Join with independent worker/native/physical-drain receipts',
        submission_eligible=False, speed_claim=False)


def execute():
    spec = importlib.util.spec_from_file_location('_p201_client_admission', P / 'run.py')
    admission = importlib.util.module_from_spec(spec); spec.loader.exec_module(admission)
    manifest, manifest_sha = admission.verify_manifest()
    owner = STAGE / 'output/owner'
    stop = STAGE / 'output/STOP'
    writer = None; close_attempted = False
    def guard():
        require(digest(admission.MANIFEST.read_bytes()) == manifest_sha, 'execution admission changed')
        require(not any(os.path.lexists(p) for p in (stop, P.parents[1]/'ops/lane-queue/STOP-A',
                    P.parents[1]/'ops/lane-queue/STOP-B')), 'incident latch; no new HTTP request')
    def persist(name, row):
        require(writer is not None, 'client evidence writer unavailable')
        writer.create(name, limit_bytes=RECORD_LIMIT); writer.append(name, encoded(row))
    def native_reader(request_id):
        raw = bounded_read(owner / 'requests' / request_id / 'result.json', 256 * 1024)
        inputs = bounded_read(owner / 'requests' / request_id / 'input.tokens', 32 * 1024)
        require(re.fullmatch(rb'(?:(?:0|[1-9][0-9]{0,5})\n){1,4096}', inputs), 'native input token grammar differs')
        return json.loads(raw), digest(raw), [int(t) for t in inputs.splitlines()], digest(inputs)
    try:
        vectors, codec = plan()
        require(manifest.get('controller', {}).get('additional_write_bytes') == LIMIT, 'client evidence forecast not admitted')
        require(not os.path.lexists(OUTPUT), 'fresh client evidence required; no rerun')
        events = bounded_read(STAGE / 'output/control/events.jsonl', LIMIT)
        listeners = [r for line in events.splitlines() if (r := json.loads(line)).get('event') == 'listener']
        require(len(listeners) == 1, 'exact fresh listener event required before client starts')
        address = listeners[0]['address']
        guard(); OUTPUT.mkdir(mode=0o700)
        writer = BoundedEvidence(OUTPUT, total_limit_bytes=LIMIT, max_files=40)
        persist('admission.json', dict(manifest_sha256=manifest_sha, vectors_sha256=digest(VECTORS.read_bytes()),
                listener_events_sha256=digest(events), address=address, started_utc_ns=time.time_ns()))
        result = exercise(address, vectors, codec, native_reader=native_reader, guard=guard, persist=persist)
        persist('client-result.json', result)
        close_attempted = True; writer.close()
        return result
    except BaseException as error:
        secondary = []
        try:
            with stop.open('xb') as file:
                file.write(b'packet201 client incident; no request retry\n'); file.flush(); os.fsync(file.fileno())
        except FileExistsError:
            pass
        except BaseException as failed_stop:
            secondary.append(dict(operation='stop', type=type(failed_stop).__name__, message=str(failed_stop)[:1024]))
        try:
            if writer is not None:
                persist('client-incident.json', dict(passed=False, error_type=type(error).__name__, error=str(error)[:4096],
                        secondary_errors=secondary, retry=False))
        except BaseException as failed_evidence:
            secondary.append(dict(operation='evidence', type=type(failed_evidence).__name__, message=str(failed_evidence)[:1024]))
        if writer is not None and not close_attempted:
            close_attempted = True
            try:
                writer.close()
            except BaseException as failed_close:
                secondary.append(dict(operation='close', type=type(failed_close).__name__, message=str(failed_close)[:1024]))
        for failure in secondary:
            error.add_note('client secondary failure: ' + json.dumps(failure))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--plan', action='store_true'); mode.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.plan:
        vectors, _ = plan()
        print(json.dumps(dict(passed=True, device_executed=False, requests=len(vectors['rows']),
              maximum_output_tokens=vectors['maximum_output_tokens'], vectors_sha256=digest(VECTORS.read_bytes()))))
    else:
        print(json.dumps(execute()))


if __name__ == '__main__':
    main()
