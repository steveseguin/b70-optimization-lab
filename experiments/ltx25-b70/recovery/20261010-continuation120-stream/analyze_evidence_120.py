#!/home/steve/.venvs/ltx25-baseline/bin/python
"""CPU-only regular-file receipt analysis; stdout only, no runtime/device imports."""
import datetime
import hashlib
import json
from pathlib import Path
import statistics
import struct

BASE = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
STEM = 'encoder-server-continuation-stream-{packet}-frame-dg{dg}-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f121'
CONFIGS = [('118b-dg0', '118b', 0, '.completed-20261010T0250Z', 's118b-live02'),
           ('118b-dg1-sampler-a', '118b', 1, '', 's118b-dg1-live01'),
           ('119-dg1-eager-display', '119', 1, '-dseager-display-ra1-ssfull', 's119-live01')]


def analyze():
    files = {}
    def read(path):
        raw = path.read_bytes()
        files[str(path)] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
                            'read_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        return raw
    def obj(path):
        return json.loads(read(path))
    def summary(vals):
        return {'n':len(vals), 'median':statistics.median(vals), 'min':min(vals), 'max':max(vals)}
    result = {'schema':'ltx.continuation120.evidence.v1', 'runs':{}, 'files_read':files,
              'methodology':{'metric_sequences':list(range(10,36)), 'identity_sequences':list(range(37)),
                'period':'submit[i+1]-submit[i], seconds, paired i=10..35',
                'limits':'Host wall boundaries, not device kernel timestamps. Upsampler end is inferred from next condition-B node start; node overhead included. Live logs/manifests may grow; hashes identify observed bytes.'}}
    all_d = {}
    for label, packet, dg, suffix, work in CONFIGS:
        root=BASE/(STEM.format(packet=packet,dg=dg)+suffix)
        receipts=[obj(root/'receipts'/('receipt-stream%s-s%08d.json'%(packet,i))) for i in range(37)]
        decodes=[obj(root/'receipts'/('decode-stream%s-s%08d.json'%(packet,i))) for i in range(37)]
        manifest=[json.loads(line) for line in read(Path('/home/steve/ltx-stream')/work/'manifest.jsonl').splitlines() if line]
        read(Path('/home/steve/ltx-stream')/work/'client.log')
        metrics={}; timelines=[]; snaps={}; margins=[]; memory=[]
        def add(k,v):metrics.setdefault(k,[]).append(v)
        for i in range(10,36):
            r,d,prev,nxt=receipts[i],decodes[i],decodes[i-1],receipts[i+1]
            t,pt,dt=r['timing_ns'],prev['timing_ns'],d['timing_ns']
            base=t['sampler_a_start']
            marks={'sampler_a_start':base,'sampler_a_end':t['stage_a_done'],
                'predecessor_display_start':pt['display_start'],'predecessor_display_end':pt['display_done'],
                'upsampler_start':t['upsampler_start'],'upsampler_end_upper_bound':t['condition_b_start'],
                'condition_b_start':t['condition_b_start'],'sampler_b_start':t['sampler_b_start'],
                'sampler_b_end':t['stage_b_done'],'cone_start':dt['decode_start'],'cone_end':dt['video_done']}
            timelines.append({'sequence':i,'origin_ns':base,'seconds_after_sampler_a_start':{k:(v-base)/1e9 for k,v in marks.items()}})
            for k,v in marks.items():add('timeline_'+k,(v-base)/1e9)
            add('period',(nxt['timing_ns']['submit']-t['submit'])/1e9)
            add('upsample_b_prep',(t['sampler_b_start']-t['stage_a_done'])/1e9)
            add('upsampler_to_condition_b',(t['condition_b_start']-t['upsampler_start'])/1e9)
            add('condition_b',(t['condition_b_done']-t['condition_b_start'])/1e9)
            add('receipt',(t['receipt_staged']-t['anchor_ready'])/1e9)
            for key,value in r['turnaround']['split'].items():
                add('turnaround_'+key,value)
            add('cone_on_chain',r['timing_s']['anchor_decode_in_chain'])
            add('display',d['timing_s']['display_decode'])
            add('text_a_prep',r['timing_s']['submit_to_sampler_start'])
            add('anchor_ready_to_go',d['timing_s']['anchor_ready_to_go'])
            add('actual_go_wait',d['schedule']['go_wait_s'])
            add('first_node_to_condition_a',r['timing_s']['submit_split']['first_node_to_condition_a'])
            add('display_end_minus_condition_b',(pt['display_done']-t['condition_b_start'])/1e9)
            for s in r['snapshots']:
                add(s['label']+'_snapshot',s['seconds'])
                snaps.setdefault(s['label'],[]).append({'seq':i,'dual':s['dual'],'min_margin_bytes':s['min_margin_bytes'],'parts_s':s['parts_s']})
                margins.append(s['min_margin_bytes'])
            for site in ('before','after'):
                memory.append({'seq':i,'site':site,**r['memory'][site]})
            turn=nxt['turnaround']['marks_ns']
            ra=d['schedule'].get('anchor_read_ahead')
            if ra:
                add('read_ahead_done_after_commit_written',(ra['prepared_ns']-turn['commit_written'])/1e9)
                add('read_ahead_done_minus_http_constructed',(ra['prepared_ns']-turn['first_served'])/1e9)
                add('read_ahead_done_minus_next_submit',(ra['prepared_ns']-nxt['timing_ns']['submit'])/1e9)
        prep=obj(root/'stream-preparation.json')
        result['runs'][label]={'path':str(root),'observed_manifest_rows':len(manifest),
            'metrics':{k:summary(v) for k,v in metrics.items()}, 'timelines':timelines,
            'snapshots':snaps,'memory':memory,'preparation_snapshot':prep['snapshot'],
            'decoder_pool':decodes[20]['decoder'].get('pool'),
            'qualification_verdict_sha256':receipts[20]['qualification_verdict_sha256'],
            'cone_equal_37':sum(d['anchor_decode']['equal'] is True for d in decodes),
            'anchor_read_sources':[r.get('anchor_read_source') for r in receipts],
            'min_snapshot_margin_bytes':min(margins)}
        all_d[label]=decodes
    result['identity']={}
    for label,ds in all_d.items():
        result['identity'][label]={tensor:sum(a['tensors'][tensor]['sha256']==b['tensors'][tensor]['sha256'] for a,b in zip(all_d['118b-dg0'],ds)) for tensor in ('images','waveform')}
    checkpoint=Path('/mnt/fast-ai/llm-models/LTX-2.5-baseline/vae/ltx-2.5-video-vae-bf16.safetensors')
    with checkpoint.open('rb') as stream:
        header_length=struct.unpack('<Q',stream.read(8))[0]; raw=stream.read(header_length)
    header=json.loads(raw); groups={}
    for key,value in header.items():
        if key=='__metadata__':continue
        prefix=key.split('.')[0]; groups[prefix]=groups.get(prefix,0)+value['data_offsets'][1]-value['data_offsets'][0]
    result['sources'] = {}
    author = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261010-continuation119-stream')
    for name in ('integration.py','stream_schedule.py','stream_receipts.py','session.py','snapshot_fingerprint.py'):
        read(author/name)
        result['sources'][name] = str(author/name)
    for name in ('source/scripts/native_safety.py','source/comfy_extras/nodes_lt_upsampler.py'):
        source=BASE/'prepared-continuation-stream-119'/name
        read(source)
        result['sources'][name]=str(source)
    result['checkpoint_census']={'path':str(checkpoint),'header_sha256':hashlib.sha256(raw).hexdigest(),
        'header_bytes':header_length,'tensor_payload_bytes_by_prefix':groups,
        'limit':'Checkpoint storage census, not runtime allocated/reserved peak; header only read, no tensor payload loaded.'}
    return result

if __name__=='__main__':
    print(json.dumps(analyze(),indent=2,sort_keys=True,ensure_ascii=False))
