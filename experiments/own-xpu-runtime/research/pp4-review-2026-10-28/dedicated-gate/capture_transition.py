"""Narrow offline exception for the exact capture patch, never a general flag."""
from hashlib import sha256
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent

def need(value,message):
    if not value:raise ValueError(message)

def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())

def receipt(plan):
    entries=[(p,h) for p,h in plan['pins'].items() if p.endswith('/build-receipt.json')]
    need(len(entries)==1,'one pinned build receipt required')
    path,expected=entries[0];need(digest(path)==expected,'build receipt changed')
    result=read(path)
    need(plan['pins'].get(result['binary'])==result['binary_sha256']
         and digest(result['binary'])==result['binary_sha256'],'binary differs from pinned receipt')
    return result

def validate_build_delta(old,new,catalog):
    need(old['binary_sha256']==catalog['old_binary_sha256'],'unrecognized old capture-control binary')
    need(set(old['sources'])==set(new['sources']),'native source inventory changed')
    actual={k for k in old['sources'] if old['sources'][k]!=new['sources'][k]}
    need(actual==set(catalog['sources']),'native change outside exact capture patch')
    for name,row in catalog['sources'].items():
        need((old['sources'][name],new['sources'][name])==(row['before'],row['after']),
             'capture patch source bytes differ: '+name)
    for field in ('runtime_assets','generated_authority','generated_dependencies','build_script_sha256'):
        need(old[field]==new[field],'build runtime/compiler authority changed: '+field)
    def normalize(r):
        # Receipt rows also contain elapsed time and compiler diagnostics.
        # Build identity is the successful command argv, not those observations.
        need(all(row.get('rc') == 0 for row in r['commands'].values()),
             'successful compiler/link commands required')
        commands={name:row['cmd'] for name,row in r['commands'].items()}
        return json.dumps(commands,sort_keys=True).replace(str(Path(r['binary']).parent),'<BUILD>')
    need(normalize(old)==normalize(new),'compiler/link commands differ beyond fresh build paths')


def validate(old_plan,new_plan,proof_path,proof_sha256):
    need(isinstance(proof_sha256,str) and digest(proof_path)==proof_sha256,'explicit capture parity proof SHA required')
    catalog=read(HERE/'capture-candidate/native-transition.json')
    need(digest(HERE/'capture-candidate/native.patch')==catalog['native_patch_sha256'],'capture allowlist patch changed')
    old,new=receipt(old_plan),receipt(new_plan);validate_build_delta(old,new,catalog)
    need(new_plan.get('dedicated_capture_ready') is True,'capture timing plan must explicitly enable capture')
    python_delta={row['path']:row for row in read(HERE/'capture-candidate/python-tests.json')['sources']
                  if row['base_sha256'] is not None}
    for path,row in python_delta.items():
        need(new_plan['pins'].get(path)==row['candidate_sha256'],'capture Python source differs: '+path)
    for path in old_plan['pins'].keys() & new_plan['pins'].keys():
        if not path.endswith('.py') or old_plan['pins'][path]==new_plan['pins'][path]:continue
        need(path in python_delta and old_plan['pins'][path]==python_delta[path]['base_sha256']
             and new_plan['pins'][path]==python_delta[path]['candidate_sha256'],
             'Python change outside exact capture patch: '+path)

    proof=read(proof_path)
    need(proof.get('schema')=='ownrt.dedicated-state-parity.v1' and proof.get('passed') is True,
         'full dedicated parity proof required')
    need(proof['target'].get('passed') is True and len(proof['target']['compared_source_keys'])==2065
         and proof['draft'].get('passed') is True and len(proof['draft']['compared_source_keys'])==73,
         'full2065 target/73draft comparison required')
    need(proof['pair_sequence_sha256']=='fc730d4ca40b4da0b0787706758851296a5b445b209629b1be7544e44f9eb9d5',
         'capture gate canonical1707pair identity differs')
    candidates=[]
    for item in proof['sources']:
        path=Path(item['path'])
        if path.name!='plan.json':continue
        need(path.is_file() and digest(path)==item['sha256'],'parity proof plan source changed')
        plan=read(path)
        if plan.get('schema')=='ownrt.dedicated-provider-plan.v1':candidates.append(plan)
    need(len(candidates)==1,'one actual dedicated gate plan required')
    gate=candidates[0]
    need(all(gate['pins'].get(path)==new_plan['pins'][path] for path in new_plan['pins'] if path.endswith('.py')),
         'capture gate Python source pins differ from timing')
    need(receipt(gate)['binary_sha256']==new['binary_sha256'] and gate.get('dedicated_capture_ready') is True
         and gate.get('check_policy')=='qualification','proof not bound to current capture binary/opt-in gate')
    for key in ('prompt_tokens','context','vocab','eos_token_ids','model_identity_sha256','draft_model_sha256','speculative_depth'):
        need(gate[key]==new_plan[key],'capture gate/timing identity mismatch: '+key)
    need(gate['max_new']==32,'capture parity proof must be the bounded32-output gate')
    return dict(scope='Exact capture-patch binary transition only; old controls retained, no unchanged rerun.',
        old_binary_sha256=old['binary_sha256'],new_binary_sha256=new['binary_sha256'],
        source_changes=sorted(catalog['sources']),parity_proof_sha256=proof_sha256)
