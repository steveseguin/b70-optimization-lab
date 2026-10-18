"""Run the frozen K1 arithmetic fixture on CPU, never its device executable."""
import json,resource,subprocess,tempfile
from pathlib import Path
from build_engine import P,ROOT,BASE,save,sha,limits

def main():
    limits();binary=P/'build/gnu-host/p58-cache-fixtures'
    with tempfile.TemporaryDirectory(prefix='k1-cpu-',dir=P/'build') as d:
        output=Path(d)/'run'
        r=subprocess.run([str(binary),'--down-layout','down-tile16','--iterations','2','--output',str(output)],
                         stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
        assert r.returncode==0,r.stderr
        row=json.loads((output/'k1.json').read_text());assert row['passed'] and not row['device_executed']
        assert all(row[k] for k in ('zero_copy_bytes_equal','mixed_bytes_equal','streamed_bytes_equal'))
        cases=(output/'k1-cases.jsonl').read_text();(P/'evidence/k1-async-cases.jsonl').write_text(cases)
        save(P/'evidence/k1-async-cpu.json',dict(passed=True,device_executed=False,native=row,
            binary_sha256=sha(binary),arithmetic_unchanged=True,
            actual_async_protocol_byte_gate='protocol-gates.json',
            peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024,
            sources={str((BASE/'build/gnu-host/p58-cache-fixtures').relative_to(ROOT)):sha(binary)}))
    print('K1 full-shape zero-copy/mixed/streamed byte equality PASS')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
