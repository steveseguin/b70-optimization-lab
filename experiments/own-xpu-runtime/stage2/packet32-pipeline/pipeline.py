#!/usr/bin/env python3
"""Bounded two-process controller; CPU host backend by default. No threads."""
import argparse, hashlib, json, mmap, os, select, signal, socket, struct, subprocess, time
from pathlib import Path
P=Path(__file__).resolve().parent
SLOT=65536;SHARED=2*SLOT+4096
REQUEST=struct.Struct("<8i");REPLY=struct.Struct("<8i4d")
HALF,ACCEPT,ROLLBACK,DUMP,FINISH,CANARY,FAIL,STALL=range(1,9)
def save(path,value):
    path.write_text(json.dumps(value,indent=2)+"\n")
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def require(test,message):
    if not test:raise ValueError(message)
class Draft:
    """guess(history, position) -> token | None, using confirmed history only.

    Future MTP provider: rank1 consumes previous final streams + embedding(x_p)
    before its HALF(p), publishing {valid,position,token,error,elapsed_ns} at
    shared offset 131072. It cannot mutate target state or target arithmetic.
    The controller never treats the provider result as an emitted token.
    """
    def __init__(self,mode="none",script=()):
        require(mode in ("none","ngram","script"),"mtp provider hook exists; implementation not built")
        self.mode=mode;self.script=list(script);self.index=0
    def guess(self,history,position):
        if self.mode=="none":return None
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
        b=self.b;b.work_start=time.monotonic();history=[];tokens=[];stamps=[];rows=[];prefill_start=time.monotonic();prompt_ms=None
        def fixture(p):return max(0,p-len(prompt)+2)
        def half(rank,token,p,spec=False):b.start(rank,HALF,token,p,fixture(p),int(spec))
        def accept(rank):b.call(rank,ACCEPT)
        half(0,prompt[0],0);b.wait(0);accept(0)
        for p in range(len(prompt)+count-1):
            token=prompt[p] if p<len(prompt) else tokens[-1]
            history.append(token)
            b.handover();half(1,token,p)
            more=p+1<len(prompt)+count-1;known=more and p+1<len(prompt)
            guess=None;pending=False
            if known and self.overlap:
                half(0,prompt[p+1],p+1);pending=True
            elif more and not known:
                guess=self.draft.guess(history,p+1)
                self.stats["guesses" if guess is not None else "no_guess"]+=1
                if guess is not None:half(0,guess,p+1,True);pending=True
            result=b.wait(1);stamp=time.monotonic();accept(1)
            if fixture(p)>0:
                emitted=result["token"];tokens.append(emitted);stamps.append(stamp)
                rows.append(dict(generated_index=len(tokens),token_id=emitted,completed_monotonic=stamp))
                if prompt_ms is None:prompt_ms=(stamp-prefill_start)*1000
                if emitted in eos:
                    if pending:b.wait(0);b.call(0,ROLLBACK)
                    break
            if not more:break
            if known:
                if not pending:half(0,prompt[p+1],p+1)
                b.wait(0);accept(0)
            else:
                actual=tokens[-1]
                if pending:
                    b.wait(0)
                    if guess==actual:self.stats["hits"]+=1;accept(0)
                    else:
                        self.stats["misses"]+=1;start=time.monotonic();b.call(0,ROLLBACK)
                        half(0,actual,p+1);b.wait(0);accept(0);self.stats["redo_ms"]+=(time.monotonic()-start)*1000
                else:half(0,actual,p+1);b.wait(0);accept(0)
            if self.dumps:b.call(0,DUMP,position=p+1)
        b.work_end=time.monotonic()
        duration=(stamps[-1]-stamps[0])*1000 if len(stamps)>1 else 0
        diagnostic=self.draft.mode=="script"
        return dict(tokens=tokens,stats=self.stats,prompt_wall_ms=prompt_ms,prompt_overlap=self.overlap,
                    diagnostic=diagnostic,evidence_label="DIAGNOSTIC ONLY: scripted guesses; never a speed result" if diagnostic else "CPU preparation; device qualification pending",
                    decode_wall_ms=duration,decode_intervals=max(0,len(tokens)-1),decode_numerator=max(0,len(tokens)-1),
                    decode_definition="63 intervals ending at tokens 2..64, from completion of token 1 to token 64",
                    decode_tok_s=None if diagnostic or not b.device else (len(tokens)-1)*1000/duration if duration else None,
                    diagnostic_interval_rate=(len(tokens)-1)*1000/duration if duration else None,timing_rows=rows)
