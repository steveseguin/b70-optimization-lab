#!/usr/bin/env python3
"""Bounded two-process controller; CPU host backend by default. No threads."""
import argparse, hashlib, json, math, mmap, os, select, signal, socket, struct, subprocess, sys, time
from pathlib import Path
P=Path(__file__).resolve().parent
SLOT=65536;SHARED=2*SLOT+4096
REQUEST=struct.Struct("<8i");REPLY=struct.Struct("<8i4d")
HALF,ACCEPT,ROLLBACK,DUMP,FINISH,CANARY,FAIL,STALL=range(1,9)
def save(path,value):
    path.write_text(json.dumps(value,indent=2)+"\n")
def failure_attempt(label,action,errors):
    """Receipt/hook failures must never prevent cooperative stop and drain."""
    try:action()
    except Exception as error:
        message=f"{label}: {error}"
        errors.append(message)
        try:print(message,file=sys.stderr,flush=True)
        except Exception:pass

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def require(test,message):
    if not test:raise ValueError(message)
DRAFT=9
PUBLICATION=struct.Struct("<iiiiQiid")
class Draft:
    """guess(history, position) -> token | None, using confirmed history only.

    MTP provider: rank1 consumes previous final streams + embedding(x_p)
    before its HALF(p), publishing {valid,position,token,error,elapsed_ns} at
    shared offset 131072. It cannot mutate target state or target arithmetic.
    The controller never treats the provider result as an emitted token.
    """
    def __init__(self,mode="none",script=()):
        require(mode in ("none","ngram","script","mtp"),"unknown provider")
        self.mode=mode;self.script=list(script);self.index=0
    def guess(self,history,position):
        if self.mode in ("none","mtp"):return None
        if self.mode=="script":
            value=self.script[self.index] if self.index<len(self.script) else None
            self.index+=1;return value if value is not None and value>=0 else None
        for n in (2,1):
            if len(history)<n:continue
            for start in range(len(history)-n-1,-1,-1):
                if history[start:start+n]==history[-n:]:return history[start+n]
        return None
