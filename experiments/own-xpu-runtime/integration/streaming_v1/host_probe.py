#!/usr/bin/env python3
"""Explicit tiny HOST_ONLY streaming seam; --plan never starts an owner.

FixtureFacade deliberately is NOT StreamingChatService. Synthetic native
vocab16/identity cannot pass production codec admission. Actual decoder bytes
and HTTP delivery are exercised without changing those production gates.
"""
from __future__ import annotations
if __name__=='__main__' and not __package__:
    raise SystemExit('Use the fixed venv with PYTHONPATH=integration and -m streaming_v1.host_probe; direct script invocation is refused')
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import checkpoint_engine_host_probe as B
import session_lifecycle_host_probe as H
from chat_codec import PinnedChatCodec
from chat_service import ChatRequestError
from native_checkpoint_store import NativeCheckpointStore
from request_front.client_v2 import NativeFront
from streaming_v1 import decoder as D, engine as E, http as HTTP

OUTPUT=B.PACKET/'build/engine-integration-streaming-a'
MODEL='synthetic-host-streaming-seam'
ROWS=[dict(session='alpha',content='BCD',tokens=[1,2,3],generated=[0]*4,disposition='SAVE'),
      dict(session='beta',content='EF',tokens=[4,5],generated=[1]*4,disposition='RELEASE')]
RETAINED=[]

def payload(row):
    return dict(model=MODEL,messages=[dict(role='user',content=row['content'])],max_tokens=4,stream=True)

def origins():
    expected={B:'checkpoint_engine_host_probe.py',H:'session_lifecycle_host_probe.py',
              D:'streaming_v1/decoder.py',E:'streaming_v1/engine.py',HTTP:'streaming_v1/http.py'}
    for module,name in expected.items():
        B.require(Path(module.__file__).resolve()==HERE.parent/name,'canonical helper/module origin required')
    for symbol,name in ((NativeFront,'request_front/client_v2.py'),(NativeCheckpointStore,'native_checkpoint_store.py'),
                        (PinnedChatCodec,'chat_codec.py')):
        module=sys.modules.get(symbol.__module__)
        B.require(module is not None and Path(module.__file__).resolve()==HERE.parent/name and
                  getattr(module,symbol.__name__,None) is symbol,'canonical imported symbol required')


def plan():
    B.require(Path(sys.executable)==Path('/home/steve/.venvs/vllm-xpu/bin/python'),'fixed vllm-xpu interpreter required')
    origins()
    B.require(not os.path.lexists(OUTPUT),'fresh fixed streaming scratch required; no replay')
    base=B.plan(OUTPUT)
    B.require(base['expected_identity']['geometry']['eos']==15,'tiny native EOS identity changed')
    sources=dict(base['sources_sha256'])
    for path in [HERE/n for n in ('__init__.py','host_probe.py','test_host_probe.py','HOST-ONLY-PLAN.md','HOST-PROBE-PREP.md','engine.py','decoder.py','http.py','delivery.py')]+[HERE.parent/n for n in ('session_lifecycle_host_probe.py','session_lifecycle.py','chat_service.py','chat_codec.py','chat_http.py')]:
        sources[str(path.relative_to(B.ROOT))]=B.sha(path)
    return dict(schema='ownrt.streaming-tiny-host-plan.v1',passed=True,device_executed=False,native_executed=False,
        production_service_exercised=False,base=base,argv=base['argv'],binary_sha256=base['binary_sha256'],
        output=str(OUTPUT),native_request_limit=8,requests=ROWS,native_seconds=180,native_idle_seconds=30,
        fixture_seconds=150,request_timeout_seconds=30,client_timeout_seconds=35,
        address_space_limit_bytes=4*1024**3,planned_write_bytes=8*B.SAVE_BOUND,disk_floor_bytes=B.FLOOR,
        save_bound_bytes=B.SAVE_BOUND,expected_controls=['SAVE','RELEASE'],expected_stop_reason='quit',
        source_sha256=sources,scope='Synthetic tiny owner and fixture facade; actual decoder/engine/store/HTTP. No production chat service, model or device qualification.')