class Transport:
    def __init__(self,args,out,environment=None,check=None):
        self.a=args;self.out=out;self.device=args.device;self.check=check or (lambda:None)
        self.children=[];self.sockets=[];self.logs=[];self.seq=[0,0];self.pending=[False,False];self.started=[0.,0.];self.commands=[{},{}]
        self.metrics=[dict(busy_ms=0.,handover_ms=0.,calls=0,gpu_ms=0.) for _ in range(2)]
        self.trace=[];self.stop_sent=False;self.retained=[];self.failure_hook=lambda reason:None;self.closed=False;self.finishing=set();self.last_complete=[0.,0.]
        self.shared_path=out/"shared.bin"
        fd=os.open(self.shared_path,os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600);os.ftruncate(fd,SHARED)
        self.mapping=mmap.mmap(fd,SHARED);os.close(fd)
        self.stop_read,self.stop_write=os.pipe();self.start_time=time.monotonic()
        env=environment or {"PATH":"/usr/bin:/bin","OMP_NUM_THREADS":"2"}
        if not self.device:
            for key in ("ASAN_OPTIONS","UBSAN_OPTIONS","PACKET24_ORDER_SEED"):
                if key in os.environ:env[key]=os.environ[key]
        if "LD_LIBRARY_PATH" in os.environ and "LD_LIBRARY_PATH" not in env:env["LD_LIBRARY_PATH"]=os.environ["LD_LIBRARY_PATH"]
        for rank in range(2):
            parent,child=socket.socketpair();parent.setblocking(False);self.sockets.append(parent)
            dest=out/("rank"+str(rank));log=(out/("rank"+str(rank)+".log")).open("w");self.logs.append(log)
            cmd=[str(args.binary),"--rank",str(rank),"--channel",str(child.fileno()),"--stop-fd",str(self.stop_read),
                 "--shared",str(self.shared_path),"--cards","1","--card",str(args.card+rank),"--output",str(dest),
                 "--memory","resident" if self.device else getattr(args,"host_memory","layer-streaming"),"--context",str(args.context),"--seconds",str(args.seconds),
                 "--native-nice",str(args.native_nice),"--timing",args.timing,"--max-new",str(args.tokens)]
            if getattr(args,"canary",False):cmd += ["--pipeline-canary"]
            if args.mini or getattr(args,"canary",False):cmd += ["--mini","--pipeline-mini"]
            else:
                inp=json.loads((args.input/"input.json").read_text())
                cmd += ["--plan",str(args.input/"plan.tsv"),"--identity",str(args.input/"identity.tsv"),"--model-dir",inp["model_dir"]]
            if args.oracle:cmd += ["--oracle",str(args.oracle)]
            if args.dispatch:cmd += ["--dispatch",str(args.dispatch)]
            if self.device:cmd += ["--authorized-device-window"]
            proc=subprocess.Popen(["ionice","-c","3"]+cmd,pass_fds=(child.fileno(),self.stop_read),stdout=log,stderr=subprocess.STDOUT,env=env)
            self.children.append(proc);child.close()
            save(out/f"rank{rank}-launch.json",dict(argv=cmd,pid=proc.pid,environment=env,device_executed=self.device))
        for rank in range(2):self.receive(rank,args.seconds,ready=True)
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
            self.trace.append(dict(rank=rank,sequence=self.seq[rank],busy_ms=values[8],rank_received=values[10],rank_completed=values[11],received=time.monotonic(),**self.commands[rank]))
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
    def stop(self,reason):
        if not self.stop_sent:
            self.failure_hook(reason)
            save(self.out/"failure-before-teardown.json",dict(passed=False,reason=str(reason),pids=[p.pid for p in self.children]))
            if not self.closed:os.write(self.stop_write,b"!")
            self.stop_sent=True
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
        save(self.out/"ownership.json",dict(retained_pids=self.retained,stop_requested=self.stop_sent,returncodes=[p.poll() for p in self.children],signals_sent=0))
        if not self.retained:
            self.mapping.close();self.shared_path.unlink();os.close(self.stop_read);os.close(self.stop_write)
            for s in self.sockets:s.close()
            for log in self.logs:log.close()
            self.closed=True
        require(not self.retained,"rank retained for coordinator after bounded drain")
        if drain_error is not None:raise drain_error
        if success:
            for rank,p in enumerate(self.children):
                r=json.loads((self.out/f"rank{rank}/receipt.json").read_text())
                require(p.returncode==0 and r["passed"] and r.get("rank")==rank and len(r["teardown"])==1 and all(t["safe_to_exit"] and not t["in_flight"] and not t["live_bytes"] for t in r["teardown"]),"rank teardown failure")
