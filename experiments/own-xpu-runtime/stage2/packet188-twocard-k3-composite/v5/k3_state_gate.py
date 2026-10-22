"""Packet188 k3 + trims state-correctness gate (CPU only, synthetic miniature weights, no device).

The k3 storage (rank0_layers 0-26) uses the five-layer pipeline miniature G Q G G Q (mini GDN layers 2-3 =
full-model GDN layers 24-26; mini layer 4 = QSA layer 27).

Part A, engine (native/v3_state.cpp, GNU and Intel host compilers): one rank-0 miniature engine in the k3
storage; 64-step direct vs mixed hit/miss(every cancellation cut)/abandoned-redo/no-guess sequence compared on
the canonical bytes of every rank-0 allocation, guard refusals, decode-token verification, and a negative
control (advancing the moved layers on a guessed token is detected). Selections: v3k (boundary rank0: layer 3
idle on rank 0), k3, k3kio, k3prep, k3trims (static snapshot) and k3p/k3trimsp (production snapshot). The
canonical transcripts of k3/k3kio/k3prep/k3trims must be byte-identical (the trims move no byte), as must
k3p/k3trimsp; every run must agree across compilers; the trim counters prove each trim actually ran.

Part B, two-rank pipeline (the packet188 gnu-host own-rt-iq3, the real native controllers run/run_v3, the real
bracket switch op 13, the vendored packet56 transport): a fresh production-layout reference (five-layer
miniature, --pipeline-mini5), then one-load miniature brackets in BOTH start orders (V3/k3+trims/V3/k3+trims/V3
and k3+trims/V3/...), an attribution load k3/k3kio/k3prep/k3trims and a draft-suppression load; each view runs
four requests (MTP draft, scripted hit/miss/no-guess mix, no draft, EOS). Every request must equal the
reference request: tokens, all 120 per-step per-layer stream fixtures (merged over ranks), draft proposals,
draft final state and every per-layer target state buffer (owner rank by layout). Boundary views issue one
boundary per rank-0 accept; rank 1 never runs a layer its view moved to rank 0.
"""
import gzip,hashlib,json,os,resource,subprocess,sys,time
from pathlib import Path
from unittest.mock import patch
from p188_v5_build_engine import P,LOCAL,ROOT,B,CHECKED,sha,save,limits,run

OUT=B/'k3-state'
P56=LOCAL/'lineage-inputs/vendor/repo/experiments/own-xpu-runtime/stage2/packet56-draft-prefix'
BINARY=B/'gnu-host/own-rt-iq3'
INTEL='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
PROMPT=[2,5,3,7,1]


K3={'k3','k3kio','k3prep','k3trims','k3p','k3trimsp'}
TRIMS={'v3k':('copy','sync'),'k3':('copy','sync'),'k3kio':('kernel','sync'),'k3prep':('copy','async'),'k3trims':('kernel','async'),
       'k3p':('copy','sync'),'k3trimsp':('kernel','async')}


def selections():
    """Miniature-admissible record-line choices (experts/head production: the mini engine has no
    halfcache layout and no split head) plus the packet188 keys; written under build/, hashed."""
    base=json.loads((P/'lineage/v3/selection.json').read_text())
    choices={k:v for k,v in base['choices'].items() if k not in ('rank0_layers','boundary')}
    choices.update(experts='production',head='production')
    k3=lambda boundary,io,prep,snap='static':dict(rank0_layers='0-26',boundary=boundary,kernel_io=io,rank0_prepare=prep,snapshot_host=snap)
    rows={'production':{},'v3k':k3('rank0','copy','sync'),'k3':k3('rank0-k3','copy','sync'),'k3kio':k3('rank0-k3','kernel','sync'),
          'k3prep':k3('rank0-k3','copy','async'),'k3trims':k3('rank0-k3','kernel','async'),
          'k3p':k3('rank0-k3','copy','sync','production'),'k3trimsp':k3('rank0-k3','kernel','async','production')}
    out={}
    for name,extra in rows.items():
        path=OUT/'selections'/(name+'.json');path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(dict(base,choices=dict(choices,**extra)),indent=2)+'\n');out[name]=(path,sha(path))
    return out


