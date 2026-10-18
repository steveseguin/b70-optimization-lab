"""Extract unchanged packet107 harness logits on CPU; no GPU construction."""
import json, os, shlex, subprocess, time
from build_engine import P, B, ROOT, limits, sha, save
from compile_turn import turn
def main():
    limits(); B.mkdir(exist_ok=True)
    parent=P.parent/'packet107-specialised-layers'
    receipt=json.loads((parent/'evidence/build-gnu-host.json').read_text())
    source=next((parent/'build/checked').rglob('layer_bench.cpp'))
    original=source.read_text()
    prefix=original[:original.index('int main(int argc,char**argv)')]
    generated=B/'capture.cpp'
    generated.write_text(prefix+'\n'+(P/'capture_main.inc').read_text())
    compile=list(receipt['commands'][1]);compile[compile.index('-o')+1]=str(B/'capture.o');compile[-1]=str(generated)
    compile+=['-MMD','-MF',str(B/'capture.d')]
    link=[str(B/'capture.o') if x==str(parent/'build/gnu-host/layer.o') else x for x in receipt['commands'][2]]
    link[link.index('-o')+1]=str(B/'capture')
    for label,cmd in [('compile',compile),('link',link)]:
        with turn(),(B/('capture-'+label+'.log')).open('w') as log:
            subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
    dependencies=shlex.split((B/'capture.d').read_text().replace('\\\n',' ').split(':',1)[1])
    sources={str(q.relative_to(ROOT)):sha(q) for x in dependencies if (q:=__import__('pathlib').Path(x).resolve()).is_relative_to(ROOT)}
    for q in [source,parent/'selection.json',parent/'dispatch-speed6.json',P/'capture_main.inc',P/'capture_inputs.py']:
        sources[str(q.relative_to(ROOT))]=sha(q)
    objects={str(__import__('pathlib').Path(x).relative_to(ROOT)):sha(x) for x in link if x.endswith('.o')}
    out=P/'evidence/capture';assert not out.exists()
    started=time.monotonic()
    with (P/'evidence/capture.log').open('x') as log:
        subprocess.run([str(B/'capture'),str(out)],env=dict(os.environ,OMP_NUM_THREADS='2'),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
    assert (out/'harness-logits.bin').stat().st_size==16*512*4
    save(P/'evidence/input-capture.json',dict(passed=True,device_executed=False,synthetic_layer=True,rows=16,sources=sources,objects=objects,commands=[compile,link],binary_sha256=sha(B/'capture'),input_sha256=sha(out/'harness-logits.bin'),metadata_sha256=sha(out/'harness-logits.jsonl'),wall_seconds=time.monotonic()-started))
    print('16 packet107 CPU harness rows captured; no device execution',flush=True)
if __name__=='__main__': main()