class Controller:
    def __init__(self,backend,draft,overlap=True,dumps=False):
        self.b=backend;self.draft=draft;self.overlap=overlap;self.dumps=dumps
        self.stats=dict(guesses=0,hits=0,misses=0,no_guess=0,redo_ms=0.)
    def run(self,prompt,count,eos=()):
        require(prompt and count>0,"empty prompt/generation")
        b=self.b;b.work_start=time.monotonic();history=[];tokens=[];stamps=[];rows=[];prefill_start=time.monotonic();prompt_ms=None;guess_sequence=[];guess_rows=[];mtp=self.draft.mode=="mtp";draft_pending=False;draft_rows=[]
        def fixture(p):return max(0,p-len(prompt)+2)
        def half(rank,token,p,spec=False):b.start(rank,HALF,token,p,fixture(p),int(spec))
        def accept(rank):b.call(rank,ACCEPT)
        half(0,prompt[0],0);b.wait(0);accept(0)
        for p in range(len(prompt)+count-1):
            cycle_start=time.monotonic()
            token=prompt[p] if p<len(prompt) else tokens[-1]
            history.append(token)
            draft_row=None
            if draft_pending:
                waiting=time.monotonic();b.wait(1);draft_row=b.draft_result(p+1);draft_row["rank0_idle_waiting_for_guess_ms"]=(time.monotonic()-waiting)*1000;draft_pending=False;draft_rows.append(draft_row)
            b.handover();half(1,token,p)
            if draft_row is not None:
                now=time.monotonic();draft_row["rank1_half_started_monotonic"]=now
                draft_row["rank1_before_half_ms"]=(now-draft_row.get("rank1_draft_started_monotonic",now))*1000
            more=p+1<len(prompt)+count-1;known=more and p+1<len(prompt)
            guess=None;pending=False
            if known and self.overlap:
                half(0,prompt[p+1],p+1);pending=True
            elif more and not known:
                guess=(draft_row.get("guess") if draft_row else None) if mtp else self.draft.guess(history,p+1)
                guess_sequence.append(guess)
                self.stats["guesses" if guess is not None else "no_guess"]+=1
                if guess is not None:half(0,guess,p+1,True);pending=True
            result=b.wait(1);stamp=time.monotonic();accept(1)
            if draft_row is not None:
                draft_row.update(actual=result["token"] if fixture(p)>0 else prompt[p+1],
                                 hit=(guess==result["token"]) if guess is not None and fixture(p)>0 else None,
                                 target_completed_monotonic=stamp)
                if len(draft_rows)>1:
                    previous=draft_rows[-2]
                    if previous.get("target_completed_monotonic") is not None and stamps:
                        previous["cycle_ms"]=(stamp-previous["target_completed_monotonic"])*1000
            if fixture(p)>0:
                emitted=result["token"];tokens.append(emitted);stamps.append(stamp)
                rows.append(dict(generated_index=len(tokens),token_id=emitted,completed_monotonic=stamp))
                if prompt_ms is None:prompt_ms=(stamp-prefill_start)*1000
                if emitted in eos:
                    if pending:b.wait(0);b.call(0,ROLLBACK)
                    break
            if not more:break
            if mtp:
                confirmed=prompt[p+1] if known else tokens[-1]
                b.start(1,DRAFT,confirmed,p+1,int(p+2>=len(prompt)),0);draft_pending=True
            if known:
                if not pending:half(0,prompt[p+1],p+1)
                b.wait(0);accept(0)
            else:
                actual=tokens[-1]
                if pending:
                    b.wait(0)
                    guess_rows.append(dict(position=p+1,guess=guess,actual=actual,hit=guess==actual))
                    if guess==actual:self.stats["hits"]+=1;accept(0)
                    else:
                        self.stats["misses"]+=1;start=time.monotonic();b.call(0,ROLLBACK)
                        half(0,actual,p+1);b.wait(0);accept(0);self.stats["redo_ms"]+=(time.monotonic()-start)*1000
                else:half(0,actual,p+1);b.wait(0);accept(0)
            if guess_rows and guess_rows[-1]["position"]==p+1:guess_rows[-1]["cycle_ms"]=(time.monotonic()-cycle_start)*1000
            if self.dumps:b.call(0,DUMP,position=p+1)
        b.work_end=time.monotonic()
        duration=(stamps[-1]-stamps[0])*1000 if len(stamps)>1 else 0
        diagnostic=self.draft.mode=="script" or getattr(getattr(b,"a",None),"draft_fault","none")!="none"
        return dict(tokens=tokens,guess_sequence=guess_sequence,guess_rows=guess_rows,stats=self.stats,prompt_wall_ms=prompt_ms,prompt_overlap=self.overlap,
                    diagnostic=diagnostic,evidence_label="DIAGNOSTIC ONLY: scripted guesses or provider fault injection; never a speed result" if diagnostic else "official draft head, draft-only 8-bit requantisation, output identical to sequential decode" if mtp else "CPU preparation; device qualification pending",
                    acceptance=self.stats["hits"]/self.stats["guesses"] if self.stats["guesses"] else None,draft_rows=draft_rows,decode_wall_ms=duration,decode_intervals=max(0,len(tokens)-1),decode_numerator=max(0,len(tokens)-1),
                    decode_definition="63 intervals ending at tokens 2..64, from completion of token 1 to token 64",
                    decode_tok_s=None if diagnostic or not b.device else (len(tokens)-1)*1000/duration if duration else None,
                    draft_cycle_totals={name:dict(count=len(v:=[r["cycle_ms"] for r in draft_rows if r.get("hit") is hit and "cycle_ms" in r]),total_ms=sum(v),mean_ms=sum(v)/len(v) if v else None) for name,hit in (("hit",True),("miss",False))},
                    diagnostic_interval_rate=(len(tokens)-1)*1000/duration if duration else None,timing_rows=rows)
NATIVE=10
class NativeController:
    def __init__(self,backend,draft,overlap=True,dumps=False):
        self.b=backend;self.draft=draft;self.overlap=overlap;self.dumps=dumps
    def run(self,prompt,count,eos=()):
        b=self.b;mode={"none":0,"ngram":1,"script":2,"mtp":3}[self.draft.mode]
        values=[mode,count,int(self.overlap),int(self.dumps),len(prompt),len(self.draft.script),len(eos),*prompt,*self.draft.script,*eos]
        (b.shared_path.parent/"native-request.txt").write_text(" ".join(map(str,values))+"\n")
        trace_start=len(b.trace)
        b.start(1,NATIVE);b.start(0,NATIVE)
        # io() polls health/stop/deadline without issuing any token commands.
        b.wait(0);b.wait(1)
        r=json.loads((b.shared_path.parent/"native-result.json").read_text())
        b.trace[trace_start:]=r["rank_trace"]
        b.work_start=r["work_start"];b.work_end=r["work_end"]
        b.metrics=[dict(busy_ms=0.,handover_ms=0.,calls=0,gpu_ms=0.) for _ in range(2)]
        for row in b.trace:
            m=b.metrics[row["rank"]];m["busy_ms"]+=row.get("busy_ms",0);m["gpu_ms"]+=row.get("gpu_ms",0);m["calls"]+=1
        diagnostic=self.draft.mode=="script" or getattr(b.a,"draft_fault","none")!="none"
        r.update(diagnostic=diagnostic,prompt_overlap=self.overlap,acceptance=r["stats"]["hits"]/r["stats"]["guesses"] if r["stats"]["guesses"] else None,
                 evidence_label="DIAGNOSTIC ONLY: scripted guesses or provider fault injection" if diagnostic else "official draft head, draft-only 8-bit requantisation, output identical to sequential decode" if self.draft.mode=="mtp" else "CPU preparation; device qualification pending",
                 decode_definition="(N-1)*1000/(completion_ms[N]-completion_ms[1]); N emitted events",
                 decode_tok_s=(r["decode_intervals"]*1000/r["decode_wall_ms"] if r["decode_wall_ms"] else None) if b.device and not diagnostic else None)
        return r