def engine_part(sel):
    prior=json.loads((P/'engine-commands.json').read_text())
    args=list(next(r['command'] for r in prior if r['name']=='gnu-host-entry-main'));args=args[1:args.index('-o')];i=args.index('-c');del args[i:i+2]
    rows=[]
    for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel',INTEL)]:
        obj=OUT/(compiler+'.o');binary=OUT/('engine-'+compiler)
        # icpx spells the same OpenMP option -qopenmp (otherwise a driver recommendation warning).
        spell=(lambda xs:['-qopenmp' if x=='-fopenmp' else x for x in xs]) if compiler=='Intel' else (lambda xs:xs)
        run([cxx,*spell(args),'-c',P/'native/v3_state.cpp','-o',obj],'v3-state-'+compiler+'-compile')
        link=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'))
        link=[str(obj) if x.endswith('/entry-main.o') else x for x in link if not x.endswith('own-rt-iq3-entry.cpp.o')]
        link=spell(link);link[0]=cxx;link[link.index('-o')+1]=str(binary)
        if compiler=='Intel':link+=['-no-pie','-Wl,-rpath,/opt/intel/oneapi/compiler/2026.0/lib']
        run(link,'v3-state-'+compiler+'-link')
        for mode in ('v3k','k3','k3kio','k3prep','k3trims','k3p','k3trimsp'):
            path,digest=sel[mode];dest=OUT/f'engine-{compiler}-{mode}'
            if dest.exists():dest.rename(dest.with_name(dest.name+'-old-'+str(time.time_ns())))
            dest.mkdir()
            env=dict(os.environ,OMP_NUM_THREADS='2',LD_LIBRARY_PATH='/opt/intel/oneapi/compiler/2026.0/lib')
            log=P/'evidence'/f'k3-state-engine-{compiler}-{mode}.log'
            with log.open('w') as stream:
                r=subprocess.run([sys.executable,'-B',str(P/'k3_state_gate.py'),'--worker',str(binary),str(path),digest,str(dest)],env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,timeout=900)
            assert r.returncode==0,log.read_text()[-4000:]
            result=json.loads((dest/'result.json').read_text())
            archive=P/'evidence'/f'k3-state-engine-{compiler}-{mode}.txt.gz';archive.write_bytes(gzip.compress((dest/'cases.txt').read_bytes(),mtime=0))
            result.update(compiler=compiler,selection=mode,binary_sha256=sha(binary),transcript_sha256=sha(archive),snapshot=json.loads((dest/'speculative-snapshot.json').read_text()))
            assert result['passed'] and result['cases']>=65 and result['refusals']>=8 and result['negatives']==2
            io,prep=TRIMS[mode]
            assert (result['kernel_io'],result['rank0_prepare'])==(io,prep),result
            assert (result['kio_sync_transfers']>0)==(io=='kernel') and (result['staged_halves']>0)==(prep=='async'),('trim counters',mode,result)
            assert result['moved_sites']>0 and result['stored_sites']>result['moved_sites'] if mode=='v3k' else result['stored_sites']==result['moved_sites'],('k3 sites',mode,result)
            result.pop('transcript',None);result['transcript_bytes']=archive.stat().st_size
            rows.append(result);print('engine',compiler,mode,'PASS',result['cases'],'cases',result['refusals'],'refusals',flush=True)
    for mode in TRIMS:
        assert len({r['canonical_sha256'] for r in rows if r['selection']==mode})==1,'compilers differ: '+mode
    canon=lambda mode:next(r['canonical_sha256'] for r in rows if r['selection']==mode)
    assert len({canon(m) for m in ('k3','k3kio','k3prep','k3trims')})==1,'a trim changed engine state bytes (static snapshot)'
    assert canon('k3p')==canon('k3trimsp'),'a trim changed engine state bytes (production snapshot)'
    assert canon('v3k')!=canon('k3'),'the k3 boundary must change which rank-0 layer state evolves'
    return rows


# ------------------------------------------------------------------ part B: two-rank pipeline
def pipeline_module():
    if str(P56) not in sys.path:sys.path.insert(0,str(P56))
    import pipeline
    return pipeline


