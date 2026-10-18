"""Projection regression and strict boundary checks; no native work."""
import copy,json
import pytest
from unittest.mock import patch
from source_decision import P,O,sha
import argument_gate
import selection_gate
import p49_dispatch


def test_complete_actual_arguments():
 row=argument_gate.verify()
 assert len(row['windows'])==11
 assert sum(len(x['argv']) for x in row['windows'])==31
 assert row['k2']['selection']['route']=='route-exp32-rank4'
 assert row['k2']['selection']['recurrence']=='rows4-shared'
 assert row['old_packet124_refusal']['returncode']!=0


@pytest.mark.parametrize('key',['route','recurrence','hc'])
def test_required_kernel_key_is_not_defaulted(key,tmp_path):
 selected=json.loads((P/'selection.json').read_text());del selected['choices'][key]
 (tmp_path/'selection.json').write_text(json.dumps(selected))
 with patch.object(p49_dispatch,'P',tmp_path),pytest.raises(KeyError,match=key):
  p49_dispatch.pin_production_dispatch(tmp_path,{},round3_root=tmp_path)


@pytest.mark.parametrize('value',[
 {'route':'route-exp32-rank4','recurrence':'rows4-shared','hc':'production','other_fusion':'fused'},
 {'route':'route-exp32-rank4','recurrence':'rows4-shared'},
 {'route':'invalid','recurrence':'rows4-shared','hc':'production'},
])
def test_kernel_validator_is_still_strict(value):
 with pytest.raises(ValueError):selection_gate.validate_choices(value)


def test_full_bundle_rejects_unknown_key():
 from packet56_submission import validate_bundle
 bundle=json.loads((P/'bundle-selection.json').read_text());selection=json.loads((P/'selection.json').read_text())
 selection['choices']['unknown']='bad'
 with pytest.raises(ValueError,match='composed choices differ'):validate_bundle(bundle,selection)


def test_readiness_requires_real_argument_gate():
 import verify_ready
 with patch.object(argument_gate,'verify',side_effect=AssertionError('argument gate sentinel')):
  row=verify_ready.evaluate()
 assert row['ready'] is False and 'argument gate sentinel' in row['reason']