def command_occupancy_ms(trace,rank,left,right):
    # Union full command envelopes, including rollback/copy/accept work. HALF's
    # kernel-body busy_ms alone omits scalar transfers before its timer starts.
    intervals=sorted((max(left,r['rank_received']),min(right,r['rank_completed']))
                     for r in trace if r['rank']==rank and r['rank_completed']>left and r['rank_received']<right)
    total=0.;end=left
    for begin,finish in intervals:
        if finish>max(begin,end):total+=finish-max(begin,end)
        end=max(end,finish)
    return total*1000

def enrich_result(result,transport):
    trace=transport.trace;result['rank_trace']=trace
    def confirmed(half):
        resolutions=sorted((r for r in trace if r['rank']==0 and r['op'] in (ACCEPT,ROLLBACK) and r['rank_received']>=half['rank_completed']),key=lambda r:r['rank_received'])
        return bool(resolutions) and resolutions[0]['op']==ACCEPT
    for row in result.get('timing_rows',[]):
        fixture=row['generated_index']
        consumer=next((r for r in trace if r['op']==HALF and r['rank']==1 and r['fixture']==fixture),None)
        producers=[r for r in trace if r['op']==HALF and r['rank']==0 and r['position']==consumer['position'] and r['rank_completed']<=consumer['rank_received']] if consumer else []
        forward=(consumer['rank_received']-max(r['rank_completed'] for r in producers))*1000 if producers else None
        row['controller_handover_ms']=forward
        row['rank0_to_rank1_handover_ms']=forward
        successors=[r for r in trace if r['op']==HALF and r['rank']==0 and r['position']==consumer['position']+1 and r['token']==row['token_id'] and confirmed(r)] if consumer else []
        successor=min(successors,key=lambda r:r['rank_received']) if successors else None
        reverse=(successor['rank_received']-consumer['rank_completed'])*1000 if successor else None
        row['rank1_to_rank0_start_minus_finish_ms']=reverse
        row['rank1_to_rank0_handover_ms']=max(0.,reverse) if reverse is not None else None
        row['rank1_to_rank0_overlapped']=reverse<0 if reverse is not None else None
        row['rank1_to_rank0_scope']='verified-token next half; negative signed gap means speculative overlap; null means no next confirmed-token half'
    result['controller_time_definition']='rank0-to-rank1: confirmed half completion to peer start at the same position; rank1-to-rank0: target half completion to next half using its verified token; signed overlap retained separately from nonnegative handover cost'
    stats=result['stats'];result['acceptance']=stats['hits']/stats['guesses'] if stats['guesses'] else None
    result['hit_miss_cycles']={}
    cycles=result.get('draft_rows',[]) if result.get('draft_rows') else result.get('guess_rows',[])
    for name,hit in (('hit',True),('miss',False)):
        values=[r['cycle_ms'] for r in cycles if r.get('hit') is hit and 'cycle_ms' in r]
        result['hit_miss_cycles'][name]=dict(count=len(values),total_ms=sum(values),mean_ms=sum(values)/len(values) if values else None)
    elapsed=(transport.work_end-transport.work_start)*1000
    for rank,m in enumerate(transport.metrics):
        occupied=command_occupancy_ms(trace,rank,transport.work_start,transport.work_end)
        lower=max(0.,elapsed-occupied)
        m.update(request_wall_ms=elapsed,host_command_busy_ms=occupied,host_command_idle_lower_bound_ms=lower,
                 gpu_event_timing_available=bool(transport.device and transport.a.timing!='token'))
        if not transport.device:
            m.update(gpu_idle_estimate_ms=None,gpu_idle_estimate_kind='not applicable: CPU backend',gpu_idle_estimate_scope='host command occupancy only; no GPU event timing')
        elif transport.a.timing=='token':
            m.update(gpu_idle_estimate_ms=lower,gpu_idle_estimate_kind='lower bound from host command occupancy',
                     gpu_idle_estimate_scope='request wall minus union of full rank command envelopes; command time may contain GPU idle, so this is a lower bound, not measured GPU event time')
        else:
            m.update(gpu_idle_estimate_ms=max(0.,elapsed-m['gpu_ms']),gpu_idle_estimate_kind='profiled kernel time complement',
                     gpu_idle_estimate_scope='request wall minus summed profiled GPU kernel time; includes unprofiled copies and coordination; host-command lower bound retained separately')
    result['rank_metrics']=transport.metrics
    return result