def run(args,environment=None,check=None,failure_hook=None):
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
        transport=Transport.__new__(Transport);transport.__init__(args,args.output,environment,check_all)
        if failure_hook:transport.failure_hook=failure_hook
        result.update(Controller(transport,provider,args.prompt_overlap=="on",args.dump_state).run(prompt,args.tokens,() if args.mini else (248044,248046)))
        if args.oracle:
            expected=json.loads((args.oracle/"result.json").read_text())["tokens"][:args.tokens]
            require(result["tokens"]==expected,"oracle generated-token mismatch")
        transport.close(True);result["passed"]=True
    except Exception as error:
        failure=error;result.update(error=str(error),passed=False)
        if failure_hook:failure_hook(error)
        save(args.output/"receipt.json",result)
        if transport is not None and hasattr(transport,"stop_write"):
            transport.stop(error)
            try:transport.close(False)
            except Exception as teardown:result["teardown_error"]=str(teardown)
    finally:
        for s,handler in old.items():signal.signal(s,handler)
    if transport is not None and hasattr(transport,"metrics"):
        elapsed=(getattr(transport,"work_end",time.monotonic())-getattr(transport,"work_start",transport.start_time))*1000
        for m in transport.metrics:
            m["idle_and_coordination_ms"]=max(0.,elapsed-m["busy_ms"])
            m["busy_ms_per_output_token"]=m["busy_ms"]/max(1,len(result.get("tokens",[])))
            m["idle_ms_per_output_token"]=m["idle_and_coordination_ms"]/max(1,len(result.get("tokens",[])))
        result.update(rank_metrics=transport.metrics,rank_trace=transport.trace,rank_timing_scope="model request only, excluding load/teardown; busy is half wall time, idle includes coordinator and accept/rollback IO")
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
                     for t in transport.trace if t["rank"]==rank and t["op"]==HALF)
            decode_ranks.append(dict(rank=rank,intervals=count,busy_ms=busy,idle_and_coordination_ms=max(0.,span-busy),
                busy_ms_per_interval=busy/count,idle_ms_per_interval=max(0.,span-busy)/count))
        result["decode_rank_metrics"]=decode_ranks
        result["decode_rank_timing_scope"]="native host HALF wall occupancy clipped to decode span; includes uploads/drains, not GPU busy time"
    result.update(arithmetic="iq3-p17-detmath-v2",draft=args.draft,binary_sha256=binary_hash,no_speed_claim=True)
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
    p.add_argument("--script",type=Path);p.add_argument("--prompt-overlap",choices=("on","off"),default="on");p.add_argument("--dump-state",action="store_true")
    p.add_argument("--card",type=int,default=0);p.add_argument("--tokens",type=int,default=8);p.add_argument("--context",type=int,default=256)
    p.add_argument("--seconds",type=int,default=10800);p.add_argument("--wait-seconds",type=int,default=3600);p.add_argument("--native-nice",type=int,default=19)
    p.add_argument("--timing",choices=("token","class"),default="token")
    return p
if __name__=="__main__":
    a=parser().parse_args()
    require(not a.device,"device ranks must be launched by admitted window.py")
    require((a.draft=="script")==bool(a.script),"--draft script requires exactly one --script FILE")
    run(a)
