"""CPU-only replay of packet58amc checks; no compile, model read or queue mutation."""
import json,pathlib,subprocess,resource,tempfile,hashlib
P=pathlib.Path(__file__).resolve().parent;E=P/'evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def limit():resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
rows=[]
for compiler in ('GNU','Intel'):
 for gate in ('demand-bytes','ownership'):
  binary=P/'build'/f'{compiler}-{gate}'
  for repeat in range(2):
   with tempfile.TemporaryDirectory(prefix='p58amc-fixture-') as tmp:
    cmd=[str(binary)]+([tmp] if gate=='demand-bytes' else [])
    log=E/f'p58amc-{compiler}-{gate}-{repeat}.log'
    with log.open('w') as f:cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,preexec_fn=limit)
    row=dict(compiler=compiler,gate=gate,repeat=repeat,passed=cp.returncode==0,binary_sha256=sha(binary),log_sha256=sha(log))
    if gate=='demand-bytes' and row['passed']:
     a=pathlib.Path(tmp)/'expected.bin';b=pathlib.Path(tmp)/'actual.bin';row.update(bytes=a.stat().st_size,exact=sha(a)==sha(b),output_sha256=sha(a));assert row['exact']
    rows.append(row);print(compiler,gate,repeat,cp.returncode,flush=True)
rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024;assert rss<=2*1024**3
(E/'p58amc-final-fixtures.json').write_text(json.dumps(dict(passed=all(r['passed'] for r in rows),records=rows,device_executed=False,compilation_performed=False,max_rss_bytes=rss),indent=2)+'\n')