SUBMISSION_DEFINITION = ('rate for the 99 inter-token intervals between generated-token timestamps 1 and 100 after TTFT; '
                         '99 / (t100 - t1), timestamps in seconds; 100 events, 99 intervals')
LEGACY_DEFINITION = ('(N-1) / (tN - t1), timestamps in seconds; first N=min(64, non-EOG output count) events; '
                     '63 intervals ending at tokens 2..64 for N=64')

def request_timing_metadata(result,transport,prompt,count):
    """Wrapper accounting only: preserve every completion and both fixed spans."""
    rows=result.get('timing_rows',[])
    stamps=[r['completed_monotonic'] for r in rows]
    require(len(stamps)==len(result['tokens']), 'missing generated-token completion timestamp')
    require(all(math.isfinite(t) for t in stamps) and
            all(b>=a for a,b in zip(stamps,stamps[1:])), 'invalid completion timestamps')
    start,end=transport.work_start,transport.work_end
    require(not stamps or start<=stamps[0]<=stamps[-1]<=end,'completion outside request')
    elapsed=end-start
    speed=transport.device and not result.get('diagnostic')
    legacy=rows[:-1] if rows and rows[-1]['token_id'] in (248044,248046) else rows
    legacy=legacy[:64]
    span=legacy[-1]['completed_monotonic']-legacy[0]['completed_monotonic'] if len(legacy)>1 else 0.
    intervals=max(0,len(legacy)-1)
    submission_span=stamps[99]-stamps[0] if len(stamps)>=100 else None
    result.update(requested_output_tokens=count,prompt_tokens=len(prompt),output_tokens=len(stamps),
        ended_early=len(stamps)<count,request_start_monotonic=start,request_end_monotonic=end,
        generated_token_completion_timestamps=stamps,completion_timestamp_clock='monotonic seconds',
        ttft_ms=(stamps[0]-start)*1000 if stamps else None,
        ttft_definition='1000 * (t1 - request_start); prompt processing plus first generated token',
        prompt_wall_definition='native/controller prompt_wall_ms includes first generated token; do not add it to TTFT',
        request_wall_ms=elapsed*1000,wall_tok_s=len(stamps)/elapsed if speed and elapsed>0 else None,
        wall_rate_definition='output_tokens / (request_end - request_start); prompt plus full generation, excludes load/reset/teardown',
        guesses=result['stats']['guesses'],hits=result['stats']['hits'],
        decode_wall_ms=span*1000,decode_intervals=intervals,decode_numerator=intervals,
        decode_event_count=len(legacy),decode_definition=LEGACY_DEFINITION,
        decode_tok_s=intervals/span if speed and span>0 else None,
        submission_tok_s=99/submission_span if speed and submission_span and submission_span>0 else None,
        submission_definition=SUBMISSION_DEFINITION,
        submission_event_count=100 if submission_span is not None else 0,
        submission_intervals=99 if submission_span is not None else 0,
        submission_numerator=99 if submission_span is not None else 0,
        submission_first_completed_monotonic=stamps[0] if submission_span is not None else None,
        submission_last_completed_monotonic=stamps[99] if submission_span is not None else None,
        submission_wall_ms=submission_span*1000 if submission_span is not None else None,
        submission_window_available=submission_span is not None)
    return result

def request_run(transport,provider,prompt,count,eos=(),overlap=True,dumps=False):
    cls=NativeController if getattr(transport.a,"controller","python")=="native" else Controller
    result=cls(transport,provider,overlap,dumps).run(prompt,count,eos)
    result["controller"]=getattr(transport.a,"controller","python")
    return request_timing_metadata(enrich_result(result,transport),transport,prompt,count)

