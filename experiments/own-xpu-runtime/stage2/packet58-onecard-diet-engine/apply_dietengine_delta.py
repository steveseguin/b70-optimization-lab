#!/usr/bin/env python3
"""Packet58-onecard-diet-engine native delta: register p58ag_diet::GateUp beside the record gate/up kernel behind the
in-load key `expert_gateup=production|diet`, switched at the drained view boundary like `cache_cap`.

Exact once-replacements on the copied packet58-onecard-cache23 sources (pre-delta snapshot: lineage/p58c23-parent-native).
  --apply   edit native/ in place and write native-dietengine-delta.patch (diff against the snapshot)
  --check   verify every replacement is present exactly once (no write)
The pinned header native/p58ag_diet.hpp (= packet58-onecard-diet-micro/p58ag_diet.hpp byte for byte) is copied, never edited.
The diet dispatch is its OWN TU (native/p58ag_diet_submit.cpp: the production issue<> body verbatim with the diet kernel object),
so p58ag_submit.cpp keeps exactly the record kernel set in its device code (co-compiling the diet in that TU changed the inlining
of the shared decode_tile callee and with it both inherited p58ag_exp kernels' opcode sequences: evidence/kernel-identity-diagnostic.json).
"""
import difflib, hashlib, json, subprocess, sys
from pathlib import Path
P = Path(__file__).resolve().parent
OLD = P / 'lineage/p58c23-parent-native/native'
DIET_HEADER_SHA = '35005ee3b3f3561902b727f9658ea0b08513e58a3a5651aff540fd1fabd66089'
ABS = '/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine'

