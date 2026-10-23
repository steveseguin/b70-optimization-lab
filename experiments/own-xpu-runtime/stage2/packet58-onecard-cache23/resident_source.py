"""Explicit host-only delta to the checked packet58p/58j entry and 58r bracket."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent

def integrate(text):
    from native_source import once
    text='#include '+json.dumps(str(P/'native/resident_lookup.hpp'))+'\n'+text
    text=once(text,'  fs::path inputs, output, model, plan, auth, oracle, suite_inputs, bracket_inputs;',
              '  bool resident_lookups=false;\n  fs::path inputs, output, model, plan, auth, oracle, suite_inputs, bracket_inputs;')
    text=once(text,'    else if (k == "--bracket-inputs")',
              '    else if (k == "--resident-lookups") a.resident_lookups=true;\n    else if (k == "--bracket-inputs")')
    start=text.index('  std::map<std::string,std::unique_ptr<iq3::Slice>> lookup_mappings;')
    end=text.index('  Weights(const Options &a)',start)
    text=text[:start]+'''  std::string residency="{\\"enabled\\":false}";
#include '''+json.dumps(str(P/'native/resident_weights.hpp'))+'\n'+text[end:]
    start=text.index('    if(auto it=lookup_mappings.find(name)');end=text.index('    auto slice = model->slice(name, off, n);',start)
    text=text[:start]+text[end:]
    text=once(text,'    if (mini) {\n      auto &b = synthetic.at(name);',
              '''    if(use_resident_lookups) {
      if(auto it=resident_lookups.find(name);it!=resident_lookups.end()) {
        const auto* data=it->second->slice(off,n);return {data,data+n};
      }
      require(name!="token_embd.weight"&&name!="per_layer_token_embd.weight","resident lookup missing; no file fallback");
    }
    if (mini) {
      auto &b = synthetic.at(name);''')
    # Normal and bracket loads allocate once, before engine work. Mini plans
    # synthesize the SAME lookup tensors here, so full-output CPU tests use it.
    text=once(text,'    e->initialize();',
              '''    e->initialize();
    // Keep a complete owner available for the normal drain-on-error proof.
    if(a.resident_lookups||!a.bracket_inputs.empty())w->load_resident_lookups();
    w->use_resident_lookups=a.resident_lookups;''')
    text=once(text,'    for(const auto& view:bracket_views) {',
              '    for(const auto& view:bracket_views) {\n    w->use_resident_lookups=view.resident;')
    text=text.replace('residency_json=w->residency; // sparse host lookups; do not touch all 28.8 GB PLE pages','residency_json=w->residency;')
    text=once(text,'      save(view_output/"boundary.json",',
              '''      save(view_output/"lookup-backing.json","{\\"resident\\":"+std::string(view.resident?"true":"false")+",\\"copies\\":"+w->residency+"}\\n");
      save(view_output/"boundary.json",''')
    # Localize faults to prepare_token, retaining original whole-token counters.
    text=once(text,'      {auto t0=std::chrono::steady_clock::now();e->prepare_token(token);e->prepare_ms=Engine::ms(t0);}',
              '''      struct rusage prepare_before{},prepare_after{};
      getrusage(RUSAGE_SELF,&prepare_before);
      {auto t0=std::chrono::steady_clock::now();e->prepare_token(token);e->prepare_ms=Engine::ms(t0);}
      getrusage(RUSAGE_SELF,&prepare_after);''')
    text=once(text,'<<",\\"prepare_ms\\":"<<e->prepare_ms',
              '<<",\\"prepare_major_faults\\":"<<prepare_after.ru_majflt-prepare_before.ru_majflt<<",\\"prepare_minor_faults\\":"<<prepare_after.ru_minflt-prepare_before.ru_minflt<<",\\"resident_lookups\\":"<<(w->use_resident_lookups?"true":"false")<<",\\"prepare_ms\\":"<<e->prepare_ms')
    return text