class Transport:
    def __init__(self,args,out,environment=None,check=None,launch_hook=None):
        self.a=args;self.out=out;self.device=args.device;self.check=check or (lambda:None)
        self.children=[];self.sockets=[];self.logs=[];self.seq=[0,0];self.pending=[False,False];self.started=[0.,0.];self.commands=[{},{}]
        self.metrics=[dict(busy_ms=0.,handover_ms=0.,calls=0,gpu_ms=0.) for _ in range(2)]
        self.trace=[];self.stop_sent=False;self.retained=[];self.failure_hook=lambda reason:None;self.closed=False;self.finishing=set();self.last_complete=[0.,0.]
        self.shared_path=out/"shared.bin"
        fd=os.open(self.shared_path,os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600);os.ftruncate(fd,SHARED)
        self.mapping=mmap.mmap(fd,SHARED);os.close(fd)
        self.stop_read,self.stop_write=os.pipe();self.start_time=time.monotonic()
        env=dict(environment) if environment is not None else {"PATH":"/usr/bin:/bin","OMP_NUM_THREADS":"2"}
        if not self.device:
            for key in ("ASAN_OPTIONS","UBSAN_OPTIONS","PACKET24_ORDER_SEED"):
                if key in os.environ:env[key]=os.environ[key]
        if "LD_LIBRARY_PATH" in os.environ:
            require("LD_LIBRARY_PATH" not in env or env["LD_LIBRARY_PATH"]==os.environ["LD_LIBRARY_PATH"],"coordinator LD_LIBRARY_PATH changed")
            env["LD_LIBRARY_PATH"]=os.environ["LD_LIBRARY_PATH"]
        for rank in range(2):
            rank_home=P/"build"/"driver-cache"/("rank"+str(rank));rank_home.mkdir(parents=True,exist_ok=True)
            cache_warm=any(f.is_file() for f in rank_home.rglob("*"))
            env["HOME"]=str(rank_home)
            parent,child=socket.socketpair();parent.setblocking(False);self.sockets.append(parent)
            dest=out/("rank"+str(rank));log=(out/("rank"+str(rank)+".log")).open("w");self.logs.append(log)
            cmd=[str(args.binary),"--rank",str(rank),"--channel",str(child.fileno()),"--stop-fd",str(self.stop_read),
                 "--shared",str(self.shared_path),"--cards","1","--card",str(args.card+rank),"--output",str(dest),
                 "--memory","resident" if self.device else getattr(args,"host_memory","layer-streaming"),"--context",str(args.context),"--seconds",str(args.seconds),
                 "--native-nice",str(args.native_nice),"--timing",args.timing,"--max-new",str(args.tokens)]
            if args.draft=="mtp" and rank==1:cmd += ["--draft-mtp","--draft-fault",getattr(args,"draft_fault","none")]
            if getattr(args,"canary",False):cmd += ["--pipeline-canary"]
            if args.mini or getattr(args,"canary",False):cmd += ["--mini","--pipeline-mini"]
            else:
                inp=json.loads((args.input/"input.json").read_text())
                cmd += ["--plan",str(args.input/"plan.tsv"),"--identity",str(args.input/"identity.tsv"),"--model-dir",inp["model_dir"]]
            cmd += ["--host-path",getattr(args,"host_path","prepared")]
            if getattr(args,"argument_audit",False):cmd += ["--argument-audit"]
            if getattr(args,"audit_prepare_each",False):cmd += ["--audit-prepare-each"]
            if args.oracle:cmd += ["--oracle",str(args.oracle)]
            if args.dispatch:cmd += ["--dispatch",str(args.dispatch)]
            if self.device:cmd += ["--authorized-device-window"]
            proc=subprocess.Popen(["ionice","-c","3"]+cmd,pass_fds=(child.fileno(),self.stop_read),stdout=log,stderr=subprocess.STDOUT,env=env)
            self.children.append(proc);child.close()
            if launch_hook:launch_hook(proc.pid)
            save(out/f"rank{rank}-launch.json",dict(argv=cmd,pid=proc.pid,environment=env,device_executed=self.device,cpu_affinity=sorted(os.sched_getaffinity(0)),native_nice=args.native_nice,driver_cache_home=str(rank_home),driver_cache_files_present_before=cache_warm,driver_cache_hit="unobservable; files present is not proof of a hit"))
        for rank in range(2):self.receive(rank,args.seconds,ready=True)
        if self.device and not args.mini and not getattr(args,"canary",False):
            from memory_gate import check as admit, snapshot
            ledger=json.loads((P/"memory-plan.json").read_text())
            census=[json.loads((out/f"rank{rank}/census.json").read_text()) for rank in range(2)]
            save(out/"device-memory-admission.json",dict(passed=True,ranks=[dict(admit(c,ledger,r,args.draft=="mtp"),process=snapshot(self.children[r].pid)) for r,c in enumerate(census)]))
    def check_alive(self):
        self.check()
        require(time.monotonic()-self.start_time<self.a.seconds,"pipeline total deadline")
        for rank,proc in enumerate(self.children):
            require(proc.poll() is None or rank in self.finishing,"rank failed/closed unexpectedly")
        # No device APIs: bound our two child anonymous mappings using procfs.
        anonymous=0
        for proc in self.children:
            try:
                for line in Path(f"/proc/{proc.pid}/status").read_text().splitlines():
                    if line.startswith("RssAnon:"):anonymous+=int(line.split()[1])*1024
            except FileNotFoundError:pass
        require(anonymous<8*1024**3,"aggregate rank anonymous memory exceeded 8 GiB")
    def io(self,rank,payload=None,timeout=None):
        end=time.monotonic()+(timeout or self.a.wait_seconds);data=bytearray();sent=0;sock=self.sockets[rank]
        while (sent<len(payload) if payload is not None else len(data)<REPLY.size):
            self.check_alive();require(time.monotonic()<end,"bounded rank channel timeout")
            readable,writable,_=select.select([sock] if payload is None else [],[sock] if payload is not None else [],[],min(.05,max(0,end-time.monotonic())))
            if payload is not None and writable:
                n=sock.send(payload[sent:]);require(n>0,"rank send EOF");sent+=n
            elif payload is None and readable:
                part=sock.recv(REPLY.size-len(data));require(part,"rank receive EOF");data.extend(part)
        return bytes(data)
    def receive(self,rank,timeout=None,ready=False):
        values=REPLY.unpack(self.io(rank,timeout=timeout))
        require(values[0]==0 and values[2]==0 and values[4]==self.seq[rank] and values[5]==rank,"rank reply status/sequence/identity")
        require(0<=values[3]<=SLOT,"rank payload bounds")
        if not ready:
            m=self.metrics[rank];m["busy_ms"]+=values[8];m["gpu_ms"]+=values[9];m["calls"]+=1
            m["handover_ms"]+=max(0.,values[10]*1000-self.started[rank]*1000)
            self.last_complete[rank]=values[11]
            self.trace.append(dict(rank=rank,sequence=self.seq[rank],busy_ms=values[8],gpu_ms=values[9],rank_received=values[10],rank_completed=values[11],received=time.monotonic(),**self.commands[rank]))
        if rank==0 and self.commands[rank].get("op")==HALF:
            require(values[3]==(128 if self.a.mini else 20480),"rank0 stream payload extent")
            self.stream_bytes=values[3]
        return dict(token=values[1],bytes=values[3],busy_ms=values[8])
    def start(self,rank,op,token=0,position=0,fixture=0,speculative=0):
        require(not self.pending[rank],"second command to busy rank")
        self.seq[rank]+=1;self.started[rank]=time.monotonic();self.commands[rank]=dict(op=op,token=token,position=position,fixture=fixture,speculative=bool(speculative))
        self.io(rank,REQUEST.pack(op,token,position,fixture,speculative,self.seq[rank],0,0));self.pending[rank]=True
    def wait(self,rank):
        require(self.pending[rank],"wait without command")
        result=self.receive(rank);self.pending[rank]=False;return result
    def call(self,rank,op,token=0,position=0,fixture=0,speculative=0):
        self.start(rank,op,token,position,fixture,speculative);return self.wait(rank)
    def handover(self):
        require(not self.pending[1],"overwrite consumer payload while busy")
        n=self.stream_bytes;self.mapping[SLOT:SLOT+n]=self.mapping[:n]
    def draft_result(self,expected_position):
        v=PUBLICATION.unpack(self.mapping[2*SLOT:2*SLOT+PUBLICATION.size])
        valid,position,token,error,ns,sequence,reserved,gpu=v
        vocab=16 if self.a.mini else 248320
        good=valid==1 and not error and position==expected_position and sequence==self.seq[1] and 0<=token<vocab
        return dict(position=position,sequence=sequence,guess=token if good else None,provider_error=error,
                    draft_wall_ms=ns/1e6,draft_gpu_ms=gpu if self.device else None,
                    gpu_timing_available=self.device,rank1_draft_started_monotonic=self.started[1])
    def stop(self,reason):
        if not self.stop_sent:
            self.stop_errors=getattr(self,"stop_errors",[])
            failure_attempt("failure hook",lambda:self.failure_hook(reason),self.stop_errors)
            failure_attempt("failure receipt",lambda:save(self.out/"failure-before-teardown.json",dict(passed=False,reason=str(reason),pids=[p.pid for p in self.children])),self.stop_errors)
            # Attempt the receipt before signalling, even if the filesystem is full.
            # Both ranks poll without consuming the byte; closing also wakes both.
            try:
                if not self.closed:os.write(self.stop_write,b"!")
            except OSError as error:
                self.stop_errors.append(f"stop pipe write: {error}")
                failure_attempt("stop pipe close",lambda:os.close(self.stop_write),self.stop_errors)
            finally:self.stop_sent=True
    def close(self,success):
        if self.closed:return
        if success:
            for rank in range(len(self.children)):
                require(not self.pending[rank],"finish with in-flight command")
                self.finishing.add(rank);self.seq[rank]+=1;self.io(rank,REQUEST.pack(FINISH,0,0,0,0,self.seq[rank],0,0))
        else:self.stop("controller failure")
        end=time.monotonic()+65
        drain_error=None
        while any(p.poll() is None for p in self.children) and time.monotonic()<end:
            try:self.check()
            except Exception as error:
                drain_error=error;self.stop(error)
            time.sleep(.05)
        self.retained=[p.pid for p in self.children if p.poll() is None]
        ownership_error=[]
        failure_attempt("ownership receipt",lambda:save(self.out/"ownership.json",dict(retained_pids=self.retained,stop_requested=self.stop_sent,returncodes=[p.poll() for p in self.children],signals_sent=0,diagnostic_errors=getattr(self,"stop_errors",[]))),ownership_error)
        if not self.retained:
            self.mapping.close();self.shared_path.unlink();os.close(self.stop_read)
            try:os.close(self.stop_write)
            except OSError:pass
            for s in self.sockets:s.close()
            for log in self.logs:log.close()
            self.closed=True
        require(not self.retained,"rank retained for coordinator after bounded drain")
        if drain_error is not None:raise drain_error
        if ownership_error:raise OSError("; ".join(ownership_error))
        if success:
            for rank,p in enumerate(self.children):
                r=json.loads((self.out/f"rank{rank}/receipt.json").read_text())
                require(p.returncode==0 and r["passed"] and r.get("rank")==rank and len(r["teardown"])==1 and all(t["safe_to_exit"] and not t["in_flight"] and not t["live_bytes"] for t in r["teardown"]),"rank teardown failure")
