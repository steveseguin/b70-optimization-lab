"""CPU host-only checkpoint v3 gate (packet181: qualified-one-card label, v1.2+p180 read
compatibility, prefill/append path record; every packet180 case kept).

Compiles this packet's patched entry TU (native-source .../build/native/main.cpp +
checkpoint.hpp v3 via entry-main.cpp) with -DOWN_RT_HOST_ONLY and relinks packet58aj's
qualified gnu-host object set from dereferenced in-packet copies (build/gnu-host-ancestor,
each asserted equal to packet58aj's build-receipt pin), exactly as packet179/packet180's probe
did. Runs --mini --pipeline-mini synthetic sessions on the real CPU arithmetic path:

  A. packet179 round trip (save K=8, two same-generation resumes M=4, merged == reference) with
     the v1.2+p181 manifest (label qualified-one-card, qualified_by) and the prefill record;
  B. append + restore-then-save + chain (packet180's case) plus append-span variants: a 1-token
     delta, a 28-token delta crossing the 32-position split boundary, and a restore point that
     is not a multiple of 4 (N=13) followed by a 25-token delta; every append == a fresh
     one-shot reference of the same input; the repeat append and a FRESH save of the same
     history hold byte-identical state blobs; append with an empty delta == the resume. There
     is no chunked prefill in this engine: every case records path "incremental";
  C. inspect (full and metadata-only, one JSON object on stdout, JSON lines on stderr;
     metadata mode with every blob unreadable still passes, full mode refuses);
  D. every packet180 refusal (26 refusal/boundary cases incl. lock), each before the first
     device upload, labelled before/after the model load;
  E. validated delete (wrong targets refused without creating a lock, incl. an unknown label)
     and a real concurrent delete-vs-restore (host-only hold hook; delete reports in_use);
  G. label compatibility: a v1.2+p180 "experimental" manifest (this probe's checkpoint converted)
     is accepted for same-generation resume, append and restore-then-save (whose new checkpoint
     is v1.2+p181 qualified-one-card), inspect and delete; it is refused only by an identity
     check (binary mismatch -> engine identity); label/contract pairing and qualified_by edits
     are refused as malformed manifests;
  F. production shape: (1) packet179's real device gate checkpoint (128 blobs, N=342) converted
     to v1.2+p180 "experimental" and to v1.2+p181 "qualified-one-card" passes this C++ reader
     (metadata + full inspect, real control-blob semantics), a TSV tamper is refused, the
     scratch copies are removed by the delete tool; (2) packet180's REAL device checkpoints S1
     and S2 (v1.2+p180, label experimental, written by the packet180 engine on device) pass
     metadata + full inspect VERBATIM (their device-rendered fields.tsv equals this reader's
     rendering) and the delete tool; S1 also passes this engine's whole pre-load restore
     precheck with the real 469-token NEW input (the mini probe then stops at its own
     token-range check; on device the engine-identity check would refuse it).

No GPU, no model reads; synthetic mini evidence is not arithmetic or performance qualification.
The production-geometry gates are device rows a and b. The real device checkpoints are read
in place (packet179/packet180 evidence trees, local untracked blobs) into scratch copies that
the delete tool removes; nothing is pinned outside this packet.
"""
import fcntl,hashlib,json,os,re,resource,shutil,struct,subprocess,sys,time
from pathlib import Path
from build_engine import P,ROOT,limits,turn,sha,save
NAT='native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/build/native'
HOLD_DEADLINE_SECONDS=60  # CPU probe only: wait for the host-only hold marker of the concurrent restore
LABEL,CONTRACT='qualified-one-card','v1.2+p181'
LEGACY_LABEL,LEGACY_CONTRACT='experimental','v1.2+p180'
QUALIFIED_BY_TEXT=('{"scope":"one card (tp1-full512 profile) only; TP2 checkpoints not implemented; no ctxkeeper adapter yet",'
    '"device_gates":[{"packet":"packet179-session-swap","date":"2026-10-22","operations":["same-generation-resume"]},'
    '{"packet":"packet180-session-swap-v2","date":"2026-10-22","operations":["append","restore-then-save"]}]}')
QUALIFIED_BY=json.loads(QUALIFIED_BY_TEXT)
QUALIFIED_GATES='packet179-session-swap@2026-10-22:same-generation-resume;packet180-session-swap-v2@2026-10-22:append,restore-then-save'
OPERATIONS=['same-generation-resume','append','restore-then-save']
REAL179=ROOT/'experiments/own-xpu-runtime/stage2/packet179-session-swap/one-card/evidence/device-p179-checkpoint-A-b/run/checkpoints/gate'
REAL180=ROOT/'experiments/own-xpu-runtime/stage2/packet180-session-swap-v2/one-card/evidence/device-p180-lifecycle-A-b/run/checkpoints'

