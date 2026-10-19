"""Run the actual device binary's explicit CPU-only preparation path."""
import json,os,resource,subprocess,sys
from prepare import P,sha,save
from build_engine import limits,compiler_turn
def main():
    records=[];revision=sys.argv[1] if len(sys.argv)>1 else 'a'
    for kind in ('smoke','v5'):
        limits();proposal=P/'proposals'/f'{kind}.json';row=json.loads(proposal.read_text())
        argv=row['native_argv'].copy();output=P/f'evidence/preparation-{revision}-{kind}'
        assert not output.exists(),'fresh probe output required'
        argv[argv.index('--output')+1]=str(output);argv+=['--cpu-preparation-probe']
        env={'PATH':'/usr/bin:/bin',**row['environment']}
        with compiler_turn(),(P/f'evidence/preparation-{revision}-{kind}.log').open('w') as log:
            # Sparse virtual extents exceed physical RAM by design; record RSS.
            trace=P/f'evidence/preparation-{revision}-{kind}.strace'
            cp=subprocess.run(['/usr/bin/strace','-f','-e','trace=openat,ioctl','-o',str(trace),*argv],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
        assert cp.returncode==0,f'{kind} real-argv preparation failed'
        trace_text=trace.read_text()
        assert not any(x in trace_text for x in ('/dev/dri','/dev/accel','.gguf','/mnt/usb-models','/mnt/raid-models')),'CPU probe touched model/device path'
        result=json.loads((output/'preparation.json').read_text());assert result['passed']
        records.append(dict(proposal_sha256=sha(proposal),binary_sha256=sha(argv[0]),real_argv=row['native_argv'],probe_argv=argv,result=result,syscall_trace=str(trace.relative_to(P)),syscall_trace_sha256=sha(trace),no_model_or_device_open=True))
        print(kind,'actual device-binary CPU preparation PASS',flush=True)
    rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024;assert rss<4*1024**3
    save(P/'evidence/preparation.json',dict(passed=True,device_executed=False,max_rss_bytes=rss,records=records))
if __name__=='__main__':main()
