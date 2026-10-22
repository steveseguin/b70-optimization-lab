#!/usr/bin/env python3
"""Apply the packet183 S1 dispatch/selection delta to the copied packet153 sources.

Exact-once text replacements; refuses if an anchor is missing or ambiguous, and
refuses to run twice. Files touched (all inside this packet):
  v5/native-src/main.cpp   include; Engine::dense_metadata(); load-time census
                           of every expanded Q6_K tensor (sticky refusal on any
                           non-finite d or word mismatch, receipt
                           dense-scales-census.json); three dispatch sites
                           (p33.dense.segment Q6_K, p49c attention_combine Q6_K
                           K6144, p49d small.ffn.q6) choose p183:: when the
                           selection says dense_scales=metadata.
  v5/native-src/mtp.hpp    draft head (p33.dense.segment on the resident target
                           head rows) takes the same switch.
  v5/native/engine_bracket.hpp  the one-load switch key is dense_scales
                           (expanded|metadata); snapshot_host is fixed to
                           production in every view.
  native-base/.../p49d_submit.cpp  registers dense_scales (14 choice keys) and
                           keeps it out of the packet56 target check.
Writes s1-delta.patch (diff against packet153's bytes) and lineage/s1-delta.json.
"""
import difflib, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SRC153 = HERE.parent / 'packet153-snapshot-host'
NB = 'native-base/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro'
CHK = '/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/build/checked/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro'
MARK = '// packet183-s1'


def once(text, old, new, what):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'anchor count {n} for {what}: {old[:100]!r}')
    return text.replace(old, new, 1)


EDITS = {
 'v5/native-src/main.cpp': [
  ('include',
   '#include "' + CHK + '/p105_submit.hpp"\n',
   '#include "' + CHK + '/p105_submit.hpp"\n#include "' + CHK + '/s1_submit.hpp" ' + MARK + '\n'),
  ('dense_metadata',
   '  bool split_head()const {return head_choice()=="head-split-compute"||head_choice()=="head-split-bcs";}\n',
   '  bool split_head()const {return head_choice()=="head-split-compute"||head_choice()=="head-split-bcs";}\n'
   '  ' + MARK + ': process-wide dense scale source of the sealed/bracket selection.\n'
   '  bool dense_metadata()const {auto i=sealed_selection.choices.find("dense_scales");return i!=sealed_selection.choices.end()&&i->second=="metadata";}\n'
   '  p183::Census dense_census;size_t dense_census_tensors=0;\n'
   '  void write_dense_census(){save(a.output/"dense-scales-census.json","{\\"schema\\":\\"packet183.dense-scales-census.v1\\",\\"passed\\":"+std::string(dense_census.nonfinite||dense_census.mismatch?"false":"true")+",\\"rank\\":"+std::to_string(a.rank)+",\\"tensors\\":"+std::to_string(dense_census_tensors)+",\\"rows\\":"+std::to_string(dense_census.rows)+",\\"blocks\\":"+std::to_string(dense_census.blocks)+",\\"groups\\":"+std::to_string(dense_census.groups)+",\\"nonfinite_d\\":"+std::to_string(dense_census.nonfinite)+",\\"word_mismatches\\":"+std::to_string(dense_census.mismatch)+"}");}\n'),
  ('census',
   '        auto expanded=hccache?p90::hc_repack(raw.data(),raw.size()):iq3::expanded::expand(type,raw.data(),raw.size(),t.shape[1]);\n'
   '        upload(c,id,row*er,expanded.data(),expanded.size());\n'
   '      }\n'
   '      return;\n',
   '        auto expanded=hccache?p90::hc_repack(raw.data(),raw.size()):iq3::expanded::expand(type,raw.data(),raw.size(),t.shape[1]);\n'
   '        if(type==iq3::Type::Q6_K&&!hccache){auto census=p183::census_q6(expanded.data(),nr,t.shape[1]);p183::census_add(dense_census,census); ' + MARK + '\n'
   '          if(census.nonfinite||census.mismatch){write_dense_census();require(false,"p183 dense-scales census refused: "+name);}}\n'
   '        upload(c,id,row*er,expanded.data(),expanded.size());\n'
   '      }\n'
   '      if(type==iq3::Type::Q6_K&&!hccache){++dense_census_tensors;write_dense_census();} ' + MARK + '\n'
   '      return;\n'),
  ('small',
   'name=="small.ffn.q6"?p49d::small(dev(c),name,members,variants):',
   'name=="small.ffn.q6"?(dense_metadata()?p183::small(dev(c),name,members,variants):p49d::small(dev(c),name,members,variants)):'),
  ('attention',
   ':round2?p49c::dense_submit(dev(c),m,kind,b):',
   ':round2?((dense_metadata()&&kind==p39::Kind::attention_combine&&m.type==iq3::Type::Q6_K&&m.columns==6144)?p183::attention(dev(c),m,b):p49c::dense_submit(dev(c),m,kind,b)):'),
  ('segment',
   '    if((candidate.starts_with("p28.")||candidate.starts_with("p29.")||candidate.starts_with("p33.")||candidate.starts_with("p42."))&&!a.mini){\n',
   '    if(candidate=="p33.dense.segment"&&!a.mini&&l.op=="gemv"&&m.type==iq3::Type::Q6_K&&dense_metadata()&&arithmetic::is_expanded(variant(l))){ ' + MARK + '\n'
   '      finish(c,p183::segment(dev(c),{m},false,variant(l)),true);return;\n'
   '    }\n'
   '    if((candidate.starts_with("p28.")||candidate.starts_with("p29.")||candidate.starts_with("p33.")||candidate.starts_with("p42."))&&!a.mini){\n'),
 ],
 'v5/native-src/mtp.hpp': [
  ('draft-head',
   '    e.finish(0,head_candidate.starts_with("p33.")?p33::submit(e.dev(0),{m},head_candidate,false,head_variant):p29::submit(e.dev(0),{m},head_candidate,false,head_variant),true);return;\n',
   '    if(head_candidate=="p33.dense.segment"&&m.type==iq3::Type::Q6_K&&e.dense_metadata()&&arithmetic::is_expanded(head_variant)&&e.weights[0].count("output.weight")&&w.id==e.weights[0].at("output.weight")){e.finish(0,p183::segment(e.dev(0),{m},false,head_variant),true);return;} ' + MARK + '\n'
   '    e.finish(0,head_candidate.starts_with("p33.")?p33::submit(e.dev(0),{m},head_candidate,false,head_variant):p29::submit(e.dev(0),{m},head_candidate,false,head_variant),true);return;\n'),
 ],
 'v5/native/engine_bracket.hpp': [
  ('switch-key',
   '      if(key!="snapshot_host")\n',
   '      if(key!="dense_scales") ' + MARK + '\n'),
  ('domains',
   '      domain(selection->choices,"snapshot_host",{"production","static"});\n',
   '      domain(selection->choices,"snapshot_host",{"production"}); ' + MARK + '\n'
   '      domain(selection->choices,"dense_scales",{"expanded","metadata"});\n'),
 ],
 NB + '/p49d_submit.cpp': [
  ('resolve',
   ' if(cls=="snapshot_host"&&(choice=="production"||choice=="static"))return production;\n',
   ' if(cls=="snapshot_host"&&(choice=="production"||choice=="static"))return production;\n'
   ' if(cls=="dense_scales"&&(choice=="expanded"||choice=="metadata"))return production; ' + MARK + '\n'),
  ('count', 'values.size()!=13', 'values.size()!=14'),
  ('target', 'target_values.erase("snapshot_host");', 'target_values.erase("snapshot_host");target_values.erase("dense_scales");'),
 ],
}