def run(args,environment=None,check=None,failure_hook=None,launch_hook=None):
    if getattr(args,"suite_manifest",None):
        from suite import run as suite_run
        return suite_run(args,environment,check,failure_hook,launch_hook)
    require(os.getpriority(os.PRIO_PROCESS,0)==args.native_nice,"declared priority mismatch")
    require(os.environ.get("OMP_NUM_THREADS")=="2","OMP_NUM_THREADS=2 required")
    require(not args.output.exists(),"new output required");args.output.mkdir(parents=True)
    if args.draft=="script":print("DIAGNOSTIC ONLY: scripted guesses; never a speed result",flush=True)
    prompt=[2,5,3,7,1] if args.mini else list(map(int,(args.input/"tokens.txt").read_text().split()))
    require(len(prompt)+args.tokens-1<=args.context,"context exceeded")
    require((args.draft=="script")==bool(args.script),"script provider requires its guess file")
    guesses=list(map(int,args.script.read_text().split())) if args.script else []
    provider=Draft(args.draft,guesses)
    binary_hash=sha(args.binary)
    transport=None;result=dict(passed=False,device_executed=args.device);failure=None
    stopped=[]
    def check_all():
        require(not stopped,"coordinator stop requested")
        if check:check()
    old={s:signal.signal(s,lambda signum,frame:stopped.append(signum)) for s in (signal.SIGTERM,signal.SIGINT)}
    try:
        # Keep partially constructed ownership reachable on constructor failure.
        transport=Transport.__new__(Transport);transport.__init__(args,args.output,environment,check_all,launch_hook)
        if failure_hook:transport.failure_hook=failure_hook
        result.update(request_run(transport,provider,prompt,args.tokens,() if args.mini else (248044,248046),args.prompt_overlap=="on",args.dump_state))
        # Final-state evidence is outside the model timing span. Keep both rank
        # dumps even when intermediate --dump-state snapshots were not requested.
        trace_end=len(transport.trace);request_metrics=[dict(m) for m in transport.metrics]
        for rank in (0,1):transport.call(rank,DUMP,position=2147483647)
        result['final_state_commands']=transport.trace[trace_end:];del transport.trace[trace_end:]
        transport.metrics=request_metrics
        result['final_state']={str(rank):f'rank{rank}/state-2147483647' for rank in (0,1)}
        if args.draft=='mtp':result['draft_final_state']='rank1/draft-final-state'
        if args.oracle:
            expected=json.loads((args.oracle/"result.json").read_text())["tokens"][:args.tokens]
            require(result["tokens"]==expected,"oracle generated-token mismatch")
        transport.close(True);result["passed"]=True
    except Exception as error:
        failure=error;result.update(error=str(error),passed=False)
        diagnostic_errors=[]
        failure_attempt("failure receipt",lambda:save(args.output/"receipt.json",result),diagnostic_errors)
        if failure_hook:failure_attempt("failure hook",lambda:failure_hook(error),diagnostic_errors)
        if transport is not None and hasattr(transport,"stop_write"):
            try:transport.stop(error)
            finally:
                try:transport.close(False)
                except Exception as teardown:result["teardown_error"]=str(teardown)
        if diagnostic_errors:result["diagnostic_errors"]=diagnostic_errors
    finally:
        for s,handler in old.items():signal.signal(s,handler)
    if transport is not None and hasattr(transport,"metrics"):
        elapsed=(getattr(transport,"work_end",time.monotonic())-getattr(transport,"work_start",transport.start_time))*1000
        for m in transport.metrics:
            m["idle_and_coordination_ms"]=max(0.,elapsed-m["busy_ms"])
            m["busy_ms_per_output_token"]=m["busy_ms"]/max(1,len(result.get("tokens",[])))
            m["idle_ms_per_output_token"]=m["idle_and_coordination_ms"]/max(1,len(result.get("tokens",[])))
        result.update(rank_metrics=transport.metrics,rank_trace=transport.trace,rank_timing_scope="model request only, excluding load/teardown; busy includes half and draft wall time, idle includes coordinator and accept/rollback IO")
        for rank in range(2):
            profile=args.output/f"rank{rank}/class-times.json"
            if profile.exists():
                row=json.loads(profile.read_text());row["scope"]="entire request: prompt plus accepted, rejected and redone halves";save(profile,row)
    if args.timing=="class":
        result.update(decode_tok_s=None,diagnostic=True,evidence_label="DIAGNOSTIC ONLY: per-class profiling")
    # Clip half intervals to the same token1..token64 wall span used by decode.
    stamps=result.get("timing_rows",[])
    if len(stamps)>1 and transport is not None:
        left,right=stamps[0]["completed_monotonic"],stamps[-1]["completed_monotonic"]
        count=len(stamps)-1;span=(right-left)*1000;decode_ranks=[]
        for rank in (0,1):
            busy=sum(max(0.,min(right,t["rank_completed"])-max(left,t["rank_received"]))*1000
                     for t in transport.trace if t["rank"]==rank and t["op"] in (HALF,DRAFT))
            decode_ranks.append(dict(rank=rank,intervals=count,busy_ms=busy,idle_and_coordination_ms=max(0.,span-busy),
                busy_ms_per_interval=busy/count,idle_ms_per_interval=max(0.,span-busy)/count))
        result["decode_rank_metrics"]=decode_ranks
        result["decode_rank_timing_scope"]="native host HALF wall occupancy clipped to decode span; includes uploads/drains, not GPU busy time"
    result.update(arithmetic="iq3-p17-detmath-v2",draft=args.draft,binary_sha256=binary_hash,no_speed_claim=True,host_path=getattr(args,"host_path","prepared"),cpu_affinity=sorted(os.sched_getaffinity(0)),load_average=list(os.getloadavg()))
    save(args.output/"receipt.json",result)
    if failure:raise failure
    return result