def h(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Load:
    def __init__(self,pipeline,sel,first,out,fault='none'):
        self.pl=pipeline;self.sel=sel;self.out=out
        path,digest=sel[first];real=pipeline.subprocess.Popen
        def popen(cmd,*a,**k):
            cmd=list(cmd);assert '--mini' in cmd and '--selection' not in cmd
            return real(cmd+['--selection',str(path),'--selection-sha256',digest,'--pipeline-mini5'],*a,**k) # packet188: five-layer miniature for every load
        args=pipeline.parser().parse_args(['--binary',str(BINARY),'--output',str(out),'--mini','--context','256','--tokens','24',
            '--seconds','600','--wait-seconds','300','--native-nice','19','--draft','mtp','--draft-rank','1','--target-split','0',
            '--draft-fault',fault,'--controller','native','--timing','token','--retain-steps','1-24'])
        args.host_memory='resident';out.mkdir(parents=True)
        with patch.object(pipeline.subprocess,'Popen',popen):
            self.t=pipeline.Transport(args,out,{'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'})
        self.args=args;self.current=None;self.view=first
    def _clear(self,dest):
        t=self.t;t.request_output=dest;t.mapping[:]=bytes(len(t.mapping));t.trace=[]
        t.metrics=[dict(busy_ms=0.,handover_ms=0.,calls=0,gpu_ms=0.) for _ in range(2)];t.last_complete=[0.,0.]
    def switch(self,name,dest):
        """Bracket switch + total reset (op 13) on both ranks, as v5/bracket.py does."""
        path,digest=self.sel[name];t=self.t;dest.mkdir(parents=True)
        for rank in (0,1):
            meta=t.out/f'rank{rank}'/f'bracket-{t.seq[rank]+1}.txt';reset=meta.with_suffix('.reset.txt')
            receipt=dest/f'boundary-rank{rank}.json';reset.write_text(str(dest/f'rank{rank}')+'\n\n')
            meta.write_text('\n'.join([str(path),digest,str(reset),str(receipt)])+'\n');t.call(rank,13)
            proof=json.loads(receipt.read_text());assert proof['passed'] and proof['total_reset'] and proof['selection_sha256']==digest
        self._clear(dest);self.view=name
    def reset(self,dest):
        t=self.t;dest.mkdir(parents=True)
        for rank in (0,1):
            meta=t.out/f'rank{rank}'/f'reset-{t.seq[rank]+1}.txt';meta.write_text(str(dest/f'rank{rank}')+'\n\n');t.call(rank,11)
        self._clear(dest)
    def request(self,scenario):
        pl=self.pl;mode,guesses,eos={'mtp':('mtp',[],()),'script':('script',SCRIPT,()),'none':('none',[],()),'eos':('script',[1]*30,(1,))}[scenario]
        result=pl.request_run(self.t,pl.Draft(mode,guesses),PROMPT,24,eos,True,False)
        for rank in (0,1):self.t.call(rank,4,position=2147483647)
        return result
    def close(self):self.t.close(True)


SCRIPT=[1,3,1,-1,1,1,3,3,1,-1,1,3,1,1,1,-1,3,1,1,1,3,1,-1,1,1,1,1,1,1,1]  # hit/miss/no-guess mix (mini target emits 1)
SCENARIOS=('mtp','script','none','eos')


def identity(dest,result,view):
    fixtures={}
    for rank in (0,1):
        for f in (dest/f'rank{rank}').glob('step*/layer-*.bf16'):
            key=f.parent.name+'/'+f.name;assert key not in fixtures,'fixture produced by both ranks: '+key;fixtures[key]=h(f)
    moved={'production':(),'v3k':(2,)}.get(view,(2,3)) # mini layers run by rank 0's boundary in this view
    state={}
    for rank in (0,1):
        for f in (dest/f'rank{rank}/state-2147483647').glob('*.bin'):
            name=f.stem
            if name.startswith('blk.'):
                layer=int(name.split('.')[1]);owner=0 if layer<2 else (0 if layer in moved else 1)
                if owner==rank:state[name]=h(f)
            elif name.startswith('alternate-blk.') and rank==0:state[name]=h(f)
            elif rank==1 and (name.startswith('final.') or name in ('logits','next_token')):state[name]=h(f)
    rows=[json.loads(x) for x in (dest/'rank1/draft-rows.jsonl').read_text().splitlines() if x.strip()] if (dest/'rank1/draft-rows.jsonl').exists() else []
    trace=result['rank_trace'];boundaries=sum(1 for x in trace if x['rank']==0 and x['op']==15)
    accepts=sum(1 for x in trace if x['rank']==0 and x['op']==2)
    rank1_layers=sorted({f.name for f in (dest/'rank1').glob('step*/layer-*.bf16')})
    return dict(tokens=result['tokens'],stats={k:result['stats'][k] for k in ('guesses','hits','misses','no_guess')},fixtures=fixtures,state=state,
                proposals=[(r.get('draft_position'),r.get('confirmed_token'),r.get('guess')) for r in rows],
                boundaries=boundaries,accepts=accepts,rank1_layers=rank1_layers,moved=list(moved))


def draft_state(dest):
    d=dest/'rank1/draft-final-state'
    return {str(f.relative_to(d)):h(f) for f in d.rglob('*') if f.is_file()} if d.exists() else {}


def pipeline_part(sel):
    pl=pipeline_module();stamp=str(time.time_ns());root=OUT/('pipeline-'+stamp)
    plans=[('reference','production',['production'],'none'),
           ('bracket-v3k-first','v3k',['v3k','k3trims','v3k','k3trims','v3k'],'none'),
           ('bracket-k3trims-first','k3trims',['k3trims','v3k','k3trims','v3k','k3trims'],'none'),
           ('trims-attribution','k3',['k3','k3kio','k3prep','k3trims'],'none'),
           ('production-snapshot','k3p',['k3p','k3trimsp'],'none'),
           ('suppress','v3k',['v3k','k3trims'],'suppress')]
    loads={};reference=None
    for label,first,views,fault in plans:
        load=Load(pl,sel,first,root/label/'load',fault);rows=[]
        try:
            for index,view in enumerate(views):
                vdir=root/label/f'view{index}-{view}'
                load.switch(view,vdir/'switch')
                for scenario in (SCENARIOS if fault=='none' else ('mtp',)):
                    dest=vdir/scenario;load.reset(dest);result=load.request(scenario)
                    rows.append(dict(view=view,index=index,scenario=scenario,dest=dest,identity=identity(dest,result,view)))
            load.reset(root/label/'tail')
        finally:load.close()
        for row in rows:row['identity']['draft_state']=draft_state(row['dest'])
        loads[label]=rows;print('pipeline',label,'ran',len(rows),'requests',flush=True)
    ref={r['scenario']:r['identity'] for r in loads['reference']}
    supp_ref=None;summary=[]
    for label,rows in loads.items():
        for r in rows:
            i=r['identity'];expected=ref[r['scenario']] if label!='suppress' else (supp_ref:=supp_ref or i)
            for key in ('tokens','fixtures','state','proposals','draft_state'):
                assert i[key]==expected[key],f'{label} view{r["index"]}-{r["view"]} {r["scenario"]}: {key} differs from the reference'
            assert i['stats']==expected['stats'],f'{label} {r["scenario"]}: acceptance differs'
            boundary=r['view']!='production'
            assert (i['boundaries']==i['accepts'] if boundary else i['boundaries']==0),f'{label} {r["view"]} {r["scenario"]}: boundary count {i["boundaries"]} vs accepts {i["accepts"]}'
            assert not any(f'layer-{m:02d}.bf16' in i['rank1_layers'] for m in i['moved']),f'{label} {r["view"]}: rank 1 ran a moved layer'
            assert len(i['fixtures'])==(120 if r['scenario']!='eos' else len(i['fixtures'])) and i['state'],'fixture/state census'
            summary.append(dict(load=label,view=r['view'],index=r['index'],scenario=r['scenario'],tokens=len(i['tokens']),
                                fixtures=len(i['fixtures']),state_buffers=len(i['state']),stats=i['stats'],boundaries=i['boundaries'],accepts=i['accepts']))
    hits=sum(s['stats']['hits'] for s in summary);misses=sum(s['stats']['misses'] for s in summary);no_guess=sum(s['stats']['no_guess'] for s in summary)
    assert hits and misses and no_guess,'scenario mix must contain hits, misses and no-guess steps'
    return dict(root=str(root.relative_to(ROOT)),requests=len(summary),hits=hits,misses=misses,no_guess=no_guess,rows=summary,
                reference_scenarios={k:dict(tokens=len(v['tokens']),stats=v['stats']) for k,v in ref.items()})


def main():
    limits();OUT.mkdir(parents=True,exist_ok=True);sel=selections()
    engine=engine_part(sel)
    os.environ['OMP_NUM_THREADS']='2'
    pipe=pipeline_part(sel)
    save(P/'evidence/k3-state.json',dict(passed=True,device_executed=False,model_read=False,full_shape_read=False,
        selections={k:dict(path=str(v[0].relative_to(ROOT)),sha256=v[1]) for k,v in sel.items()},
        engine_runs=engine,pipeline=pipe,
        scope='k3 moved-layer state correctness (GDN layers 24-26 = mini 2-3) and trim byte-identity: engine-level direct vs '
              'speculative sequences with every cancellation cut, redo/fallback, guard refusals and a detecting negative control '
              'for V3 and k3 views and every kernel_io x rank0_prepare combination (identical canonical transcripts); two-rank '
              'miniature one-load brackets in both start orders plus an attribution load against a fresh five-layer '
              'production-layout reference (tokens, 120 fixtures, proposals, draft and target state)',
        sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'k3_state_gate.py',P/'native/v3_state.cpp',P/'native/v3_boundary.hpp',P/'native/engine_bracket.hpp',
                 P/'native/kernel_io.hpp',P/'native/bracket_boundary.hpp',P/'native-src/rank.hpp',P/'native-src/main.cpp',P/'native-src/mtp.hpp',
                 P/'native-src/strict_snapshot.hpp',BINARY)}))
    # Raw miniature request trees are scratch: the identities above are the retained evidence.
    import shutil;shutil.rmtree(ROOT/pipe['root'])
    for leftover in OUT.glob('engine-*-*'):
        if leftover.is_dir():shutil.rmtree(leftover)
    limits()


if __name__=='__main__':
    if '--worker' in sys.argv:
        resource.setrlimit(resource.RLIMIT_AS,(1280*1024**2,1280*1024**2));os.execv(sys.argv[2],sys.argv[2:])
    else:
        resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