class FixtureFacade:
    model=MODEL
    def __init__(self,engine,policies,codec,guard,*,deadline):
        B.require(type(engine) is E.StreamingCheckpointEngine,'actual streaming engine required')
        D.verify_codec(codec)
        B.require(engine.vocab==16 and engine.context==64,'tiny fixture geometry required')
        self.engine,self.policies,self.codec,self.guard=engine,policies,codec,guard
        self.deadline=deadline;self.turns=[];self.timeline=[];self.failure=None;self.halted_reason=None

    def validate(self,value):
        if self.failure is not None:raise self.failure
        if len(self.turns)>=2 or value!=payload(ROWS[len(self.turns)]):
            raise ChatRequestError('only fixed two-row synthetic fixture admitted')
        return None

    def complete(self,*args,**kwargs):
        raise ChatRequestError('fixture requires SSE; production service is not used')

    def stream(self,value,*,session,request_id,on_delta):
        self.validate(value);index=len(self.turns);row=ROWS[index]
        if session!=row['session']:raise ChatRequestError('fixed synthetic session required')
        try:
            self.guard();B.require(time.monotonic()<self.deadline,'fixture lifetime exhausted')
            decoder=D.TokenDecoder(self.codec,maximum_tokens=4)
            def observe(token):
                front=self.engine.front
                B.require(front.state=='running' and front.pending is None and front.completed==index
                          and front.completed_controls==index,'token callback must precede terminal consumption/disposition')
                B.require(type(token) is int and 0<=token<15,'tiny EOS is not a production codec stop token')
                self.timeline.append(dict(event='token-callback',request_id=request_id,token=token,
                    monotonic=time.monotonic(),front_state=front.state,completed=front.completed,controls=front.completed_controls))
                text=decoder.feed(token)
                if text:on_delta(text)  # Trusted production transport's bounded nonblocking offer.
            outcome=self.engine.run_turn(self.policies[index],session,[dict(tokens=row['tokens'])],
                                         request_id=request_id,max_new=4,on_token=observe)
            if self.engine.last_observer_error is not None:raise self.engine.last_observer_error
            generated=outcome['response']['tokens'];B.require(generated==row['generated'],'fixed miniature output differs')
            tail=decoder.finish(generated)
            if tail:on_delta(tail)
            B.require(outcome['observation']['observer_failed'] is False and
                      self.engine.front.completed_controls==index+1 and self.engine.front.pending is None,
                      'required native disposition did not finish')
            parked=outcome['parked'];released=outcome['release']
            B.require((parked is not None and released is None) if index==0 else (parked is None and released is not None),
                      'SAVE then RELEASE fixture ordering differs')
            tick=time.monotonic();self.timeline.append(dict(event='disposition-observed',request_id=request_id,
                disposition=row['disposition'],monotonic=tick,controls=self.engine.front.completed_controls))
            self.guard()
            completion=dict(id='chatcmpl-'+request_id,object='chat.completion',created=0,model=MODEL,
                choices=[dict(index=0,message=dict(role='assistant',content=decoder.text),finish_reason='length')],
                usage=dict(prompt_tokens=len(row['tokens']),completion_tokens=4,total_tokens=len(row['tokens'])+4))
            self.turns.append(dict(request_id=request_id,session=session,tokens=generated,
                disposition=row['disposition'],disposition_monotonic=tick,
                checkpoint_id=parked.checkpoint_id if parked else None,completion=completion))
            return dict(completion=completion,stream_passed=True,observation=outcome['observation'])
        except BaseException as error:
            self.failure=error;self.halted_reason=type(error).__name__;raise


