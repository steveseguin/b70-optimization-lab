"""Unsafe source maps must fail before a plan or new gate can be emitted."""
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from source_decision import ROOT,P,O,sha
from source_gate136 import verify_sources

def test_external_source_refused(tmp_path):
 import tempfile
 with tempfile.TemporaryDirectory(dir=P/'build/tmp',prefix='safe-path-') as d:
  source=tmp_path/'external.json';source.write_text('{}')
  link=Path(d)/'external.json';link.symlink_to(source)
  with pytest.raises(ValueError,match='unsafe identity path'):
   verify_sources({str(link.relative_to(ROOT)):sha(source)})

def test_oracle_never_enters_source_map():
 with pytest.raises(ValueError):
  verify_sources({str((P/'oracle/results/suite-manifest.json').relative_to(ROOT)):sha(P/'oracle/results/suite-manifest.json')})

def test_confirm_plan_reaches_admission_before_screen():
 import confirm136
 with patch.object(confirm136,'admission',side_effect=ValueError('unsafe identity path sentinel')):
  with pytest.raises(ValueError,match='unsafe identity path'):
   confirm136.main(['--index','-1','--output',str(confirm136.output(-1)),'--plan'])

def test_chain_plan_reaches_real_cpu_admission():
 import chain_entry,sys
 with patch.object(sys,'argv',['chain_entry.py','queue','--plan']),patch('source_gate136.oracle'),patch('verify_cpu.verify',side_effect=ValueError('source admission sentinel')):
  with pytest.raises(ValueError,match='source admission sentinel'):chain_entry.main()

def test_native_bank_selection_is_only_delta():
 from bundle_selection import views,selection
 values=list(views().values());control,candidate=map(selection,values)
 assert control['choices']['miss']=='batch' and candidate['choices']['miss']=='banks-batch'
 candidate['choices']['miss']='batch'
 assert candidate==control

def test_chain_commands_embed_libraries_without_shell_setup():
 from chain_entry import embed_environment
 from confirm136 import LIBRARIES
 assert embed_environment(['env','-i','LD_LIBRARY_PATH=','python3'])==['env','-i','LD_LIBRARY_PATH='+LIBRARIES,'python3']
 with pytest.raises(ValueError,match='closed library environment'):embed_environment(['python3'])
