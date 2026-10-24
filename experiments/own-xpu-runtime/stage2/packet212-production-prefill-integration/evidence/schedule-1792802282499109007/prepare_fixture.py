"""Extract retained production metadata only; no model reads or runtime imports."""
from collections import Counter
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
P181 = P.parent / 'packet181-session-swap-v3/one-card'
OWNER = P.parent / 'packet201-streaming-serving/evidence/planned-a/output/owner'
PROFILE = ROOT / 'experiments/own-xpu-runtime/ops/packet201-window/actual-cpu-plan.json'
CENSUS = P.parent / 'packet207-host-paired-projections/production-census.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def extract():
    sources = [OWNER / 'plan.json', OWNER / 'census.json', OWNER / 'prepared-arguments-parity0.jsonl',
               P181 / 'inputs/plan.tsv', P181 / 'dispatch.json', P181 / 'selection.json', PROFILE, CENSUS]
    pins = {str(path.relative_to(ROOT)): sha(path) for path in sources}
    plan = json.loads((OWNER / 'plan.json').read_text())
    profile = json.loads(PROFILE.read_text())['profile']
    old = json.loads(CENSUS.read_text())
    for name, value in old['source_sha256'].items():
        require(sha(ROOT / name) == value, 'retained production census source changed: ' + name)
    require(plan['cards'] == 1 and plan['dispatch_sites'] == len(plan['launch_census']) == 1486,
            'exact retained full production plan')
    tensors = {row['name']: row for row in plan['tensor_owners']}
    types = {}
    for line in (P181 / 'inputs/plan.tsv').read_text().splitlines():
        fields = line.split()
        name = fields[1]
        require(name not in types, 'duplicate original tensor')
        types[name] = {'type_code': int(fields[3]), 'gguf_dimensions': [int(x) for x in fields[9:]],
                       'source_bytes': int(fields[5])}
    recorded = {row['name']: row for row in old['gdn_projection_tensors']}
    captures = Counter()
    prepared = [json.loads(line) for line in (OWNER / 'prepared-arguments-parity0.jsonl').read_text().splitlines()]
    for row in prepared:
        index = row['site']
        require(type(index) is int and 0 <= index < len(plan['launch_census']), 'prepared index')
        require(row['label'] == plan['launch_census'][index]['label'], 'prepared label/order mismatch')
        captures[index] += 1
    sites = []
    for index, original in enumerate(plan['launch_census']):
        site = dict(index=index, label=original['label'], op=original['op'], card=original['card'],
                    recorded_prepared_commands=captures[index], core_kernels=original['core_kernels'],
                    parallel_kernels=original['parallel_kernels'])
        if original['label'].endswith(('.gdn.qkv', '.gdn.z')):
            layer = int(original['label'].split('.')[1])
            name = f"blk.{layer}.{'attn_qkv' if original['label'].endswith('.qkv') else 'attn_gate'}.weight"
            t = types[name]
            evidence = recorded[name]
            require(t['gguf_dimensions'] == [2560, 10240 if original['label'].endswith('.qkv') else 6144],
                    'actual projection shape')
            require(t['type_code'] == evidence['gguf_type'] and tensors[name]['stored_bytes'] == evidence['stored_bytes'],
                    'actual projection layout/type census')
            require(evidence['variant'] == 'expanded_sg32_v1', 'selected projection variant')
            site['projection'] = dict(name=name, type_code=t['type_code'], rows=t['gguf_dimensions'][1],
                                      columns=t['gguf_dimensions'][0], variant=6,
                                      stored_bytes=tensors[name]['stored_bytes'])
        sites.append(site)
    require(len({row['label'] for row in sites}) == len(sites), 'unique logical sites')
    argv = profile['native_argv']
    observed = {name: argv[argv.index(name) + 1] for name in
                ('--experts', '--hc', '--hc-geometry', '--other-fusion', '--cache-maintenance', '--cache-cap', '--cache-bytes')}
    require(observed == {'--experts':'wide64+halfcache', '--hc':'p60fusion', '--hc-geometry':'hc-wide',
                         '--other-fusion':'fused', '--cache-maintenance':'overlap', '--cache-cap':'max',
                         '--cache-bytes':'21552729600'}, 'selected baseline execution identity')
    require(json.loads((P181 / 'selection.json').read_text())['choices']['down'] == 'down-tile16', 'selected down kernel')
    return dict(schema='packet212.production-schedule-inputs.v1', source_sha256=pins, sites=sites,
                geometry=profile['identity']['geometry'], selected_baseline_flags=observed,
                field_scope='Exact recorded logical order/op/card and prepared command multiplicity; candidate tensor type/shape/layout joined to pinned source. Inputs/outputs arrays unavailable and deliberately not fabricated. Runtime validates actual Engine bindings.',
                baseline_cache_scope='Recorded baseline uses overlap; new frozen interval policy is a separate explicit candidate delta.',
                prepared_command_rows=len(prepared), distinct_prepared_sites=len(captures),
                logical_sites_without_prepared_commands=len(sites)-len(captures))


def main():
    value = extract()
    target = P / 'schedule-inputs.json'
    require(not target.exists(), 'preserve prior fixture; no overwrite')
    target.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed':True, 'native_executed':False, 'file':str(target), 'sha256':sha(target),
                      'sites':len(value['sites']), 'prepared_command_rows':value['prepared_command_rows']}))


if __name__ == '__main__':
    main()