def main():
    patches, rows = [], []
    for rel, edits in EDITS.items():
        path = HERE / rel
        text = path.read_text()
        if MARK in text:
            raise SystemExit('already applied: ' + rel)
        before = text
        for what, old, new in edits:
            text = once(text, old, new, rel + ':' + what)
        path.write_text(text)
        src_rel = rel.replace('packet183-twocard-s1-micro', 'packet153-snapshot-host')
        orig = (SRC153 / src_rel).read_text().replace('packet153-snapshot-host', 'packet183-twocard-s1-micro')
        if orig != before:
            raise SystemExit('copied source differs from packet153 after identity rewrite: ' + rel)
        patches.append(''.join(difflib.unified_diff(orig.splitlines(True), text.splitlines(True), 'packet153/' + src_rel, 'packet183/' + rel)))
        rows.append({'name': rel, 'edits': [e[0] for e in edits], 'after_digest': hashlib.sha256(text.encode()).hexdigest()})
    for new in ('s1_lanes.hpp', 's1_submit.hpp', 's1_submit.cpp'):
        text = (HERE / NB / new).read_text()
        patches.append(''.join(difflib.unified_diff([], text.splitlines(True), '/dev/null', 'packet183/' + NB + '/' + new)))
        rows.append({'name': NB + '/' + new, 'edits': ['new file'], 'after_digest': hashlib.sha256(text.encode()).hexdigest()})
    (HERE / 's1-delta.patch').write_text(''.join(patches))
    (HERE / 'lineage/s1-delta.json').write_text(json.dumps({'schema': 'packet183.s1-delta.v1', 'device_executed': False,
        'base': 'packet153-snapshot-host sources after the packet183 identity rewrite', 'changed': rows,
        'unchanged_inherited_objects': 'every packet136 parent object linked by packet153 is linked unchanged; S1 kernels are new names in a new TU'}, indent=1) + '\n')
    print('applied', len(rows), 'files; patch', len(''.join(patches).splitlines()), 'lines')


if __name__ == '__main__':
    main()