class PipelineParser(argparse.ArgumentParser):
    def parse_args(self,*args,**kwargs):
        a=super().parse_args(*args,**kwargs)
        if isinstance(a.draft,list):
            values=a.draft;a.draft=values[0]
            require(a.draft in ("none","ngram","script","mtp"),"draft provider")
            require(len(values)==1 or (a.draft=="script" and len(values)==2 and not a.script),"--draft script FILE syntax")
            if len(values)==2:a.script=Path(values[1])
        return a
def parser():
    p=PipelineParser(description=__doc__)
    p.add_argument("--binary",type=Path,default=P/"build/gnu-host/own-rt-iq3")
    p.add_argument("--output",type=Path,required=True);p.add_argument("--input",type=Path);p.add_argument("--oracle",type=Path);p.add_argument("--dispatch",type=Path)
    p.add_argument("--mini",action="store_true");p.add_argument("--device",action="store_true");p.add_argument("--draft",nargs="+",default="none")
    p.add_argument("--draft-head",choices=("full",),default="full")
    p.add_argument("--draft-fault",choices=("none","wrong","error","stall","suppress","garbage","late-error"),default="none")
    p.add_argument("--script",type=Path);p.add_argument("--prompt-overlap",choices=("on","off"),default="on");p.add_argument("--dump-state",action="store_true")
    p.add_argument("--card",type=int,default=0);p.add_argument("--tokens",type=int,default=8);p.add_argument("--context",type=int,default=256)
    p.add_argument("--seconds",type=int,default=10800);p.add_argument("--wait-seconds",type=int,default=3600);p.add_argument("--native-nice",type=int,default=19)
    p.add_argument("--timing",choices=("token","class"),default="token")
    p.add_argument("--suite-manifest",type=Path);p.add_argument("--repeat",type=int,default=1)
    p.add_argument("--controller",choices=("python","native"),default="python")
    p.add_argument("--host-path",choices=("legacy","prepared"),default="prepared")
    p.add_argument("--argument-audit",action="store_true");p.add_argument("--audit-prepare-each",action="store_true")
    return p
if __name__=="__main__":
    a=parser().parse_args()
    require(not a.device,"device ranks must be launched by admitted window.py")
    require((a.draft=="script")==bool(a.script),"--draft script requires exactly one --script FILE")
    run(a)
