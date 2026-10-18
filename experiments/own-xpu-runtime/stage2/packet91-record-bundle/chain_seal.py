#!/usr/bin/env python3
"""Bind one qualified packet91 composition and selected draft identity to the chain."""
import argparse
import json
import os
from pathlib import Path
from storage import digest
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
B=P/'build'
PARENT=P.parent/'packet56-draft-prefix'
def require(value,message):
    if not value: raise ValueError(message)
def check_map(root,entries):
    require(isinstance(entries,dict) and entries,'empty identity map')
    for name,expected in entries.items():
        require(digest(root/name)==expected,'sealed bytes changed: '+str(root/name))
def checked():
    from bundle_selection import selected, view_path
    choice=selected();view=view_path(choice)
    parent=json.loads((PARENT/'build-receipt.json').read_text())
    build=json.loads((P/'build-device-receipt.json').read_text())
    screen=json.loads((view/'screen-seal.json').read_text())
    require(parent['passed'] and parent['device_admission_ready'],'parent incomplete')
    check_map(ROOT,parent['sources']);check_map(ROOT,screen['sources'])
    check_map(view,screen['artifacts']);check_map(view,screen['gates']);check_map(view,screen['fixture_files'])
    check_map(P,build['artifacts'])
    require(len(set(screen['fixture_files'].values()))==1,'CPU fixture differs')
    artifacts=dict(parent['artifacts_sha256'])
    for name in ('device/own-rt-iq3','gnu-host/own-rt-iq3'):
        artifacts[name]=build['artifacts']['build/'+name]
    check_map(B,artifacts)
    require(artifacts['device/own-rt-iq3']==screen['artifacts']['build/device/own-rt-iq3'],'screen/chain binary differs')
    from shared_oracle import static_binding
    require(static_binding()==parent['shared_oracle'],'oracle changed')
    require(digest(B/'input/input.json')==parent['input_sha256'],'input changed')
    fixture=json.loads((P/'input-fixtures.json').read_text())
    fixture_hashes={name:item['sha256'] for name,item in fixture['files'].items()}
    check_map(B/'fusion-fixtures',fixture_hashes)
    ledger=json.loads((P/'memory-plan.json').read_text())
    from memory_gate import configuration
    admitted=configuration(ledger,4096,choice['draft_rank'],choice['target_split'])
    require([r['target_layers'] for r in admitted['ranks']]==[choice['layer_boundary'],48-choice['layer_boundary']],'memory topology differs')
    cpu=json.loads((P/'cpu-validation.json').read_text())
    require(cpu['passed'] and not cpu['device_executed'], 'CPU validation incomplete')
    check_map(ROOT,cpu['files'])
    sources={**parent['sources'],**screen['sources'],**cpu['files']}
    for path in P.iterdir():
        if path.is_file() and (path.suffix in ('.py','.sh','.hpp','.tsv','.bf16','.patch') or path.suffix=='.json' and path.name not in ('build-receipt.json','submission-pins.json')):
            sources[str(path.relative_to(ROOT))]=digest(path)
    for path in (PARENT/'build-receipt.json',view/'screen-seal.json',P/'calibration/selection.json',P/'calibration/preregistration.json',P/'oracle/suite_check.py'):
        sources[str(path.relative_to(ROOT))]=digest(path)
    fields=('passed','device_executed','arithmetic','parent_commit','shared_oracle','oracle_inputs_sha256','oracle_binary_sha256','official_manifest_sha256','input_sha256','p33_linked_fixture_host_sha256','p49_qsa_fixture_host_sha256','p49b_expert_fixture_host_sha256','p49c_fixture_host_sha256','p49d_fixture_host_sha256','nongemv_fixture_host_sha256_by_context','draft_prefix')
    from packet56_submission import SPIN,HC_FUSION
    from draft_identity import identity
    parent=dict(parent,draft_prefix=identity(choice))
    return dict({k:parent[k] for k in fields},schema='packet91.chain-cpu-seal.v1',runtime_revision=json.loads((P/'runtime-revision.json').read_text())['runtime_revision'],parent_seal_sha256=digest(PARENT/'build-receipt.json'),screen_seal_sha256=choice['screen_seal_sha256'],controller_spin=SPIN,hc_fusion=HC_FUSION,bundle_selection=choice,memory_plan=ledger,selection=dict(selection_sha256=choice['selection_sha256'],choices=json.loads((P/'selection.json').read_text())['choices']),fixture_inputs_sha256=fixture_hashes,sources=sources,artifacts_sha256=artifacts,original_artifacts_sha256=artifacts,device_admission_ready=True,scope=dict(qualification='CPU only; complete coordinator chain pending',admission='shared v4-lanes d5b060769: screen and exactness lane scope; whole host for timing; unchanged drain/hold-lane-B protocol'))
def verify():
    row=json.loads((P/'build-receipt.json').read_text())
    require(row==checked(),'chain source/build/selection binding changed')
    return row
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--verify',action='store_true');parser.parse_args()
    require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19 required')
    verify();print(json.dumps(dict(passed=True,device_executed=False)))
if __name__=='__main__':main()
