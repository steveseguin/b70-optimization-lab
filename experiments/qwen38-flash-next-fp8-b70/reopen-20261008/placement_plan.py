"""CPU allocation census; arithmetic is not a host/VRAM peak measurement."""
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('v5_plan', HERE/'overlay/vllm/q38_expert_placement.py')
v5 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v5)
GIB = 2**30


def storage_plan(config, tensors, placement):
    cfg = config['text_config']
    if (cfg['num_hidden_layers'], cfg['num_experts'], cfg['hidden_size'], cfg['moe_intermediate_size']) != (48,512,2560,640):
        raise ValueError('v5 shape census requires a new qualification')
    tables = [t for n,t in tensors.items() if 'ple_embedding.ngram_embedding' in n and len(t['shape']) == 2]
    if any(t['dtype'] not in ('F8_E4M3','F8_E4M3FN') or t['shape'][1] != 160 for t in tables):
        raise ValueError('native PLE identity changed')
    rows = sum(t['shape'][0] for t in tables)
    padded = math.ceil(rows/cfg['make_ngram_vocab_size_divisible_by'])*cfg['make_ngram_vocab_size_divisible_by']
    if padded % 4:
        raise ValueError('uneven PLE sharding')
    embedding = tensors['model.language_model.embed_tokens.weight']
    if embedding['shape'] != [248320,2560] or embedding['dtype'] != 'BF16':
        raise ValueError('embedding identity changed')
    ranks = []
    for rank in range(4):
        buffers = [dict(name='PLE',shape=[padded//4,160],itemsize=1,bytes=padded//4*160),
                   dict(name='input_embedding',shape=[248320//4,2560],itemsize=2,bytes=embedding['bytes']//4)]
        count = 0
        for layer in range(48):
            _, host = v5.row_plan(placement,rank,layer)
            count += len(host)
            for name, tail in [('w13',(1280,2560)),('w2',(2560,640))]:
                if host:
                    buffers.append(dict(name=f'layer{layer}.{name}',shape=[len(host),*tail],itemsize=1,
                                        bytes=len(host)*math.prod(tail)))
        ranks.append(dict(rank=rank,ple_host_rows=padded//4,ple_device_rows=0,
                          host_experts=count,buffers=buffers,
                          pinned_bytes=sum(b['bytes'] for b in buffers)))
    return ranks


def static_weight_floor(tensors, mtp):
    weights = {n:t for n,t in tensors.items() if n.endswith('.weight')
               and not any(skip in n for skip in ('hashstats_','token_lookup','hyper_connection_mixer.block_inject_weight'))
               and (mtp or not n.startswith('mtp.'))}
    total = sum(t['bytes'] for t in weights.values())
    replicated = sum(t['bytes'] for n,t in weights.items()
                     if n.endswith(('input_mix_weight_up.weight','input_mix_weight_down.weight')))
    # Optimistic balanced partition except proven replicated HC weights.
    # NOT a per-rank upper bound: vision, scales and runtime remain uncounted.
    return math.ceil((total+replicated*3)/4)


def enumerate_candidates(config, tensors, kv=376569856):
    certified=json.loads((HERE/'placement-certified-v5.json').read_text())
    larger=json.loads((HERE.parent/'data/20260913-q38-expert-host-placement-a315-census-5gib-mc2-per-rank.json').read_text())
    # Explore larger host placements too; no cold expert is pruned. These
    # are planning masks, not claims that their additional experts are never hit.
    extended=[]
    for goal in (1000,1100,1200):
        mask=json.loads(json.dumps(certified))
        for rank in range(4):
            layers=mask[str(rank)]
            while sum(len(v) for v in layers.values()) < goal:
                layer=min(range(48), key=lambda i:(len(layers.get(str(i),[])),i))
                rows=layers.setdefault(str(layer),[])
                rows.append(next(e for e in range(128) if e not in rows))
                rows.sort()
        extended.append((f'v5-{goal}-rows',mask))
    candidates=[]
    for name, mask in [('certified-v5',certified),('long-context-v5',larger),*extended]:
        ranks=storage_plan(config,tensors,mask)
        pins=[r['pinned_bytes'] for r in ranks]
        for mtp in [1,0]:
            base=static_weight_floor(tensors,mtp)
            # Same historical capacity used for all four is explicitly a scenario,
            # not an attestation of ranks 1..3.
            reserves=[34242297856 - (base-pin+kv) for pin in pins]
            candidates.append(dict(name=name,mtp_depth=mtp,pins_per_rank=pins,pins_total=sum(pins),
                host_peak_bytes=None,nonpin_allowance_under_85gb=85_000_000_000-sum(pins),
                conditional_static_reserve_gib_per_rank=[x/GIB for x in reserves],
                complete_vram_peak_bytes_per_rank=[None]*4,
                qualifies=False,reason='peak calibration unavailable; static floor is not a VRAM upper bound'))
    return candidates