def build_probe(p):
    build=p/'build/checkpoint-probe';build.mkdir(parents=True,exist_ok=True)
    main_cpp=(p/NAT/'main.cpp').resolve();entry=(p/NAT/'entry-main.cpp').resolve();header=main_cpp.parent/'checkpoint.hpp'
    aj=ROOT/'experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident'
    binding=json.loads((aj/'evidence/build.json').read_text())
    assert sha(aj/'build/gnu-host/own-rt-iq3')==binding['artifacts']['build/gnu-host/own-rt-iq3'],'ancestor gnu-host composition drifted'
    executed={row['name']:row['command'] for row in binding['commands']}
    compile_cmd=list(executed['gnu-host-entry-main'])
    compile_cmd[compile_cmd.index('-MF')+1]=str(build/'entry-main.d')
    compile_cmd[compile_cmd.index('-o')+1]=str(build/'entry-main.o')
    compile_cmd[compile_cmd.index('-c')+1]=str(entry)
    probe=build/'checkpoint-probe'
    link_cmd=list(executed['gnu-host-own-rt-iq3'])
    link_cmd[link_cmd.index(str(aj/'build/gnu-host/entry-main.o'))]=str(build/'entry-main.o')
    link_cmd[link_cmd.index('-o')+1]=str(probe)
    pins=json.loads((aj/'build-receipt.json').read_text())['sources']
    for i,a in enumerate(link_cmd):
        if a.endswith('.o') and a!=str(build/'entry-main.o'):
            copy=p/'build/gnu-host-ancestor'/Path(a).relative_to(aj)
            if not copy.is_file():copy.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(a,copy)
            assert sha(a)==sha(copy)==pins[str(Path(a).relative_to(ROOT))],('ancestor object differs from packet58aj build-receipt',a)
            link_cmd[i]=str(copy)
    ancestor_objects={a:sha(a) for a in link_cmd if a.endswith('.o') and a!=str(build/'entry-main.o')}
    sources={str(entry):sha(entry),str(main_cpp):sha(main_cpp),str(header):sha(header)}
    previous=json.loads((build/'compiled-inputs.json').read_text()) if (build/'compiled-inputs.json').is_file() else {}
    reuse=(probe.is_file() and previous.get('binary_sha256')==sha(probe) and previous.get('compile')==compile_cmd
           and previous.get('link')==link_cmd and previous.get('sources_sha256')==sources)
    if not reuse:
        with turn(),(build/'compile.log').open('w') as log:
            limits();subprocess.run(compile_cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
        with turn(),(build/'link.log').open('w') as log:
            limits();subprocess.run(link_cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
        save(build/'compiled-inputs.json',dict(compile=compile_cmd,link=link_cmd,binary_sha256=sha(probe),
            sources_sha256=sources,ancestor_objects_sha256=ancestor_objects))
    (build/'entry-main.o').unlink(missing_ok=True)  # scratch object; the probe binary is the retained artifact
    return build,probe,compile_cmd,link_cmd,sources,ancestor_objects

def render(m,digest,text):
    """Python port of checkpoint.hpp checkpoint_render_fields for both contracts. save_seconds is
    rendered from the manifest's literal number text (the engine prints 17 significant digits)."""
    g=m['geometry'];ts=m['token_state'];lin=m['lineage'];par=lin['parent'] or {}
    rows=[('format',m['format']),('label',m['label']),('contract',m['contract'])]
    if m['contract']==CONTRACT:
        q=m['qualified_by']
        rows+=[('qualified_scope',q['scope']),('qualified_by',';'.join(g2['packet']+'@'+g2['date']+':'+','.join(g2['operations']) for g2 in q['device_gates']))]
    rows+=[('checkpoint_id',m['checkpoint_id']),('created',m['created']),
        ('operation',lin['operation']),('parent_checkpoint_id',par.get('checkpoint_id','')),('parent_manifest_sha256',par.get('manifest_sha256','')),
        ('position',ts['position']),('prompt_length',ts['prompt_length']),('length',ts['length']),('next_token',ts['next_token']),
        ('tokens_sha256',ts['tokens_sha256']),('history0',ts['token_history'][0]),('history1',ts['token_history'][1]),
        ('identity_tsv_sha256',m['model']['identity_tsv_sha256']),('binary_sha256',m['engine']['binary_sha256']),
        ('tokenizer_identity_sha256',m['tokenizer_identity']['file_sha256']),
        ('kvh',g['kvh']),('ad',g['ad']),('ih',g['ih']),('id',g['id']),('kh',g['gdn']['kh']),('vh',g['gdn']['vh']),('d',g['gdn']['d']),('qh',g['qh']),
        ('context',g['context']),('vocab',g['vocab']),('eos',g['eos']),('layers',g['layers']),
        ('qsa_layers',','.join(map(str,g['qsa_layers']))),('gdn_layers',','.join(map(str,g['gdn_layers']))),
        ('save_seconds',re.search(r'"save_seconds":(-?[0-9][0-9.eE+-]*)',text).group(1)),('save_bytes',m['measurements']['save_bytes']),('manifest_sha256',digest)]
    out=''.join(f'{k}\t{v}\n' for k,v in rows)
    out+=''.join(f"blob\t{b['name']}\t{b['bytes']}\t{b['sha256']}\t{b['slice'][1] if b['slice'] else -1}\n" for b in m['blobs'])
    return out+''.join(f"skip\t{s['name']}\t{s['rule']}\n" for s in m['skipped_buffers'])

def main():
    limits();p=P/'one-card'
    build,probe,compile_cmd,link_cmd,sources,ancestor_objects=build_probe(p)
    sys.path.insert(0,str(p))
    import native_env
    env=native_env.environment('A')
    runroot=build/'run'
    if runroot.exists():
        for f in runroot.rglob('*'):
            if f.is_file():f.chmod(0o644)
        shutil.rmtree(runroot)
    runroot.mkdir()
    results=[]
    def record(tag,argv,cp):
        results.append(dict(tag=tag,argv=[str(a) for a in argv],returncode=cp.returncode,stdout_tail=cp.stdout[-600:],stderr_tail=cp.stderr[-600:]))
    def run(tag,argv,expect=0,extra_env=None):
        argv=[str(a) for a in argv]
        cp=subprocess.run([str(probe),*argv],env=dict(env,**(extra_env or {})),stdin=subprocess.DEVNULL,capture_output=True,text=True,
            preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3)))
        record(tag,argv,cp)
        assert cp.returncode==expect,(tag,cp.returncode,cp.stdout[-400:],cp.stderr[-600:])
        return cp
    load=lambda d:json.loads((runroot/d/'result.json').read_text())
    def write_tokens(name,tokens):
        f=runroot/name;f.write_text(' '.join(map(str,tokens))+'\n');return f
    base=['--mini','--pipeline-mini','--context','64','--retain-steps','none']
    ck=runroot/'ck'
    tid=runroot/'tokenizer-identity.tsv'
    tid.write_text('# synthetic CPU-probe identity\nformat\townrt.tokenizer-identity.v1\n'
        'gguf_header_sha256\t'+'1'*64+'\ntokenizer_source_sha256\t'+'2'*64+'\nvocab_bin_sha256\t'+'3'*64+'\n')
    tid_bad=runroot/'tokenizer-identity-other.tsv'
    tid_bad.write_text(tid.read_text().replace('1'*64,'4'*64))
    T=['--tokenizer-identity',tid]
    prompt=[2,5,3,7,1];pfile=write_tokens('p.txt',prompt)
    K,M=8,4;M1,M2,M3=4,4,4
    upload_marker='"event":"checkpoint-upload-begin"'
    def prefill_record(res,path,first,tokens):
        pf=res['checkpoint']['prefill']
        assert pf['path']==path and pf['first_position']==first and pf['tokens']==tokens and pf['ms']==res['prefill_ms'],(pf,path,first,tokens,res['prefill_ms'])
        return pf

    # ---------------- A. packet179 round trip (same-generation resume), v1.2+p181 manifest
    run('reference',base+['--max-new',K+M,'--output',runroot/'ref','--input',pfile])
    run('save',base+['--max-new',K,'--output',runroot/'save','--input',pfile,'--checkpoint-save',ck,'--checkpoint-id','gate',*T])
    r1cp=run('restore1',base+['--max-new',M,'--output',runroot/'restore1','--input',pfile,'--checkpoint-restore',ck,'--checkpoint-id','gate',*T])
    run('restore2',base+['--max-new',M,'--output',runroot/'restore2','--input',pfile,'--checkpoint-restore',ck,'--checkpoint-id','gate',*T])
    ref,sv,r1,r2=load('ref'),load('save'),load('restore1'),load('restore2')
    assert len(ref['tokens'])==K+M and len(sv['tokens'])==K,'synthetic mini stream hit EOS; adjust K/M'
    assert len(r1['tokens'])==M and r1['tokens']==r2['tokens'],'repeat restore determinism'
    assert sv['tokens']+r1['tokens']==ref['tokens'],'merged checkpoint stream != uninterrupted reference (CPU real arithmetic)'
    assert upload_marker in r1cp.stderr
    assert isinstance(r1.get('checkpoint_restore_ms'),(int,float)) and r1['checkpoint_restore_ms']>=0
    assert r1.get('prefill_ms')==0 and sv.get('checkpoint_restore_ms') is None
    N=len(prompt)+K-1
    c=r1['checkpoint'];rr=c['restore']
    assert c['operations']==['same-generation-resume'] and c['save'] is None and c['contract']==CONTRACT and c['label']==LABEL
    assert rr['operation']=='same-generation-resume' and rr['saved_prefix_length']==N and rr['saved_history_length']==N+1
    assert rr['appended_length']==0 and rr['append_prefill_ms'] is None and rr['pending_token']==sv['tokens'][-1] and rr['input_length']==len(prompt)
    assert rr['append_prefill_tokens']==0 and rr['append_prefill_path'] is None
    prefill_record(r1,None,N,0)
    prefill_record(ref,'incremental',0,len(prompt));prefill_record(sv,'incremental',0,len(prompt))
    assert ref['checkpoint']['restore'] is None and ref['checkpoint']['save'] is None and ref['checkpoint']['label']==LABEL
    assert sv['checkpoint']['operations']==['save'] and sv['checkpoint']['save']['position']==N and sv['checkpoint']['save']['parent_checkpoint_id'] is None
    gate=ck/'gate';manifest=json.loads((gate/'manifest.json').read_text())
    assert manifest['format']=='ownrt.session-checkpoint.v1' and manifest['label']==LABEL and manifest['contract']==CONTRACT
    assert manifest['qualified_by']==QUALIFIED_BY and ('"qualified_by":'+QUALIFIED_BY_TEXT+',') in (gate/'manifest.json').read_text()
    assert list(manifest)[:5]==['format','label','contract','qualified_by','operations']
    assert manifest['operations']==OPERATIONS and manifest['engine']['packet']=='packet181-session-swap-v3'
    assert manifest['lineage']=={'operation':'save','parent':None}
    assert manifest['tokenizer_identity']['file_sha256']==sha(tid) and manifest['tokenizer_identity']['gguf_header_sha256']=='1'*64
    ts=manifest['token_state'];assert ts['position']==N==ts['length'] and ts['prompt_length']==len(prompt) and ts['next_token']==sv['tokens'][-1]
    token_bytes=(gate/'tokens.bin').read_bytes()
    assert len(token_bytes)==N*4 and hashlib.sha256(token_bytes).hexdigest()==ts['tokens_sha256']
    tokens=list(struct.unpack('<%di'%N,token_bytes));assert tokens==prompt+sv['tokens'][:-1]
    assert ts['token_history']==[tokens[-2],tokens[-1]]
    g=manifest['geometry'];assert g['context']==64 and g['qsa_layers']==[1,3] and g['gdn_layers']==[0,2] and 'qh' in g
    expected_files={'manifest.json','fields.tsv','tokens.bin',*(b['name']+'.bin' for b in manifest['blobs'])}
    assert {f.name for f in gate.iterdir()}==expected_files,'closed file set'
    assert (ck/'gate.lock').is_file() and not (gate/'restore.lock').exists(),'sibling lock outside the checkpoint directory'
    small={}
    for b in manifest['blobs']:
        data=(gate/(b['name']+'.bin')).read_bytes()
        assert len(data)==b['bytes'] and hashlib.sha256(data).hexdigest()==b['sha256'],b['name']
        if len(data)<=16:small[b['name']]=data
        name=b['name']
        if name.endswith('.qsa.keys') or name.endswith('.qsa.values'):assert b['slice']==[0,N] and b['bytes']==N*1*4*2,name
        elif name.endswith('.qsa.raw'):assert b['slice']==[0,N] and b['bytes']==N*4*2,name
        elif name.endswith('.qsa.pooled'):assert b['slice']==[0,N//4] and b['bytes']==(N//4)*4*2,name
        else:assert b['slice'] is None,name
    assert struct.unpack('<i',small['position'])[0]==N and struct.unpack('<i',small['next_token'])[0]==ts['next_token']
    assert struct.unpack('<i',small['token'])[0]==tokens[-1] and list(struct.unpack('<2q',small['token_history']))==ts['token_history']
    fields=(gate/'fields.tsv').read_text()
    assert ('\nmanifest_sha256\t'+sha(gate/'manifest.json')+'\n') in fields and '\nhistory0\t' in fields
    assert fields==render(manifest,sha(gate/'manifest.json'),(gate/'manifest.json').read_text()),'Python render port != C++ fields.tsv (v1.2+p181)'
    assert ('\nlabel\t'+LABEL+'\n') in fields and ('\nqualified_by\t'+QUALIFIED_GATES+'\n') in fields

    # ---------------- B. append, restore-then-save, chain, repeat, fresh-save state equivalence, span variants
    turn_tokens=[4,6,9,2,8,3]
    new=prompt+sv['tokens']+turn_tokens;newfile=write_tokens('new.txt',new)
    run('reference-new',base+['--max-new',M1+M2+M3,'--output',runroot/'ref-new','--input',newfile])
    run('append-s2',base+['--max-new',M1,'--output',runroot/'append-s2','--input',newfile,'--checkpoint-restore',ck,'--checkpoint-id','gate',
        '--checkpoint-save',ck,'--checkpoint-save-id','s2',*T])
    run('append-s2b',base+['--max-new',M1,'--output',runroot/'append-s2b','--input',newfile,'--checkpoint-restore',ck,'--checkpoint-id','gate',
        '--checkpoint-save',ck,'--checkpoint-save-id','s2b',*T])
    run('fresh-s2ref',base+['--max-new',M1,'--output',runroot/'fresh-s2ref','--input',newfile,'--checkpoint-save',ck,'--checkpoint-id','s2ref',*T])
    run('resume-s2-save-s3',base+['--max-new',M2,'--output',runroot/'resume-s2','--input',newfile,'--checkpoint-restore',ck,'--checkpoint-id','s2',
        '--checkpoint-save',ck,'--checkpoint-save-id','s3',*T])
    run('resume-s3',base+['--max-new',M3,'--output',runroot/'resume-s3','--input',newfile,'--checkpoint-restore',ck,'--checkpoint-id','s3',*T])
    run('append-empty',base+['--max-new',M,'--output',runroot/'append-empty','--input',write_tokens('history-pending.txt',prompt+sv['tokens']),
        '--checkpoint-restore',ck,'--checkpoint-id','gate',*T])
    R,X,X2,XF,Y,Z,E=(load(d) for d in ('ref-new','append-s2','append-s2b','fresh-s2ref','resume-s2','resume-s3','append-empty'))
    assert len(R['tokens'])==M1+M2+M3,'synthetic reference hit EOS'
    assert X['tokens']==R['tokens'][:M1],('append != one-shot reference',X['tokens'],R['tokens'])
    assert Y['tokens']==R['tokens'][M1:M1+M2],('restore-then-save chain (S2) != reference',Y['tokens'],R['tokens'])
    assert Z['tokens']==R['tokens'][M1+M2:],('second chained restore (S3) != reference',Z['tokens'],R['tokens'])
    assert X2['tokens']==X['tokens'] and XF['tokens']==X['tokens']
    assert E['tokens']==r1['tokens'],'append with an empty delta must equal the same-generation resume'
    L=len(new)
    xr=X['checkpoint']['restore'];xs=X['checkpoint']['save']
    assert X['checkpoint']['operations']==['append','save']
    assert xr['operation']=='append' and xr['saved_prefix_length']==N and xr['appended_length']==len(turn_tokens) and xr['input_length']==L
    assert xr['pending_token']==sv['tokens'][-1] and isinstance(xr['append_prefill_ms'],(int,float)) and xr['append_prefill_ms']>0
    assert X['prefill_ms']==xr['append_prefill_ms'] and xr['append_prefill_tokens']==L-N and xr['append_prefill_path']=='incremental'
    prefill_record(X,'incremental',N,L-N);prefill_record(R,'incremental',0,L);prefill_record(XF,'incremental',0,L)
    assert xs['checkpoint_id']=='s2' and xs['parent_checkpoint_id']=='gate' and xs['position']==L+M1-1 and xs['pending_token']==X['tokens'][-1]
    yr=Y['checkpoint']['restore']
    assert yr['operation']=='same-generation-resume' and yr['saved_prefix_length']==L+M1-1 and Y['checkpoint']['save']['checkpoint_id']=='s3'
    prefill_record(Y,None,L+M1-1,0)
    er=E['checkpoint']['restore'];assert er['operation']=='append' and er['appended_length']==0 and er['append_prefill_tokens']==1
    prefill_record(E,'incremental',N,1)
    man=lambda cid,root=ck:json.loads((root/cid/'manifest.json').read_text())
    m2,m2b,m2f,m3=man('s2'),man('s2b'),man('s2ref'),man('s3')
    strip=lambda m:[(b['name'],b['bytes'],b['sha256'],b['slice']) for b in m['blobs']]
    assert strip(m2)==strip(m2b)==strip(m2f),'append state != repeat append state != fresh one-shot state'
    assert m2['token_state']==m2b['token_state']==m2f['token_state']
    assert m2['lineage']=={'operation':'restore-then-save','parent':{'checkpoint_id':'gate','manifest_sha256':sha(gate/'manifest.json')}}
    assert m2f['lineage']=={'operation':'save','parent':None}
    assert m3['lineage']['parent']['checkpoint_id']=='s2' and m3['token_state']['prompt_length']==L and m3['token_state']['position']==L+M1+M2-1
    assert all(m['label']==LABEL and m['qualified_by']==QUALIFIED_BY for m in (m2,m2b,m2f,m3))
    state_equivalence=dict(blobs_compared=len(m2['blobs']),append_vs_repeat_vs_fresh_identical=True)
    # Span variants: every append of a different length/boundary equals a fresh one-shot reference
    # and leaves state byte-identical to a fresh save of the same processed history.
    spans=[]
    def span_case(tag,root_id,history,delta,decode,save_k=None):
        newv=history+delta;f=write_tokens(tag+'.txt',newv)
        run(tag+'-reference',base+['--max-new',decode,'--output',runroot/(tag+'-ref'),'--input',f,'--checkpoint-save',ck,'--checkpoint-id',tag+'-fresh',*T])
        run(tag+'-append',base+['--max-new',decode,'--output',runroot/(tag+'-append'),'--input',f,'--checkpoint-restore',ck,'--checkpoint-id',root_id,
            '--checkpoint-save',ck,'--checkpoint-save-id',tag+'-appended',*T])
        rf,ap=load(tag+'-ref'),load(tag+'-append')
        assert len(rf['tokens'])==decode,(tag,'synthetic reference hit EOS')
        assert ap['tokens']==rf['tokens'],(tag,'append != one-shot reference',ap['tokens'],rf['tokens'])
        Nr=man(root_id)['token_state']['position']
        ar=ap['checkpoint']['restore'];assert ar['operation']=='append' and ar['saved_prefix_length']==Nr and ar['append_prefill_tokens']==len(newv)-Nr
        prefill_record(ap,'incremental',Nr,len(newv)-Nr);prefill_record(rf,'incremental',0,len(newv))
        ma,mf=man(tag+'-appended'),man(tag+'-fresh')
        assert strip(ma)==strip(mf) and ma['token_state']==mf['token_state'],(tag,'append state != fresh one-shot state')
        spans.append(dict(case=tag,restore_position=Nr,restore_position_mod4=Nr%4,appended_positions=len(newv)-Nr,
            last_prompt_position=len(newv)-1,crosses_position_32=Nr<32<=len(newv)-1,decode=decode,append_equals_reference=True,
            state_identical_to_fresh_save=True,path='incremental'))
    span_case('span1',gate.name,prompt+sv['tokens'],[4],4)
    span_case('span28',gate.name,prompt+sv['tokens'],[(3*i+1)%14 for i in range(28)],6)
    run('save-k9',base+['--max-new',9,'--output',runroot/'save-k9','--input',pfile,'--checkpoint-save',ck,'--checkpoint-id','gate13',*T])
    s9=load('save-k9');assert len(s9['tokens'])==9 and man('gate13')['token_state']['position']==13
    span_case('span25-n13',('gate13'),prompt+s9['tokens'],[(5*i+2)%14 for i in range(25)],6)
    assert [s['restore_position_mod4'] for s in spans]==[0,0,1] and spans[1]['crosses_position_32'] and spans[2]['crosses_position_32']

    # ---------------- C. inspect modes
    def single_object(cp):
        lines=cp.stdout.splitlines();assert len(lines)==1,('stdout must be exactly one JSON object',cp.stdout[-300:])
        obj=json.loads(cp.stdout);assert isinstance(obj,dict)
        events=[json.loads(line) for line in cp.stderr.splitlines()]
        return obj,events
    cp=run('inspect-full-s2',['--checkpoint-inspect',ck/'s2'])
    full,events=single_object(cp)
    assert full['schema']=='ownrt.checkpoint-inspect.v1' and full['ok'] is True and full['mode']=='full' and full['device_required'] is False
    assert full['label']==LABEL and full['contract']==CONTRACT
    assert full['manifest']==m2 and full['manifest_sha256']==sha(ck/'s2/manifest.json') and full['error'] is None
    assert full['verified']['blobs_verified']==len(m2['blobs']) and full['verified']['blob_bytes_verified']==m2['measurements']['save_bytes']+4*m2['token_state']['position']
    assert sum(1 for e in events if e.get('event')=='blob-verified')==len(m2['blobs']) and events[0]['event']=='inspect-start' and events[-1]=={'event':'inspect-end','ok':True}
    cp=run('inspect-metadata-s2',['--checkpoint-inspect-metadata',ck/'s2'])
    meta,events=single_object(cp)
    assert meta['ok'] is True and meta['mode']=='metadata' and meta['manifest']==m2 and meta['verified']['blobs_verified'] is None
    assert not any(e.get('event')=='blob-verified' for e in events)
    noread=runroot/'noread';shutil.copytree(ck/'s2',noread/'s2')
    for f in (noread/'s2').glob('*.bin'):f.chmod(0)
    cp=run('inspect-metadata-unreadable-blobs',['--checkpoint-inspect-metadata',noread/'s2'])
    obj,_=single_object(cp);assert obj['ok'] is True,'metadata mode must not read blobs'
    cp=run('inspect-full-unreadable-blobs',['--checkpoint-inspect',noread/'s2'],expect=1)
    obj,_=single_object(cp);assert obj['ok'] is False and obj['error']['check']=='blob read' and obj['manifest'] is None
    for f in (noread/'s2').glob('*.bin'):f.chmod(0o644)
    cp=run('inspect-missing',['--checkpoint-inspect',runroot/'nothing'/'gate'],expect=1)
    obj,_=single_object(cp);assert obj['ok'] is False and obj['error']['check']=='visibility'
    corrupt_root=runroot/'inspect-corrupt';shutil.copytree(gate,corrupt_root/'gate')
    f=corrupt_root/'gate/blk.1.qsa.keys.bin';b=bytearray(f.read_bytes());b[0]^=1;f.write_bytes(bytes(b))
    cp=run('inspect-corrupt-blob',['--checkpoint-inspect',corrupt_root/'gate'],expect=1)
    obj,_=single_object(cp);assert obj['ok'] is False and obj['error']['check']=='blob sha256'

    # ---------------- D. restore refusals, each before the first device upload (packet180's 26 cases)
    refusals=[]
    def reseal(d,manifest_edit,tsv_edit):
        mtext=(d/'manifest.json').read_text();new_m=manifest_edit(mtext);assert new_m!=mtext
        ttext=(d/'fields.tsv').read_text();new_t=tsv_edit(ttext);assert new_t!=ttext
        old_row='\nmanifest_sha256\t'+hashlib.sha256(mtext.encode()).hexdigest()+'\n'
        assert new_t.count(old_row)==1
        new_t=new_t.replace(old_row,'\nmanifest_sha256\t'+hashlib.sha256(new_m.encode()).hexdigest()+'\n')
        (d/'manifest.json').write_text(new_m);(d/'fields.tsv').write_text(new_t)
    def one(text,old,new):
        assert text.count(old)==1,(old,text.count(old));return text.replace(old,new)
    def refusal(tag,mutate,marker,argv_input=None,tokenizer=tid,check_phrase='checkpoint restore refused',early=True,max_new=M,extra=(),source=None):
        # early: refused by the pre-load precheck (or argument parsing) -- no output directory is
        # ever created, i.e. before any model load; late: refused by restore after the model
        # load (engine-dependent checks). Both are before the first upload.
        root=runroot/'refuse'/tag;shutil.copytree(source or gate,root/'gate')
        if mutate:mutate(root/'gate')
        argv=base+['--max-new',max_new,'--output',runroot/'refuse-out'/tag,'--input',argv_input or pfile,'--checkpoint-restore',root,'--checkpoint-id','gate',*extra]
        if tokenizer is not None:argv+=['--tokenizer-identity',tokenizer]
        cp=run(tag,argv,expect=1)
        assert check_phrase in cp.stderr and marker in cp.stderr,(tag,cp.stderr[-400:])
        assert upload_marker not in cp.stderr,(tag,'refusal after the upload began')
        assert not (runroot/'refuse-out'/tag/'result.json').exists()
        assert (runroot/'refuse-out'/tag).exists()==(not early),(tag,'expected '+('pre-load' if early else 'post-load')+' refusal')
        refusals.append(tag+': '+marker+(' [before model load]' if early else ' [after model load, before upload]'))
    def corrupt(d):
        f=d/'blk.1.qsa.keys.bin';b=bytearray(f.read_bytes());b[0]^=1;f.write_bytes(bytes(b))
    refusal('corrupt-blob',corrupt,'blob sha256',early=False)
    refusal('wrong-prompt',None,'prefix',argv_input=write_tokens('wrong.txt',[3,5,3,7,1]))
    binsha=manifest['engine']['binary_sha256']
    def binary_mismatch(d):
        reseal(d,lambda m:one(m,'"binary_sha256":"'+binsha+'"','"binary_sha256":"'+'0'*64+'"'),
            lambda t:one(t,'\nbinary_sha256\t'+binsha+'\n','\nbinary_sha256\t'+'0'*64+'\n'))
    refusal('binary-mismatch',binary_mismatch,'engine identity',early=False)
    refusal('geometry-mismatch',lambda d:reseal(d,lambda m:one(m,'"context":64,','"context":128,'),lambda t:one(t,'\ncontext\t64\n','\ncontext\t128\n')),'geometry',early=False)
    def tamper(d):
        with (d/'manifest.json').open('a') as f:f.write(' ')
    refusal('manifest-tamper',tamper,'manifest sha256')
    h0=ts['token_history'][0]
    refusal('tsv-host-state-tamper',lambda d:(d/'fields.tsv').write_text(one((d/'fields.tsv').read_text(),'\nhistory0\t%d\n'%h0,'\nhistory0\t%d\n'%(h0+6))),
        'manifest cross-check: fields.tsv line')
    refusal('json-history-tamper',lambda d:reseal(d,lambda m:one(m,'"token_history":[%d,'%h0,'"token_history":[%d,'%(h0+6)),
        lambda t:one(t,'\nhistory0\t%d\n'%h0,'\nhistory0\t%d\n'%(h0+6))),'token state: manifest token_history disagrees')
    bad=list(new);bad[3]^=1
    refusal('append-prefix-mismatch',None,'prefix: append: --input differs from the saved processed history at index 3',argv_input=write_tokens('bad-prefix.txt',bad))
    bad=prompt+sv['tokens'][:-1]+[(sv['tokens'][-1]+1)%15]+turn_tokens
    refusal('append-pending-mismatch',None,'must be the saved pending token',argv_input=write_tokens('bad-pending.txt',bad))
    refusal('append-length-neither',None,'is neither the recorded prompt length',argv_input=write_tokens('bad-length.txt',prompt+sv['tokens'][:3]))
    refusal('tokenizer-mismatch',None,'tokenizer identity',tokenizer=tid_bad)
    refusal('tokenizer-missing',None,'--tokenizer-identity FILE is required for every checkpoint operation',tokenizer=None,check_phrase='')
    refusal('extra-file-in-checkpoint',lambda d:(d/'restore.lock').write_text('locked'),'file set: unexpected file restore.lock')
    # Pending stop token: a consistent checkpoint whose pending token is eos (mini eos=15) cannot be
    # resumed as the same generation (the uninterrupted run ended there) but can be appended to.
    eos=manifest['geometry']['eos'];nt=ts['next_token']
    def stop_pending(d):
        old_blob=hashlib.sha256((d/'next_token.bin').read_bytes()).hexdigest()
        (d/'next_token.bin').write_bytes(struct.pack('<i',eos));new_blob=hashlib.sha256((d/'next_token.bin').read_bytes()).hexdigest()
        reseal(d,lambda m:one(one(m,'"next_token":%d,'%nt,'"next_token":%d,'%eos),'"name":"next_token","bytes":4,"sha256":"'+old_blob+'"','"name":"next_token","bytes":4,"sha256":"'+new_blob+'"'),
               lambda t:one(one(t,'\nnext_token\t%d\n'%nt,'\nnext_token\t%d\n'%eos),'\nblob\tnext_token\t4\t'+old_blob+'\t','\nblob\tnext_token\t4\t'+new_blob+'\t'))
    refusal('resume-after-stop-token',stop_pending,'ended generation: same-generation resume: the saved generation already ended with stop token %d'%eos)
    stop_root=runroot/'stop-append';shutil.copytree(gate,stop_root/'gate');stop_pending(stop_root/'gate')
    cp=run('append-after-stop-token',base+['--max-new',M,'--output',runroot/'stop-append-out','--input',write_tokens('stop-append.txt',prompt+sv['tokens'][:-1]+[eos]+turn_tokens),
        '--checkpoint-restore',stop_root,'--checkpoint-id','gate',*T])
    sa=load('stop-append-out')['checkpoint']['restore'];assert sa['operation']=='append' and sa['pending_is_stop'] is True and sa['pending_token']==eos
    assert r1['checkpoint']['restore']['pending_is_stop'] is False
    refusals.append('append-after-stop-token: allowed (a chat turn may follow a stop token); pending_is_stop recorded')
    # Context bound: a resume steps positions N..N+max_new-1 (a save needs one more free position).
    refusal('resume-beyond-context',None,'context: same-generation resume of %d saved positions plus --max-new %d exceeds'%(N,64-N+1),max_new=64-N+1)
    refusal('resume-save-beyond-context',None,'(a save needs one free position)',max_new=64-N,extra=('--checkpoint-save',runroot/'never-written','--checkpoint-save-id','ctx'))
    assert not (runroot/'never-written').exists()
    cp=run('resume-to-context-edge',base+['--max-new',64-N,'--output',runroot/'edge','--input',pfile,'--checkpoint-restore',ck,'--checkpoint-id','gate',*T])
    edge=load('edge');assert len(edge['tokens'])==64-N and edge['tokens'][:M]==r1['tokens'] and edge['first_generated_token_ms']>0
    refusals.append('resume-to-context-edge: allowed exactly up to the last position; first_generated_token_ms recorded for a resume')
    # Save-only: a bad tokenizer identity file is refused before any model load and writes nothing.
    bad_tid=runroot/'tokenizer-identity-bad-format.tsv';bad_tid.write_text('format\tsomething-else\n')
    cp=run('save-bad-tokenizer-file',base+['--max-new',K,'--output',runroot/'save-bad-tid','--input',pfile,'--checkpoint-save',runroot/'bad-tid-root','--checkpoint-id','x',
        '--tokenizer-identity',bad_tid],expect=1)
    assert 'checkpoint save refused: tokenizer identity' in cp.stderr and not (runroot/'save-bad-tid').exists() and not (runroot/'bad-tid-root').exists()
    refusals.append('save-bad-tokenizer-file: refused before model load; nothing written')
    before=sha(ck/'s2/manifest.json')
    cp=run('never-overwrite',base+['--max-new',M,'--output',runroot/'never-overwrite','--input',newfile,'--checkpoint-restore',ck,'--checkpoint-id','gate',
        '--checkpoint-save',ck,'--checkpoint-save-id','s2',*T],expect=1)
    assert 'checkpoint save refused: never overwrite' in cp.stderr and upload_marker not in cp.stderr and sha(ck/'s2/manifest.json')==before
    refusals.append('never-overwrite: existing restore-then-save target refused before model load')
    cp=run('same-id-restore-then-save',base+['--max-new',M,'--output',runroot/'same-id','--input',pfile,'--checkpoint-restore',ck,'--checkpoint-id','gate',
        '--checkpoint-save',ck,'--checkpoint-save-id','gate',*T],expect=1)
    assert 'never overwrites the restored one' in cp.stderr;refusals.append('same-id-restore-then-save: argument refusal')
    held_root=runroot/'held';shutil.copytree(gate,held_root/'gate')
    with open(held_root/'gate.lock','a+') as lockfile:
        fcntl.flock(lockfile,fcntl.LOCK_EX)
        cp=run('lock-held-exclusive',base+['--max-new',M,'--output',runroot/'held-out','--input',pfile,'--checkpoint-restore',held_root,'--checkpoint-id','gate',*T],expect=1)
        assert 'checkpoint restore refused: lock' in cp.stderr and upload_marker not in cp.stderr
        cp=run('inspect-lock-held-exclusive',['--checkpoint-inspect-metadata',held_root/'gate'],expect=1)
        obj,_=single_object(cp);assert obj['error']['check']=='lock'
    refusals.append('lock-held-exclusive: restore and inspect refuse while a save/delete holds the lock')
    for tag,argv,phrase in (
        ('arg-save-id-without-restore',base+['--max-new',M,'--output',runroot/'arg1','--checkpoint-save',ck,'--checkpoint-id','x1','--checkpoint-save-id','x2',*T],'--checkpoint-save-id names the new checkpoint'),
        ('arg-tokenizer-without-mode',base+['--max-new',M,'--output',runroot/'arg2',*T],'--tokenizer-identity requires a checkpoint mode'),
        ('arg-dotdot-id',base+['--max-new',M,'--output',runroot/'arg3','--checkpoint-restore',ck,'--checkpoint-id','..',*T],'checkpoint id must be'),
        ('arg-lock-suffix-id',base+['--max-new',M,'--output',runroot/'arg4','--checkpoint-save',ck,'--checkpoint-id','x.lock',*T],'not ending in .lock')):
        cp=run(tag,argv,expect=1);assert phrase in cp.stderr,(tag,cp.stderr[-300:]);refusals.append(tag+': argument refusal')
    packet180_refusals=len(refusals)
    assert packet180_refusals==26,packet180_refusals

    # ---------------- E. validated delete and concurrent delete-vs-restore
    deletes=[]
    def delete(tag,target,expect,reason=None):
        cp=run(tag,['--checkpoint-delete',target],expect=0 if expect else 1)
        obj,_=single_object(cp)
        assert obj['schema']=='ownrt.checkpoint-delete.v1' and obj['deleted'] is expect,(tag,obj)
        if reason:assert obj['reason']==reason,(tag,obj)
        deletes.append(dict(tag=tag,deleted=obj['deleted'],reason=obj['reason'],check=(obj['error'] or {}).get('check')))
        return obj
    droot=runroot/'del';shutil.copytree(gate,droot/'gate')
    delete('delete-valid',droot/'gate',True)
    assert not (droot/'gate').exists() and not (droot/'gate.lock').exists()
    uroot=runroot/'inuse';shutil.copytree(gate,uroot/'gate')
    with open(uroot/'gate.lock','a+') as lockfile:
        fcntl.flock(lockfile,fcntl.LOCK_SH)
        delete('delete-in-use',uroot/'gate',False,'in_use')
    assert (uroot/'gate/manifest.json').is_file()
    plain=runroot/'notackpt';plain.mkdir();(plain/'data.txt').write_text('not a checkpoint\n')
    delete('delete-wrong-target-plain-dir',plain,False,'not_a_checkpoint')
    assert plain.is_dir() and not (runroot/'notackpt.lock').exists(),'no lock file for a non-checkpoint'
    mroot=runroot/'mismatch';shutil.copytree(gate,mroot/'other')
    delete('delete-wrong-target-id-mismatch',mroot/'other',False,'not_a_checkpoint')
    assert (mroot/'other').is_dir() and not (mroot/'other.lock').exists()
    lroot=runroot/'label';shutil.copytree(gate,lroot/'gate')
    reseal(lroot/'gate',lambda m:one(m,'"label":"'+LABEL+'"','"label":"stable"'),lambda t:one(t,'\nlabel\t'+LABEL+'\n','\nlabel\tstable\n'))
    delete('delete-wrong-target-label',lroot/'gate',False,'not_a_checkpoint')
    assert (lroot/'gate').is_dir() and not (lroot/'gate.lock').exists()
    xroot=runroot/'extra';shutil.copytree(gate,xroot/'gate');(xroot/'gate/notes.txt').write_text('extra\n')
    delete('delete-wrong-target-extra-file',xroot/'gate',False,'not_a_checkpoint')
    assert (xroot/'gate/notes.txt').is_file()
    delete('delete-missing',runroot/'nothing'/'gate',False,'not_a_checkpoint')
    # Real concurrency: a restore holds the shared lock (host-only hold hook) while delete runs.
    croot=runroot/'concurrent';shutil.copytree(gate,croot/'gate')
    argv=[str(a) for a in base+['--max-new',M,'--output',runroot/'concurrent-restore','--input',pfile,'--checkpoint-restore',croot,'--checkpoint-id','gate',*T]]
    child=subprocess.Popen([str(probe),*argv],env=dict(env,OWNRT_CHECKPOINT_TEST_HOLD_MS='3000'),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
        preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3)))
    seen=[];deadline=time.monotonic()+HOLD_DEADLINE_SECONDS
    while True:
        line=child.stderr.readline()
        assert line or child.poll() is None,'restore exited before holding the lock'
        seen.append(line)
        if '"event":"checkpoint-test-hold"' in line:break
        assert time.monotonic()<deadline,'hold marker deadline'
    in_use=delete('delete-during-restore',croot/'gate',False,'in_use')
    cp_inspect=run('inspect-during-restore',['--checkpoint-inspect-metadata',croot/'gate'])
    assert json.loads(cp_inspect.stdout)['ok'] is True,'shared holders coexist'
    out,err=child.communicate()
    results.append(dict(tag='concurrent-restore',argv=argv,returncode=child.returncode,stdout_tail=out[-600:],stderr_tail=(''.join(seen)+err)[-600:]))
    assert child.returncode==0 and upload_marker in ''.join(seen)+err
    assert load('concurrent-restore')['tokens']==r1['tokens'],'restore under a concurrent delete attempt must still continue exactly'
    delete('delete-after-restore',croot/'gate',True)
    assert not (croot/'gate').exists() and not (croot/'gate.lock').exists()
    for leftover in runroot.rglob('*.json.tmp'):raise AssertionError('partial manifest left behind: '+str(leftover))

    # ---------------- G. label compatibility (packet181): v1.2+p180 "experimental" manifests
    qb_text='"qualified_by":'+QUALIFIED_BY_TEXT+','
    def to_legacy(d):
        """This probe's v1.2+p181 checkpoint rewritten as a packet180 v1.2+p180 manifest (label
        experimental, no qualified_by); fields.tsv re-rendered by the packet180 rule and resealed."""
        reseal(d,lambda m:one(m,'"label":"'+LABEL+'","contract":"'+CONTRACT+'",'+qb_text,'"label":"'+LEGACY_LABEL+'","contract":"'+LEGACY_CONTRACT+'",'),
               lambda t:one(t,'\nlabel\t'+LABEL+'\ncontract\t'+CONTRACT+'\nqualified_scope\t'+QUALIFIED_BY['scope']+'\nqualified_by\t'+QUALIFIED_GATES+'\n',
                              '\nlabel\t'+LEGACY_LABEL+'\ncontract\t'+LEGACY_CONTRACT+'\n'))
        m=json.loads((d/'manifest.json').read_text())
        assert m['label']==LEGACY_LABEL and m['contract']==LEGACY_CONTRACT and 'qualified_by' not in m
        assert (d/'fields.tsv').read_text()==render(m,sha(d/'manifest.json'),(d/'manifest.json').read_text()),'legacy rendering'
        return m
    compat={}
    legacy_root=runroot/'legacy';shutil.copytree(gate,legacy_root/'gate');legacy=to_legacy(legacy_root/'gate')
    cp=run('legacy-inspect-metadata',['--checkpoint-inspect-metadata',legacy_root/'gate'])
    obj,_=single_object(cp);assert obj['ok'] is True and obj['label']==LEGACY_LABEL and obj['contract']==LEGACY_CONTRACT and obj['manifest']==legacy
    cp=run('legacy-inspect-full',['--checkpoint-inspect',legacy_root/'gate'])
    obj,_=single_object(cp);assert obj['ok'] is True and obj['verified']['blobs_verified']==len(legacy['blobs'])
    compat['inspect_experimental']='metadata and full inspect accept the v1.2+p180 experimental manifest'
    run('legacy-resume',base+['--max-new',M,'--output',runroot/'legacy-resume','--input',pfile,'--checkpoint-restore',legacy_root,'--checkpoint-id','gate',*T])
    lr=load('legacy-resume');assert lr['tokens']==r1['tokens'] and lr['checkpoint']['restore']['operation']=='same-generation-resume'
    assert lr['checkpoint']['restore']['manifest_sha256']==sha(legacy_root/'gate/manifest.json')
    compat['resume_experimental']='same-generation resume of an experimental checkpoint == the qualified checkpoint resume'
    run('legacy-append-save',base+['--max-new',M1,'--output',runroot/'legacy-append','--input',newfile,'--checkpoint-restore',legacy_root,'--checkpoint-id','gate',
        '--checkpoint-save',legacy_root,'--checkpoint-save-id','upgraded',*T])
    la=load('legacy-append');assert la['tokens']==X['tokens'] and la['checkpoint']['restore']['operation']=='append'
    up=man('upgraded',legacy_root)
    assert up['label']==LABEL and up['contract']==CONTRACT and up['qualified_by']==QUALIFIED_BY
    assert up['lineage']=={'operation':'restore-then-save','parent':{'checkpoint_id':'gate','manifest_sha256':sha(legacy_root/'gate/manifest.json')}}
    assert strip(up)==strip(m2) and up['token_state']==m2['token_state'],'restore-then-save from an experimental parent == from the qualified parent'
    run('legacy-upgraded-resume',base+['--max-new',M2,'--output',runroot/'legacy-upgraded-resume','--input',newfile,'--checkpoint-restore',legacy_root,'--checkpoint-id','upgraded',*T])
    assert load('legacy-upgraded-resume')['tokens']==R['tokens'][M1:M1+M2]
    compat['append_restore_then_save_experimental']='append from an experimental parent == the qualified append; its restore-then-save child is v1.2+p181 qualified-one-card with identical state blobs, and resumes == reference'
    refusal('legacy-binary-mismatch',lambda d:(to_legacy(d),binary_mismatch(d)),'engine identity',early=False)
    compat['experimental_refused_only_by_identity']='an experimental manifest with another binary_sha256 is refused by the engine identity check (after load), not by its label'
    def pair(mtext_old,mtext_new,tsv_old,tsv_new):
        return lambda d:reseal(d,lambda m:one(m,mtext_old,mtext_new),lambda t:one(t,tsv_old,tsv_new))
    refusal('label-experimental-with-p181-contract',pair('"label":"'+LABEL+'"','"label":"'+LEGACY_LABEL+'"','\nlabel\t'+LABEL+'\n','\nlabel\t'+LEGACY_LABEL+'\n'),
        'manifest: label experimental does not pair with contract v1.2+p181')
    refusal('label-qualified-with-p180-contract',lambda d:(to_legacy(d),pair('"label":"'+LEGACY_LABEL+'"','"label":"'+LABEL+'"','\nlabel\t'+LEGACY_LABEL+'\n','\nlabel\t'+LABEL+'\n')(d)),
        'manifest: label qualified-one-card does not pair with contract v1.2+p180')
    refusal('qualified-by-edited',pair('"date":"2026-10-22","operations":["append"','"date":"2026-10-23","operations":["append"',
        'packet180-session-swap-v2@2026-10-22:','packet180-session-swap-v2@2026-10-23:'),"manifest: qualified_by differs from this engine's qualification record")
    refusal('qualified-by-missing',lambda d:reseal(d,lambda m:one(m,qb_text,''),lambda t:one(t,'\nqualified_scope\t'+QUALIFIED_BY['scope']+'\nqualified_by\t'+QUALIFIED_GATES+'\n','\n')),
        'manifest: unexpected key set in manifest')
    def qualified_by_on_legacy(d):
        to_legacy(d)
        reseal(d,lambda m:one(m,'"contract":"'+LEGACY_CONTRACT+'",','"contract":"'+LEGACY_CONTRACT+'",'+qb_text),
               lambda t:one(t,'\ncontract\t'+LEGACY_CONTRACT+'\n','\ncontract\t'+LEGACY_CONTRACT+'\nqualified_scope\t'+QUALIFIED_BY['scope']+'\nqualified_by\t'+QUALIFIED_GATES+'\n'))
    refusal('qualified-by-on-legacy',qualified_by_on_legacy,'manifest: unexpected key set in manifest')
    refusal('contract-p179',pair('"contract":"'+CONTRACT+'"','"contract":"v1.2+p179"','\ncontract\t'+CONTRACT+'\n','\ncontract\tv1.2+p179\n'),
        'manifest: contract v1.2+p179 (this engine reads v1.2+p181 and v1.2+p180 checkpoints)')
    refusal('label-unknown',pair('"label":"'+LABEL+'"','"label":"stable"','\nlabel\t'+LABEL+'\n','\nlabel\tstable\n'),'manifest: label stable does not pair')
    compat['pairing_refusals']='label/contract pairing, qualified_by edits/missing/extra, other contracts and unknown labels are refused as malformed manifests before model load'
    ldel=runroot/'legacy-delete';shutil.copytree(gate,ldel/'gate');to_legacy(ldel/'gate')
    delete('delete-experimental',ldel/'gate',True)
    assert not (ldel/'gate').exists() and not (ldel/'gate.lock').exists()
    compat['delete_experimental']='the delete tool validates and removes an experimental checkpoint'
    compat_refusals=len(refusals)-packet180_refusals

    # ---------------- F. production shape: real device checkpoints through this C++ reader
    tid_real=p/'tokenizer-identity.tsv'
    values=dict(line.split('\t',1) for line in tid_real.read_text().splitlines() if line and not line.startswith('#'))
    production=dict(scope='real device checkpoints read in place (local untracked blobs) into scratch copies removed by the delete tool; no pins outside this packet')
    shape_root=build/'production-shape';shutil.rmtree(shape_root,ignore_errors=True);shape_root.mkdir(parents=True)
    # F1/F2. packet179's real gate checkpoint (v1 manifest) converted to both readable contracts.
    assert REAL179.is_dir() and len(list(REAL179.glob('*.bin')))==129,'packet179 real device checkpoint blobs missing (local untracked evidence)'
    old_manifest=json.loads((REAL179/'manifest.json').read_text())
    old_fields=dict(line.split('\t',1) for line in (REAL179/'fields.tsv').read_text().splitlines() if line.split('\t',1)[0] not in ('blob','skip'))
    for tag,label,contract in (('p179-as-experimental',LEGACY_LABEL,LEGACY_CONTRACT),('p179-as-qualified',LABEL,CONTRACT)):
        m=dict(format=old_manifest['format'],label=label,contract=contract)
        if contract==CONTRACT:m['qualified_by']=QUALIFIED_BY
        m.update(operations=OPERATIONS,checkpoint_id='gate',created=old_manifest['created'],
            lineage=dict(operation='save',parent=None),model=old_manifest['model'],engine=old_manifest['engine'],
            geometry=dict(old_manifest['geometry'],qh=int(old_fields['qh'])),dtypes=old_manifest['dtypes'],
            tokenizer_identity=dict(file_sha256=sha(tid_real),format=values['format'],gguf_header_sha256=values['gguf_header_sha256'],
                tokenizer_source_sha256=values['tokenizer_source_sha256'],vocab_bin_sha256=values['vocab_bin_sha256']),
            token_state=old_manifest['token_state'],sampler=old_manifest['sampler'],blobs=old_manifest['blobs'],
            skipped_buffers=old_manifest['skipped_buffers'],measurements=old_manifest['measurements'])
        text=json.dumps(m,separators=(',',':'),ensure_ascii=False)+'\n'
        pshape=shape_root/tag/'gate';pshape.mkdir(parents=True)
        (pshape/'manifest.json').write_text(text);(pshape/'fields.tsv').write_text(render(m,hashlib.sha256(text.encode()).hexdigest(),text))
        shutil.copyfile(REAL179/'tokens.bin',pshape/'tokens.bin')
        for b in m['blobs']:shutil.copyfile(REAL179/(b['name']+'.bin'),pshape/(b['name']+'.bin'))
        cp=run(tag+'-inspect-metadata',['--checkpoint-inspect-metadata',pshape])
        meta,_=single_object(cp);assert meta['ok'] is True and meta['manifest']==m and meta['label']==label and meta['contract']==contract
        cp=run(tag+'-inspect-full',['--checkpoint-inspect',pshape])
        full,_=single_object(cp)
        assert full['ok'] is True and full['verified']['blobs_verified']==128 and full['verified']['semantic_blob_checks'] is True
        assert full['verified']['blob_bytes_verified']==m['measurements']['save_bytes']+4*m['token_state']['position']==68756516+342*4
        fields_text=(pshape/'fields.tsv').read_text()
        (pshape/'fields.tsv').write_text(fields_text.replace('\nhistory1\t%d\n'%m['token_state']['token_history'][1],'\nhistory1\t%d\n'%(m['token_state']['token_history'][1]+1)))
        cp=run(tag+'-tsv-tamper',['--checkpoint-inspect-metadata',pshape],expect=1)
        obj,_=single_object(cp);assert obj['error']['check']=='manifest cross-check' and '(history1)' in obj['error']['detail']
        (pshape/'fields.tsv').write_text(fields_text)
        delete(tag+'-delete',pshape,True)
        assert not pshape.exists() and not (pshape.parent/'gate.lock').exists()
        production[tag]=dict(source='packet179 row-b device gate checkpoint (read-only), manifest converted to '+contract+' label '+label,
            blobs=128,skipped_buffers=len(m['skipped_buffers']),position=342,blob_bytes_verified=full['verified']['blob_bytes_verified'],
            python_render_equals_cpp_render=True,real_control_blob_semantics_pass=True,tsv_tamper_refused=True,scratch_copy_deleted_by_delete_tool=True)
    # F3. packet180's REAL v1.2+p180 experimental checkpoints S1/S2, verbatim (device-rendered fields.tsv).
    for cid in ('s1','s2'):
        src=REAL180/cid;assert src.is_dir() and len(list(src.glob('*.bin')))==129,'packet180 real device checkpoint '+cid+' missing (local untracked evidence)'
        realm=json.loads((src/'manifest.json').read_text())
        assert realm['label']==LEGACY_LABEL and realm['contract']==LEGACY_CONTRACT and realm['engine']['binary_sha256'].startswith('f68714ce')
        root=shape_root/'p180-real';shutil.copytree(src,root/cid)
        assert (root/cid/'fields.tsv').read_text()==render(realm,sha(root/cid/'manifest.json'),(root/cid/'manifest.json').read_text()),'Python render port != packet180 device fields.tsv'
        cp=run('p180-real-'+cid+'-inspect-metadata',['--checkpoint-inspect-metadata',root/cid])
        meta,_=single_object(cp);assert meta['ok'] is True and meta['manifest']==realm and meta['label']==LEGACY_LABEL
        cp=run('p180-real-'+cid+'-inspect-full',['--checkpoint-inspect',root/cid])
        full,_=single_object(cp)
        assert full['ok'] is True and full['verified']['blobs_verified']==128 and full['verified']['semantic_blob_checks'] is True
        assert full['verified']['blob_bytes_verified']==realm['measurements']['save_bytes']+4*realm['token_state']['position']
        row=dict(source='packet180 row-b device checkpoint '+cid+' (v1.2+p180, label experimental), copied verbatim',
            position=realm['token_state']['position'],blobs=128,blob_bytes_verified=full['verified']['blob_bytes_verified'],
            device_fields_tsv_equals_reader_rendering=True,metadata_inspect=True,full_inspect=True,real_control_blob_semantics_pass=True)
        if cid=='s1':
            # The whole pre-load restore precheck (manifest parse incl. label/contract pairing, TSV
            # cross-check, closed file set, tokens.bin, token history, tokenizer identity, append
            # classification of the real NEW input) accepts it; the mini engine then stops at its
            # own input token-range check because real token ids exceed the mini vocabulary.
            newreal=p/'lineage/packet180-receipts/row-b/run/inputs/new.txt'
            argv=base+['--max-new',128,'--output',runroot/'p180-real-s1-restore','--input',newreal,'--checkpoint-restore',root,'--checkpoint-id','s1',
                '--tokenizer-identity',tid_real]
            cp=run('p180-real-s1-restore-precheck',argv,expect=1)
            assert 'checkpoint restore refused' not in cp.stderr and upload_marker not in cp.stderr and 'token range' in cp.stderr,cp.stderr[-400:]
            assert (runroot/'p180-real-s1-restore').is_dir() and not (runroot/'p180-real-s1-restore/result.json').exists()
            row['restore_precheck']='passed pre-load (append of the real 469-token NEW input classified); the mini probe stops after load at its token-range check; on device the engine identity check refuses it (binary f68714ce... != this binary)'
        delete('p180-real-'+cid+'-delete',root/cid,True)
        assert not (root/cid).exists() and not (root/(cid+'.lock')).exists()
        row['scratch_copy_deleted_by_delete_tool']=True
        production['p180-real-'+cid]=row
    shutil.rmtree(shape_root)

    receipt=dict(passed=True,device_executed=False,model_reads=False,
        driver='patched packet181 entry TU compiled -DOWN_RT_HOST_ONLY (g++, packet58aj gnu-host entry command); ancestor gnu-host object set relinked byte-input from in-packet copies; real CPU arithmetic path',
        compile=compile_cmd,link=link_cmd,sources_sha256=sources,ancestor_objects_sha256=ancestor_objects,
        probe_binary_sha256=sha(probe),
        label=LABEL,contract=CONTRACT,qualified_by=QUALIFIED_BY,
        round_trip=dict(prompt=prompt,K=K,M=M,N=N,merged_equal_reference=True,repeat_restore_identical=True,
            blob_count=len(manifest['blobs']),skipped_count=len(manifest['skipped_buffers']),manifest_label=LABEL,python_render_equals_cpp_render=True,
            slice_arithmetic='qsa keys/values rows [0:N) at 2*kvh*ad bytes/row; raw rows [0:N) at 2*id; pooled rows [0:floor(N/4)) at 2*id; verified against blob bytes'),
        append=dict(turn=turn_tokens,new_input_tokens=L,M1=M1,M2=M2,M3=M3,append_equals_reference=True,
            restore_then_save_chain_equals_reference=True,second_chain_restore_equals_reference=True,repeat_append_identical=True,
            fresh_save_state_identical=True,empty_delta_equals_same_generation_resume=True,state_equivalence=state_equivalence,
            span_variants=spans),
        prefill_path=dict(engine_mechanism='incremental',chunked_path_exists=False,
            recorded=dict(fresh='checkpoint.prefill {path incremental, first_position 0, tokens len(input), ms == prefill_ms}',
                append='checkpoint.prefill {path incremental, first_position N, tokens len(input)-N}; restore.append_prefill_tokens/append_prefill_path',
                resume='checkpoint.prefill {path null, tokens 0}; restore.append_prefill_tokens 0, append_prefill_path null'),
            note='the brief asked for chunked == incremental == one-shot on the probe geometry; this engine has no chunked prefill (one position per prompt step for fresh prompts and appends alike), so the probe proves incremental append == one-shot for spans of 1, 6, 28 and 25 positions, restore points N=12 and N=13 (not a multiple of 4), and spans crossing position 32'),
        inspect=dict(full_single_json_object=True,metadata_single_json_object=True,stderr_json_lines=True,
            metadata_reads_no_blobs='passes with every blob chmod 000; full mode refuses with blob read',corrupt_blob='blob sha256'),
        refusals=refusals,packet180_refusal_cases=packet180_refusals,compat_refusal_cases=compat_refusals,deletes=deletes,
        label_compatibility=compat,production_shape=production,
        concurrent_delete_vs_restore=dict(delete_reason=in_use['reason'],restore_returncode=0,restore_tokens_equal_resume=True,
            hold='host-only OWNRT_CHECKPOINT_TEST_HOLD_MS hook (absent from the device build) holds the shared lock after every read'),
        results=results,
        peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024,
        scope='synthetic --mini CPU sessions of the patched entry TU plus production-shape reads of real packet179/packet180 device checkpoints; correctness of operations, format, label compatibility, locking and fail-closed gates only; not device, arithmetic or performance qualification; the production-geometry gates are device rows a and b')
    assert receipt['peak_child_rss_bytes']<4*1024**3
    save(p/'evidence/checkpoint-probe.json',receipt)
    print('one-card checkpoint v3 host-only probe PASS:',len(results),'native runs,',len(refusals),'refusals (',packet180_refusals,'packet180 +',compat_refusals,'compat ),',
          len(deletes),'delete cases,',len(spans),'span variants',flush=True)

if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
