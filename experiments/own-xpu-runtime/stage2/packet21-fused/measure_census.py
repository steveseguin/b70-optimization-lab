"""Real CPU executions measure submissions; no performance claims."""
import collections,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 available=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
 assert available>70*1024**3
 root=B/f'census-{time.time_ns()}';root.mkdir();inputs=root/'inputs';inputs.mkdir();(inputs/'tokens.txt').write_text((B/'input/tokens.txt').read_text().split()[0]+'\n');shutil.copyfile(B/'input/vocab.bin',inputs/'vocab.bin')
 binary=B/'host/own-rt-iq3';elf=subprocess.check_output(['readelf','-d',str(binary)],text=True);assert not any(v in elf.lower() for v in ('libsycl','libze_loader','libur_loader','libopencl'))
 model=json.loads((B/'input/input.json').read_text())['model_dir'];rows={};reference=None
 for gemv in ('frozen','r5'):
  for fusion in ('off','on'):
   label=gemv+'-'+fusion;out=root/label;args=[str(binary),'--checked','--cards','2','--card','0','--memory','resident','--context','256','--gemv',gemv,'--fusion',fusion,'--max-new','1','--input',str(inputs/'tokens.txt'),'--output',str(out),'--model-dir',model,'--plan',str(B/'input/plan.tsv'),'--identity',str(B/'input/identity.tsv')]
   with (root/(label+'.log')).open('w') as log:subprocess.run(args,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=10800)
   receipt=json.loads((out/'receipt.json').read_text());assert receipt['passed'] and not receipt['device_executed']
   timing=json.loads((out/'timings.jsonl').read_text().strip());sites=[json.loads(x) for x in (out/'sites.jsonl').read_text().splitlines()];layers=collections.Counter()
   for s in sites:layers[s['label'].split('.')[1] if s['label'].startswith('blk.') else 'head-control']+=s['kernel_submissions']
   assert sum(layers.values())==timing['kernel_submissions']
   hashes={x.name:sha(x) for x in (out/'step1').glob('layer-*.bf16')};identity=(hashes,receipt['tokens'])
   if reference is None:reference=identity
   assert identity==reference
   census=json.loads((out/'census.json').read_text());descriptors=collections.Counter()
   for owner in census:
    for allocation in owner['allocations']:
     if 'batch-table:' in allocation['label']:descriptors[allocation['label'].split(':')[0]]+=allocation['bytes']
   assert all(n<1048576 for n in descriptors.values())
   rows[label]=dict(fusion=fusion,gemv=gemv,binary_sha256=sha(binary),device_executed=False,measured_cpu_submissions=True,launches=timing['kernel_submissions'],per_layer=dict(layers),sites=[dict(label=s['label'],launches=s['kernel_submissions']) for s in sites],timing=timing,fixture_hashes=hashes,tokens=receipt['tokens'],allocation_census=census,descriptor_bytes_per_card=dict(descriptors),argv=args)
   print(label,timing['kernel_submissions'],'PASS',flush=True)
 result=dict(passed=True,device_executed=False,rows=rows,limit='CPU compute submissions, not device timing; --checked adds waits but no kernels')
 (P/'launch-census-measured.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