def request_sse(address,row,*,connect=socket.create_connection):
    B.require(type(address) is tuple and len(address)==2 and address[0]=='127.0.0.1' and
              type(address[1]) is int and 1<=address[1]<=65535,'literal ephemeral loopback required')
    body=json.dumps(payload(row),separators=(',',':')).encode()
    wire=(f'POST /v1/chat/completions HTTP/1.0\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\n'
          f'X-Ownrt-Session: {row["session"]}\r\nContent-Length: {len(body)}\r\n\r\n').encode()+body
    connection=connect(address,timeout=5);primary=None;raw=bytearray();frames=[];header=None;pending=b''
    deadline=time.monotonic()+35
    try:
        connection.sendall(wire)
        while True:
            remaining=deadline-time.monotonic();B.require(remaining>0,'fixture client absolute timeout')
            connection.settimeout(min(5,remaining));chunk=connection.recv(4096)
            if not chunk:break
            raw.extend(chunk);B.require(len(raw)<=65536,'tiny SSE evidence bound')
            pending+=chunk
            if header is None:
                if b'\r\n\r\n' not in pending:continue
                header,pending=pending.split(b'\r\n\r\n',1)
                B.require(header.startswith(b'HTTP/1.0 200 ') and b'content-type: text/event-stream' in header.lower(),
                          'successful SSE header required')
            while b'\n\n' in pending:
                frame,pending=pending.split(b'\n\n',1)
                B.require(frame.startswith(b'data: ') and len(frames)<32,'bounded single-data SSE frame required')
                data=frame[6:];value='[DONE]' if data==b'[DONE]' else json.loads(data)
                frames.append(dict(value=value,received_monotonic=time.monotonic()))
        B.require(header is not None and not pending and frames and frames[-1]['value']=='[DONE]',
                  'complete SSE terminal required')
        B.require(sum(x['value']=='[DONE]' for x in frames)==1,'one DONE required')
        return dict(raw_http_utf8=bytes(raw).decode('utf-8'),raw_sha256=hashlib.sha256(raw).hexdigest(),frames=frames)
    except BaseException as error:
        primary=error
        try:
            kept=bytes(raw[:65536])
            error.stream_partial=dict(raw_http_hex=kept.hex(),raw_sha256=hashlib.sha256(kept).hexdigest(),
                                      truncated=len(raw)>65536,observed_bytes=len(raw),frames=frames)
        except BaseException as capture_error:
            error.add_note('partial SSE capture failed: '+type(capture_error).__name__)
        raise
    finally:
        try:connection.close()
        except BaseException as secondary:
            if primary is None:raise
            primary.add_note('secondary client close: '+str(secondary))


def check_sse(reply,turn):
    frames=reply['frames'];chunks=[r['value'] for r in frames[:-1]];expected=turn['completion']
    B.require(chunks and all(c['id']==expected['id'] and c['model']==MODEL for c in chunks),'SSE identity mismatch')
    B.require(chunks[0]['choices'][0]['delta']==dict(role='assistant',content=''),'initial role chunk required')
    content=[(n,c['choices'][0]['delta'].get('content','')) for n,c in enumerate(chunks)]
    B.require(''.join(text for _,text in content)==expected['choices'][0]['message']['content'],'SSE decoder parity failed')
    B.require(chunks[-1]['choices'][0]['finish_reason']=='length' and chunks[-1]['usage']==expected['usage'] and
              all(c['choices'][0]['finish_reason'] is None for c in chunks[:-1]),'finish/usage only after content')
    first=next(n for n,text in content if text)
    B.require(first<len(chunks)-1,'nonempty text must precede finish/DONE')
    return dict(first_text_received_monotonic=frames[first]['received_monotonic'],
        first_text_received_before_disposition=frames[first]['received_monotonic']<turn['disposition_monotonic'],
        scope='Receive-time observation only; no latency or forced scheduling guarantee')


