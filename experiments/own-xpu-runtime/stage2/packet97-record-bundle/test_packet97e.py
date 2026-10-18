"""Regression checks for bounded KD references and untouched screen identity."""
import copy,json
from pathlib import Path
import pytest
from bundle_selection import views,selection
import kd_reference as k
P=Path(__file__).resolve().parent

def test_all_compositions_preserve_draft_and_route():
    for v in views().values():
        original=selection(v);before=copy.deepcopy(original);projected=k.project(original)
        assert original==before and projected['draft']==original['draft']
        assert projected['choices']==dict(original['choices'],**k.TARGET_ONLY)
        assert projected['choices']['route']==original['choices']['route']
        assert projected['choices']['recurrence']==original['choices']['recurrence']

def test_unsealed_draft_or_unknown_composition_refused():
    original=selection(next(iter(views().values())))
    for mutate in (lambda x:x['draft'].update(head_format='q4-g32'),lambda x:x['choices'].update(experts='unknown')):
        bad=copy.deepcopy(original);mutate(bad)
        with pytest.raises(AssertionError,match='unsealed'):k.project(bad)

def test_binding_and_every_owner_checked(tmp_path):
    from build_engine import sha,save
    target=tmp_path/'target.json';save(target,selection(next(iter(views().values()))))
    ref,binding=k.prepare(target,sha(target),tmp_path)
    assert sha(ref)==binding['reference_selection_sha256'] and sha(target)==binding['target_selection_sha256']
    save(tmp_path/'receipt.json',dict(selection_sha256=sha(ref)))
    choices=dict(selection_sha256=sha(ref),choices=binding['draft'],target_mutable_aliases=0)
    save(tmp_path/'draft-kernel-choices.json',choices);k.check_owner(tmp_path,binding)
    choices['choices']=dict(choices['choices'],route='packet59');save(tmp_path/'draft-kernel-choices.json',choices)
    with pytest.raises(AssertionError,match='draft kernels changed'):k.check_owner(tmp_path,binding)
    with pytest.raises(AssertionError,match='target selection changed'):k.prepare(target,'0'*64,tmp_path)

def test_cpu_device_command_same_selection_and_shape():
    from types import SimpleNamespace
    a=SimpleNamespace(card=0,draft_rank=1,context=4096,input=P/'build/input',dispatch=P/'dispatch-speed6.json')
    args=(Path('/binary'),a,Path('/capture'),{'model_dir':'/model'},Path('/out'),Path('/selection'),'1'*64,7)
    host=k.command(*args);device=k.command(*args,device=True)
    assert [x for x in device if x!='--authorized-device-window']==host
    assert host[host.index('--memory')+1]=='layer-streaming'
    assert host[host.index('--context')+1]=='4096'
    assert host[host.index('--draft-rank')+1]=='1'

def test_chain_entry_replaces_only_entry_and_kd():
    import queue_runner as q
    original=q.commands(P/'build/device-cards01-b')
    from chain97e import install
    q,w=install()
    for name,cmd in q.commands(P/'build/device-cards01-b').items():
        expected=original[name];i=expected.index(str(P/'window.py'))
        expected[i:i+1]=[str(P/'chain97e.py'),'window']
        assert cmd==expected
    import sys,kd_window97e
    assert sys.modules['draft_window'] is kd_window97e

def test_projection_replay_binds_native_and_target(tmp_path):
    import hashlib
    from build_engine import sha,save
    from kd_projection_replay import validate
    target=tmp_path/'target.json';save(target,selection(next(iter(views().values()))))
    ref,binding=k.prepare(target,sha(target),tmp_path)
    choices=dict(selection_sha256=sha(ref),choices=binding['draft'],target_mutable_aliases=0,sites={'draft':'production'})
    save(tmp_path/'receipt.json',dict(selection_sha256=sha(ref)));save(tmp_path/'draft-kernel-choices.json',choices)
    proof=k.check_owner(tmp_path,binding)
    host=dict(passed=True,selection_sha256=sha(target),reference_selection_sha256=sha(ref),draft_reference=proof)
    rows={'selection.json':target.read_bytes(),'KD/draft-reference-selection.json':ref.read_bytes(),
          'KD/draft-reference-binding.json':json.dumps(binding).encode(),
          'KD/host-reference-identity.json':json.dumps(host).encode(),
          **{f'KD/owner{i}/draft-reference-identity.json':json.dumps(proof).encode() for i in (0,1)}}
    window={'receipts':{n.removeprefix('KD/'):hashlib.sha256(v).hexdigest() for n,v in rows.items() if n.startswith('KD/')}}
    class Evidence:
        def raw(self,key,digest=None):
            raw=rows[key]
            if digest:assert hashlib.sha256(raw).hexdigest()==digest
            return raw
        def read(self,key,digest=None):return json.loads(self.raw(key,digest))
    assert validate(Evidence(),sha(target),window)==sha(ref)
    changed=copy.deepcopy(proof);changed['draft_kernel_choices']['choices']['route']='packet59'
    key='KD/owner1/draft-reference-identity.json';rows[key]=json.dumps(changed).encode()
    window['receipts'][key.removeprefix('KD/')]=hashlib.sha256(rows[key]).hexdigest()
    with pytest.raises(AssertionError):validate(Evidence(),sha(target),window)

def test_extended_validator_changes_only_explicit_kd_native_identity():
    import ast,submission97e as s
    tree=ast.parse(s._text)
    function=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='observed_selection')
    code=compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),'observed_selection','exec')
    ns=dict(require=s.require,selected_hash='target',kd_reference_hash='draft')
    exec(code,ns);check=ns['observed_selection']
    check({'selection_sha256':'draft'},'KD/owner0/receipt.json',mandatory=True)
    for row,path in (({'selection_sha256':'target'},'KD/owner0/receipt.json'),({'selection_sha256':'draft'},'W2m/run/rank1/receipt.json'),({},'KD/owner1/receipt.json')):
        with pytest.raises(ValueError):check(row,path,mandatory=True)
    check({'selection_sha256':'target'},'KD/window.json',mandatory=True)
