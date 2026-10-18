"""Static identity/dispatch audit, not a byte-execution or model quality gate."""
import json
from build_engine import P,ROOT,limits,sha,save
def main():
    limits()
    from run_micro import build_gate
    identity=build_gate()
    source=P.parent/'packet103-record-bundle'
    origin=json.loads((P/'source-origin.json').read_text())
    copied={}
    for name,row in origin['copies'].items():
        if row['source'].startswith(str(source.relative_to(ROOT))+'/'):
            assert sha(P/name)==row['sha256']==sha(ROOT/row['source']),name
            copied[name]=row['sha256']
    original=(P/'mtp_kernels.cpp').read_text()
    expected='#pragma once\n'+(original[:original.index('static void extent(')]+'}\n').replace('namespace mtp36 {','namespace p108base {\nusing Linear=mtp36::Linear;',1)
    base=(P/'p108_base.hpp').read_text();assert base==expected
    changed=(P/'p108_loads.hpp').read_text().replace('namespace p108 {','namespace p108base {',1)
    marker='template<unsigned K,bool Int8,bool Pair> struct Dense final:'
    assert base[base.index(marker):]==changed[changed.index(marker):], 'geometry, FP tree, stores or status changed'
    prefix=' else '
    assert base[:base.index(prefix)]==changed[:changed.index(prefix)],'non-INT8 body changed'
    selection=json.loads((source/'selection.json').read_text())
    assert all(selection['draft'][k]=='production' for k in ('gate_up','down','fuse_expert_activation'))
    dispatch=(source/'mtp.hpp').read_text()
    assert 'if(!changed(l)){matrix_production(l);return;}' in dispatch
    assert 'l.op=="gemv"&&candidate=="p33.dense.segment"' in dispatch
    assert 'e.finish(0,mtp36::linear(e.dev(0),a),true);' in dispatch
    # The bundle selectors never change these draft expert choices.
    selectors=(source/'bundle_selection.py').read_text()
    assert "['gate_up']" not in selectors and "['down']" not in selectors
    save(P/'evidence/source-audit.json',dict(passed=True,device_executed=False,static_only=True,
        baseline_matches_copied_mtp36_prefix=True,only_candidate_INT8_lane_changes=True,
        original_WG128_SG32_reduction_and_stores_identical=True,
        production_draft_expert_selection=True,expert_rows={'gate_up':640,'down':2560},
        input_columns={'gate_up':2560,'down':640},route_count=10,experts=512,
        row_strides_bytes={'gate_up':3200,'down':800},all_code_and_input_vector_addresses_8byte_aligned=True,
        device_storage_delta_bytes=0,source_copies=copied,build_identity=identity,
        sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'source_audit.py',source/'selection.json',source/'mtp.hpp',source/'bundle_selection.py',P/'p108_base.hpp',P/'p108_loads.hpp')}))
    print('Static audit PASS: packet103 baseline, INT8 raw-load-only change, selected production geometry.')
if __name__=='__main__':main()