def cleanup(owned,result,error):
    owned['stop'].set();child=owned.get('owner');thread=owned.get('thread');unknown=False
    def secondary(failure):
        nonlocal error
        if error is None:error=failure
        else:
            try:message=str(failure)
            except BaseException:message=type(failure).__name__
            error.add_note('secondary fixture cleanup: '+message)
    def status():
        nonlocal unknown
        try:return child.poll() if child is not None else 0
        except BaseException as failure:unknown=True;secondary(failure);return None
    state=status()
    if error is not None and child is not None and state is None and not unknown:
        if result.get('incident_sigterm_count',0)==0:
            result['incident_sigterm_count']=1
            try:child.send_signal(signal.SIGTERM)
            except ProcessLookupError:pass
            except BaseException as failure:secondary(failure)
        try:child.wait(timeout=65)
        except subprocess.TimeoutExpired:pass
        except BaseException as failure:secondary(failure)
    if thread is not None:
        try:
            if thread.ident is not None:thread.join(2)
        except BaseException as failure:unknown=True;secondary(failure)
    try:thread_live=thread is not None and thread.is_alive()
    except BaseException as failure:unknown=True;secondary(failure);thread_live=True
    state=status()
    retained=bool(unknown or owned.get('launch_uncertain') or owned.get('thread_start_uncertain') or
                  (child is not None and state is None) or thread_live)
    result['retained']=retained
    if retained:
        RETAINED.append(owned)
    else:
        close=[owned.get('server'),owned.get('store')]
        front=owned.get('front')
        if front is not None:close.append(front.selector)
        if child is not None:close.extend([child.stdin,child.stdout])
        close.append(owned.get('stderr'))
        for item in close:
            if item is not None:
                try:item.server_close() if item is owned.get('server') else item.close()
                except BaseException as failure:secondary(failure)
    return error