EDITS = {
 'native/generated/p58ag_submit.cpp': [
  ('integrated::Launch expert(ownrt::Device& d,const std::vector<integrated::Matrix>& m,const Bindings& b,ownrt::Allocation halfcache,bool cached){\n if(m.size()!=2||m[0].type!=Type::IQ2_S||m[0].columns!=2560)throw std::invalid_argument("p58ag expert shape");\n return cached?',
   'integrated::Launch expert(ownrt::Device& d,const std::vector<integrated::Matrix>& m,const Bindings& b,ownrt::Allocation halfcache,bool cached,const std::string& gateup){\n if(m.size()!=2||m[0].type!=Type::IQ2_S||m[0].columns!=2560)throw std::invalid_argument("p58ag expert shape");\n if(gateup!="production"&&gateup!="diet")throw std::invalid_argument("p58ag expert_gateup: unknown");\n // packet58-onecard-diet-engine: the exact instruction diet of the record gate/up kernel (p58ag_diet::GateUp) lives in its own\n // TU (p58ag_diet_submit.cpp) so this TU\x27s device code is exactly the record kernel set; selectable only on the halfcache layout.\n if(gateup=="diet"){if(!cached)throw std::invalid_argument("p58ag expert_gateup=diet requires experts=wide64+halfcache");return expert_diet(d,m,b,halfcache);}\n return cached?'),
 ],
 'native/p58ag_submit.cpp': [
  ('integrated::Launch expert(ownrt::Device& d,const std::vector<integrated::Matrix>& m,const Bindings& b,ownrt::Allocation halfcache,bool cached){\n if(m.size()!=2||m[0].type!=Type::IQ2_S||m[0].columns!=2560)throw std::invalid_argument("p58ag expert shape");\n return cached?',
   'integrated::Launch expert(ownrt::Device& d,const std::vector<integrated::Matrix>& m,const Bindings& b,ownrt::Allocation halfcache,bool cached,const std::string& gateup){\n if(m.size()!=2||m[0].type!=Type::IQ2_S||m[0].columns!=2560)throw std::invalid_argument("p58ag expert shape");\n if(gateup!="production"&&gateup!="diet")throw std::invalid_argument("p58ag expert_gateup: unknown");\n // packet58-onecard-diet-engine: the exact instruction diet of the record gate/up kernel (p58ag_diet::GateUp) lives in its own\n // TU (p58ag_diet_submit.cpp) so this TU\x27s device code is exactly the record kernel set; selectable only on the halfcache layout.\n if(gateup=="diet"){if(!cached)throw std::invalid_argument("p58ag expert_gateup=diet requires experts=wide64+halfcache");return expert_diet(d,m,b,halfcache);}\n return cached?'),
 ],
 'native/generated/p58ag_submit.hpp': [
  ('integrated::Launch expert(ownrt::Device&,const std::vector<integrated::Matrix>&,const p39::Bindings&,ownrt::Allocation,bool cached=true);',
   'integrated::Launch expert(ownrt::Device&,const std::vector<integrated::Matrix>&,const p39::Bindings&,ownrt::Allocation,bool cached=true,const std::string& gateup="production");\nintegrated::Launch expert_diet(ownrt::Device&,const std::vector<integrated::Matrix>&,const p39::Bindings&,ownrt::Allocation); // p58ag_diet_submit.cpp'),
 ],
 'native/p58ag_submit.hpp': [
  ('integrated::Launch expert(ownrt::Device&,const std::vector<integrated::Matrix>&,const p39::Bindings&,ownrt::Allocation,bool cached=true);',
   'integrated::Launch expert(ownrt::Device&,const std::vector<integrated::Matrix>&,const p39::Bindings&,ownrt::Allocation,bool cached=true,const std::string& gateup="production");\nintegrated::Launch expert_diet(ownrt::Device&,const std::vector<integrated::Matrix>&,const p39::Bindings&,ownrt::Allocation); // p58ag_diet_submit.cpp'),
 ],
 'native/generated/main.cpp': [
  # Options: the key, default production (the record path when absent)
  ('  std::string hc="p60fusion",hc_geometry="production",experts="production",other_fusion="production",retirement="production";\n',
   '  std::string hc="p60fusion",hc_geometry="production",experts="production",other_fusion="production",retirement="production";\n  std::string expert_gateup="production"; // packet58-onecard-diet-engine: production|diet (p58ag_diet::GateUp), halfcache gate/up sites only\n'),
  # parser
  ('    else if (k == "--experts") {a.experts=value();require(a.experts=="production"||a.experts=="wide64"||a.experts=="wide64+halfcache","expert dimension");}\n',
   '    else if (k == "--experts") {a.experts=value();require(a.experts=="production"||a.experts=="wide64"||a.experts=="wide64+halfcache","expert dimension");}\n    else if (k == "--expert-gateup") {a.expert_gateup=value();require(a.expert_gateup=="production"||a.expert_gateup=="diet","expert gate/up dimension");}\n'),
  ('  require(a.cache_cap=="18GB"||a.cache_cap=="max"||a.cache_cap=="max23","cache capacity mode");\n',
   '  require(a.cache_cap=="18GB"||a.cache_cap=="max"||a.cache_cap=="max23","cache capacity mode");\n  require(a.expert_gateup=="production"||a.experts=="wide64+halfcache","expert_gateup=diet requires experts=wide64+halfcache");\n'),
  # Engine: counters and the drained-boundary switch (beside the capacity switch)
  ('  uint64_t capacity_reprepares=0;\n',
   '  uint64_t capacity_reprepares=0;\n'
   '  // packet58-onecard-diet-engine: gate/up sites prepared with p58ag_diet::GateUp (diet) or the record kernel (production)\n'
   '  // since the last key switch; the labels name the switching sites. Counted at the p58ag dispatch while preparing.\n'
   '  uint64_t expert_diet_sites=0,expert_production_sites=0;std::vector<std::string> expert_diet_labels;\n'
   '  std::string expert_gateup_for(const flash::Launch& l){if(a.expert_gateup=="diet"){++expert_diet_sites;expert_diet_labels.push_back(l.label);return "diet";}++expert_production_sites;return "production";}\n'
   '  void expert_gateup(const std::string& key) {\n'
   '    require(key=="production"||key=="diet","expert gate/up dimension");\n'
   '    require(key=="production"||a.experts=="wide64+halfcache","expert_gateup=diet requires experts=wide64+halfcache");\n'
   '    require(!maintenance.running,"gate/up switch during position refused");\n'
   '    drain();cache_quiesce(); // the drained view boundary; the kernel takes effect through the boundary re-preparation\n'
   '    a.expert_gateup=key;expert_diet_sites=expert_production_sites=0;expert_diet_labels.clear();\n'
   '  }\n'),
  # dispatch site
  ('p58ag::expert(dev(c),selected,b,halfcache,a.experts=="wide64+halfcache"):p49d::expert(',
   'p58ag::expert(dev(c),selected,b,halfcache,a.experts=="wide64+halfcache",expert_gateup_for(l)):p49d::expert('),
  # help
  ('--draft-rank --experts --first-layer', '--draft-rank --experts --expert-gateup production|diet (default:production) --first-layer'),
  # view boundary: key switched (drained) before the boundary re-preparation; a selected diet must prepare diet sites
  ('record_host_memory(view_output,"before_view_reset");e->bracket_select(view.selection,view.digest,"p60fusion","hc-wide","wide64+halfcache","fused","ordered-foreground");e->cache_mode(view.maintenance);e->cache_capacity(view.capacity);record_host_memory(view_output,"after_view_reset");\n',
   'record_host_memory(view_output,"before_view_reset");e->expert_gateup(view.gateup);e->bracket_select(view.selection,view.digest,"p60fusion","hc-wide","wide64+halfcache","fused","ordered-foreground");e->cache_mode(view.maintenance);e->cache_capacity(view.capacity);record_host_memory(view_output,"after_view_reset");\n'
   '      require(view.gateup!="diet"||e->expert_diet_sites>0,"selected diet prepared no gate/up site");require(view.gateup!="production"||e->expert_diet_sites==0,"production view prepared a diet site");\n'),
  ('",\\"cache_started_empty\\":true"+\n',
   '",\\"cache_started_empty\\":true"+\n        ",\\"expert_gateup\\":"+ownrt::quote(view.gateup)+",\\"expert_diet_sites\\":"+std::to_string(e->expert_diet_sites)+",\\"expert_production_sites\\":"+std::to_string(e->expert_production_sites)+\n'),
 ],
 'native/bracket_table.hpp': [
  ('struct BracketView {std::string label;fs::path selection;std::string digest,maintenance,capacity,hc;bool resident=false;};',
   'struct BracketView {std::string label;fs::path selection;std::string digest,maintenance,capacity,hc;bool resident=false;std::string gateup="production";};'),
  ('  if(a.bracket_inputs.empty())return {{"",a.selection,a.selection_sha256,a.cache_maintenance,a.cache_cap,a.hc,a.resident_lookups}};',
   '  if(a.bracket_inputs.empty())return {{"",a.selection,a.selection_sha256,a.cache_maintenance,a.cache_cap,a.hc,a.resident_lookups,a.expert_gateup}};'),
  ('    require(bool(row>>v.label>>v.selection>>v.digest>>v.maintenance>>v.capacity>>v.hc)&&!(row>>extra),"complete six-field bracket row");',
   '    require(bool(row>>v.label>>v.selection>>v.digest>>v.maintenance>>v.capacity>>v.hc>>v.gateup)&&!(row>>extra),"complete seven-field bracket row");'),
  ('    require(v.capacity=="max"||v.capacity=="max23","cache capacity dimension");\n',
   '    require(v.capacity=="max"||v.capacity=="max23","cache capacity dimension");\n    require(v.gateup=="production"||v.gateup=="diet","expert gate/up dimension");\n'),
  ('    require((a.mini||a.tokens==64)&&views[0].label=="S0"&&views[0].capacity=="max23"&&views[0].hc=="spin-kio","fixed maximum smoke");',
   '    require((a.mini||a.tokens==64)&&views[0].label=="S0"&&views[0].capacity=="max23"&&views[0].gateup=="diet"&&views[0].hc=="spin-kio","fixed maximum smoke");'),
  ('    for(size_t i=0;i<5;++i)require(views[i].label==labels[i]&&views[i].capacity==(i%2?"max23":"max")&&views[i].hc=="spin-kio","max/max23 capacity bracket order");',
   '    for(size_t i=0;i<5;++i)require(views[i].label==labels[i]&&views[i].capacity=="max23"&&views[i].gateup==(i%2?"diet":"production")&&views[i].hc=="spin-kio","max23 production/diet gate-up bracket order");'),
 ],
 'native/preparation_probe.cpp': [
  ('      engine->bracket_select(view.selection,view.digest,"p60fusion","hc-wide","wide64+halfcache","fused","ordered-foreground");\n      engine->cache_mode(view.maintenance);engine->cache_capacity(view.capacity);record_host_memory(root/view.label,"after_view_reset");\n',
   '      engine->expert_gateup(view.gateup);engine->bracket_select(view.selection,view.digest,"p60fusion","hc-wide","wide64+halfcache","fused","ordered-foreground");\n      engine->cache_mode(view.maintenance);engine->cache_capacity(view.capacity);record_host_memory(root/view.label,"after_view_reset");\n'
   '      require(view.gateup!="diet"||engine->expert_diet_sites>0,"selected diet prepared no gate/up site");require(view.gateup!="production"||engine->expert_diet_sites==0,"production view prepared a diet site");\n'
   '      {// packet58-onecard-diet-engine: per-view capture digest of every prepared site and of the gate/up sites (which sites switch)\n'
   '       std::string all,gateup_sites;size_t gateup_count=0;\n'
   '       for(size_t i=0;i<engine->p.launches.size();++i){const auto& l=engine->p.launches[i];const auto& site=engine->issue_sites[i];std::string s=l.label+"|"+l.op+"|";\n'
   '        for(const auto& cmd:site.commands){for(auto id:cmd.ids)s+=std::to_string(id)+",";s+="|"+std::to_string(cmd.argument_bytes.size())+":"+hash(std::vector<uint8_t>(cmd.argument_bytes.begin(),cmd.argument_bytes.end()))+";";}\n'
   '        all+=s+"\\n";if(l.op=="expert_gate_up"){gateup_sites+=s+"\\n";++gateup_count;}}\n'
   '       std::ostringstream o;o<<"{\\"label\\":"<<ownrt::quote(view.label)<<",\\"cache_cap\\":"<<ownrt::quote(view.capacity)<<",\\"expert_gateup\\":"<<ownrt::quote(view.gateup)<<",\\"expert_diet_sites\\":"<<engine->expert_diet_sites<<",\\"expert_production_sites\\":"<<engine->expert_production_sites<<",\\"gateup_launches\\":"<<gateup_count<<",\\"sites\\":"<<engine->p.launches.size()<<",\\"all_sites_sha256\\":"<<ownrt::quote(hash(std::vector<uint8_t>(all.begin(),all.end())))<<",\\"gateup_sites_sha256\\":"<<ownrt::quote(hash(std::vector<uint8_t>(gateup_sites.begin(),gateup_sites.end())))<<",\\"diet_labels\\":[";\n'
   '       for(size_t i=0;i<engine->expert_diet_labels.size();++i)o<<(i?",":"")<<ownrt::quote(engine->expert_diet_labels[i]);o<<"],\\"prepared_so_far\\":"<<transport->captured<<"}\\n";\n'
   '       save(root/view.label/"gateup-capture.json",o.str());}\n'),
 ],
}


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    check = '--check' in sys.argv
    assert sha(P / 'native/p58ag_diet.hpp') == sha(P / 'native/generated/p58ag_diet.hpp') == DIET_HEADER_SHA, 'pinned diet header changed'
    counts = {}
    for rel, edits in EDITS.items():
        path = P / rel
        text = path.read_text()
        applied = all(text.count(new) == 1 for _, new in edits)
        for old, new in edits:
            if check or applied:
                assert text.count(new) == 1 and (old == new or text.count(old) == (1 if old in new else 0)), (rel, old[:80])
            else:
                assert text.count(old) == 1, (rel, old[:100], text.count(old))
                text = text.replace(old, new)
        counts[rel] = len(edits)
        if not check:
            path.write_text(text)
    if check:
        print(json.dumps(dict(passed=True, files=counts)))
        return
    patch = []
    for rel in sorted(set(EDITS) | {'native/p58ag_diet.hpp', 'native/generated/p58ag_diet.hpp', 'native/p58ag_diet_submit.cpp', 'native/generated/p58ag_diet_submit.cpp'}):
        old = (OLD / Path(rel).relative_to('native')).read_text().splitlines(keepends=True) if (OLD / Path(rel).relative_to('native')).exists() else []
        new = (P / rel).read_text().splitlines(keepends=True)
        patch += difflib.unified_diff(old, new, 'a/' + rel, 'b/' + rel)
    (P / 'native-dietengine-delta.patch').write_text(''.join(patch))
    added = sum(1 for l in patch if l.startswith('+') and not l.startswith('+++'))
    removed = sum(1 for l in patch if l.startswith('-') and not l.startswith('---'))
    print(json.dumps(dict(passed=True, files=counts, patch='native-dietengine-delta.patch', added_lines=added, removed_lines=removed)))


if __name__ == '__main__':
    main()