def execute(spec):
    B.require(os.getpriority(os.PRIO_PROCESS,0)==19 and set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32)),
              'nice19 helper placement required')
    B.require(plan()==spec,'fixed source/fixture plan changed')
    B.require(shutil.disk_usage(B.ROOT).free>=B.FLOOR+spec['planned_write_bytes'],'root floor after forecast')
    policy,parent=B.modules();environment=parent.parent_environment()
    B.require(environment.get('OMP_NUM_THREADS')=='2','two-thread tiny environment required')
    tool_env={k:environment[k] for k in ('PATH','OMP_NUM_THREADS','LD_LIBRARY_PATH')}
    resource.setrlimit(resource.RLIMIT_AS,(spec['address_space_limit_bytes'],spec['address_space_limit_bytes']))
    codec=PinnedChatCodec();D.verify_codec(codec)  # Predictable header/dependency refusal precedes owner creation.
    OUTPUT.mkdir(mode=0o700)
    owned=dict(stop=threading.Event(),launch_uncertain=False);result=dict(passed=False,device_executed=False,
        native_host_executed=False,production_service_exercised=False,incident_sigterm_count=0,requests=[],guards=[])
    error=None;outcome={}
    def guard():
        B.require(shutil.disk_usage(B.ROOT).free>=B.FLOOR,'root floor during tiny fixture')
        result['guards'].append(time.monotonic())
    try:
        (OUTPUT/'checkpoints').mkdir(mode=0o700)
        (OUTPUT/'synthetic-identity.tsv').write_bytes(B.SYNTHETIC_IDENTITY)
        (OUTPUT/'tokenizer.tsv').write_bytes(Path(spec['base']['tokenizer_source']).read_bytes());B.save(OUTPUT/'plan.json',spec)
        log=owned['stderr']=(OUTPUT/'stderr.log').open('wb')
        def spawn(*args,**kwargs):
            owned['launch_uncertain']=True
            child=subprocess.Popen(*args,**kwargs);owned['owner']=child;owned['launch_uncertain']=False;return child
        launched=time.monotonic();child=H.start_owner(spec,environment,log,popen=spawn)
        result['native_host_executed']=True
        front=owned['front']=NativeFront(child,context=64,vocab=16,max_requests=8,startup_timeout=30,request_timeout=30)
        store=owned['store']=NativeCheckpointStore(OUTPUT/'checkpoints',Path(spec['argv'][0]),spec['binary_sha256'],tool_env)
        engine=E.StreamingCheckpointEngine(front,H.GuardedStore(store,guard),root=store.root,
            expected_identity=spec['base']['expected_identity'],admitted_contract='v1.2+p198',
            save_size_bound_bytes=B.SAVE_BOUND,storage_available=lambda path:shutil.disk_usage(path).free,floor_bytes=B.FLOOR)
        policies=[policy.Parking(engine,lambda messages:messages,lambda messages:list(messages[0]['tokens']),
            budget_bytes=budget,accepted_contracts={('experimental-postreply-front','v1.2+p198')}) for budget in (B.SAVE_BOUND,0)]
        facade=FixtureFacade(engine,policies,codec,guard,deadline=launched+150)
        server=owned['server']=HTTP.make_server(facade);server.timeout=.1
        def serve():
            try:
                while len(facade.turns)<2 and not owned['stop'].is_set():
                    guard();B.require(time.monotonic()<launched+150,'fixture HTTP lifetime exhausted');server.handle_request()
                    if facade.failure is not None:raise facade.failure
                    B.require(not server.intake_halted,'streaming HTTP intake halted')
                    if server.last_stream_receipt is not None:
                        r=server.last_stream_receipt
                        B.require(r['native_complete'] and r['stream_passed'] and r['terminal_offered'] and
                                  r['delivery']['failed'] is None,'SSE delivery did not complete')
            except BaseException as failure:outcome['error']=failure
        thread=owned['thread']=threading.Thread(target=serve,name='tiny-host-streaming',daemon=False)
        owned['thread_start_uncertain']=True;thread.start();owned['thread_start_uncertain']=False
        for row in ROWS:
            try:reply=request_sse(server.server_address,row)
            except BaseException as client_error:
                result['partial_http']=getattr(client_error,'stream_partial',None)
                if facade.failure is not None:
                    result['caller_error']=dict(type=type(client_error).__name__,message=str(client_error))
                    raise facade.failure
                raise
            result['requests'].append(reply)
        thread.join(35);B.require(not thread.is_alive(),'streaming handler retained')
        if 'error' in outcome:raise outcome['error']
        B.require(len(facade.turns)==2 and front.completed==front.completed_controls==2 and front.pending is None,
                  'two turns and dispositions required before QUIT')
        for reply,turn in zip(result['requests'],facade.turns):reply['timing']=check_sse(reply,turn)
        stopped=front.close(timeout=30)
        B.require(stopped==dict(event='stopped',reason='quit',safe_to_exit=True,completed_requests=2,
            completed_controls=2,discarded_pending=False,pending_request_id='') and child.returncode==0,'clean two-of-eight QUIT required')
        native=B.read(OUTPUT/'owner/receipt.json');B.require(native['passed'] and native['safe_to_exit'] and native['device_executed'] is False,'HOST_ONLY teardown required')
        for row,turn in zip(ROWS,facade.turns):
            directory=OUTPUT/'owner/requests'/turn['request_id'];actual=B.read(directory/'result.json')
            B.require(actual['tokens']==row['generated'] and [int(t) for t in (directory/'input.tokens').read_text().splitlines()]==row['tokens'],'actual native input/output mismatch')
        checkpoint=facade.turns[0]['checkpoint_id'];snapshot=store.snapshot(checkpoint);B.require(snapshot is not None,'retained tiny SAVE required')
        result.update(passed=True,model_loads=front.ready['model_loads'],owner_returncode=child.returncode,
            stopped=stopped,controls=['SAVE','RELEASE'],turns=facade.turns,timeline=facade.timeline,
            checkpoint=dict(id=checkpoint,storage_bytes=snapshot.storage_bytes,state_sha256=B.state_hashes(OUTPUT/'checkpoints'/checkpoint)),
            native_receipt_sha256=B.sha(OUTPUT/'owner/receipt.json'),http_receipt=server.last_stream_receipt)
        B.require(result['model_loads']==1,'one tiny owner load required')
    except BaseException as failure:error=outcome.get('error',failure)
    error=cleanup(owned,result,error)
    if error is not None:
        result.update(passed=False,error_type=type(error).__name__,error=str(error))
    result['finished_utc_ns']=time.time_ns()
    try:B.save(OUTPUT/'result.json',result)
    except BaseException as failure:
        if error is None:error=failure
        else:error.add_note('fixture result write failed: '+str(failure))
    if error is not None:raise error
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--plan',action='store_true');mode.add_argument('--run-host-only',action='store_true');args=parser.parse_args()
    spec=plan()
    if args.plan:print(json.dumps(spec,indent=2));return
    try:print(json.dumps(execute(spec)))
    except BaseException:
        if RETAINED:
            # Busy/uncertain resources are deliberately held for caller inspection.
            # No retry, forced kill, background close or another native command.
            while True:time.sleep(30)
        raise

if __name__=='__main__':main()
