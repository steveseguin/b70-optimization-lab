"""Deterministic additive overlay of frozen p198; never changes parent sources."""
from pathlib import Path
import hashlib,json
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
PARENT=P.parent/'packet198-postreply-checkpoint'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def replace_once(text,old,new):
 assert text.count(old)==1,(old[:100],text.count(old))
 return text.replace(old,new)
def generate():
 parent=PARENT/'build/native'
 assert sha(parent/'main.cpp')=='1e7c5f1b6ab19f909fbd03165ead029ea7331a27810b7a6e97961d9f32039581'
 assert sha(parent/'checkpoint.hpp')=='3668ee9f15d460eecd020574ae8f941e2cc2e862440facb30cfe42665d90f02c'
 paths=[parent/n for n in ('main.cpp','checkpoint.hpp','request_front.hpp','entry-main.cpp')]
 sources={str(x.relative_to(ROOT)):sha(x) for x in paths}
 main=(parent/'main.cpp').read_text()
 main=replace_once(main,'struct Options {','struct Options {\n  bool p206_host_chunk2=false,p206_fail_after_row0=false,p206_observe=false;')
 gate='''static void p206_validate_options(const Options& a) {
  if(!a.p206_host_chunk2 && !a.p206_fail_after_row0 && !a.p206_observe)return;
#ifndef OWN_RT_HOST_ONLY
  throw std::runtime_error("p206 chunk2 is HOST_ONLY only");
#else
  require((!a.p206_fail_after_row0 || a.p206_host_chunk2) && a.mini && a.pipeline_mini && a.memory=="resident" && a.cards==1 && a.rank==-1 && !a.legacy && !a.mtp && a.draft_capture.empty() && !a.priority_probe && !a.record && !a.first && !a.canary && !a.pipeline_canary && a.bracket_inputs.empty() && a.nongemv=="parallel" && a.context<=128 && a.retain_steps.ranges.empty(),
    "p206 chunk2 requires HOST_ONLY mini pipeline resident single-owner mode");
#endif
}
'''
 main=replace_once(main,'static Options parse(int argc, char **argv) {',gate+'static Options parse(int argc, char **argv) {')
 # The guarded branches precede parse's normal mini branch; no payload access.
 needle='    else if (k == "--pipeline-mini") a.pipeline_mini=true;'
 main=replace_once(main,needle,needle+'\n    else if (k == "--p206-host-chunk2") a.p206_host_chunk2=true;\n    else if (k == "--p206-host-fail-after-row0") a.p206_fail_after_row0=true;\n    else if (k == "--p206-host-observe") a.p206_observe=true;')
 main=replace_once(main,'  if (a.canary && !seconds_supplied)', '  p206_validate_options(a);\n  if (a.canary && !seconds_supplied)')
 main=replace_once(main,'      e->timings.flush();e->prefill_timings.flush();return a.first?-1:result;','''#ifdef OWN_RT_HOST_ONLY
      if(a.p206_observe && fixture_step==0)p206::record_state(*e,"serial-prefill-state.jsonl",token_index-1,1);
#endif
      e->timings.flush();e->prefill_timings.flush();return a.first?-1:result;''')
 main=replace_once(main,'#include "checkpoint.hpp"','#include "checkpoint.hpp"\n#include "'+str(P/'chunk_runtime.hpp')+'"')
 needle='    e->initialize();\n    // Keep a complete owner available'
 main=replace_once(main,needle,'''    e->initialize();
#ifdef OWN_RT_HOST_ONLY
    std::unique_ptr<p206::Chunks> host_chunks;
    if(a.p206_host_chunk2)host_chunks=std::make_unique<p206::Chunks>(*e);
#endif
    // Keep a complete owner available''')
 needle='    e->prepare_plan();\n    e->prepare_commands();\n    residency_json='
 main=replace_once(main,needle,'''    e->prepare_plan();
    e->prepare_commands();
#ifdef OWN_RT_HOST_ONLY
    if(host_chunks)host_chunks->prepare();
#endif
    residency_json=''')
 needle='    int next=-1;auto prefill_start=std::chrono::steady_clock::now();'
 replacement='''    size_t p206_chunk_count=0;
    auto prefill_range = [&](size_t begin) {
      int result=-1;
      for(size_t i=begin;i<input.size();) {
#ifdef OWN_RT_HOST_ONLY
        if(host_chunks && i+2<input.size() && i/32==(i+1)/32) {
          require(token_index==i,"p206 host token index");
          e->request_token_index=i;e->checkpoint("p206-prefill-chunk-start");
          host_chunks->run(input,i);++p206_chunk_count;token_index+=2;i+=2;
          e->request_token_index=token_index;e->checkpoint("p206-prefill-chunk-complete");
          continue;
        }
#endif
        result=step(input[i],i+1==input.size()?1:0);++i;
      }
      return result;
    };
    int next=-1;auto prefill_start=std::chrono::steady_clock::now();'''
 main=replace_once(main,needle,replacement)
 main=replace_once(main,'for(size_t i=size_t(restored.position);i<input.size();++i)next=step(input[i],i+1==input.size()?1:0);','next=prefill_range(size_t(restored.position));')
 main=replace_once(main,'else for(size_t i=0;i<input.size();++i)next=step(input[i],i+1==input.size()?1:0);','else next=prefill_range(0);')
 main=replace_once(main,'      prefill_ms,prefill_first,prefill_tokens);','      prefill_ms,prefill_first,prefill_tokens,a.p206_host_chunk2?"host-layer-major-chunk2-with-serial-tail":pipeline::CHECKPOINT_PREFILL_PATH);')
 main=replace_once(main,'      <<",\\\"tokens\\\":[";', '      <<",\\\"p206_host_chunk2\\\":"<<(a.p206_host_chunk2?"true":"false")<<",\\\"p206_chunk_count\\\":"<<p206_chunk_count<<",\\\"tokens\\\":[";')
 checkpoint=(parent/'checkpoint.hpp').read_text().replace('v1.2+p198','v1.2+p206').replace('packet198-postreply-checkpoint','packet206-host-engine-chunk').replace('experimental-postreply-front','experimental-host-prefill-chunk').replace('experimental postreply checkpoint front; no device qualification','experimental HOST_ONLY mini prefill chunk; no device qualification')
 checkpoint=replace_once(checkpoint,'double prefill_ms,size_t prefill_first,size_t prefill_tokens) {','double prefill_ms,size_t prefill_first,size_t prefill_tokens,const char* prefill_path=CHECKPOINT_PREFILL_PATH) {')
 assert checkpoint.count('ownrt::quote(CHECKPOINT_PREFILL_PATH)')==2
 checkpoint=checkpoint.replace('ownrt::quote(CHECKPOINT_PREFILL_PATH)','ownrt::quote(prefill_path)')
 out=P/'build/native';out.mkdir(parents=True,exist_ok=True);(P/'evidence').mkdir(exist_ok=True)
 outputs={'main.cpp':main,'checkpoint.hpp':checkpoint,'request_front.hpp':(parent/'request_front.hpp').read_text(),'entry-main.cpp':(parent/'entry-main.cpp').read_text()}
 for name,text in outputs.items():(out/name).write_text(text)
 row={'schema':'packet206.source-overlay.v1','parent_source_sha256':sources,'source_sha256':{str(x.relative_to(ROOT)):sha(x) for x in [P/'source_overlay.py',P/'chunk_runtime.hpp']},'outputs':{str((out/n).relative_to(P)):sha(out/n) for n in outputs},'scope':'HOST_ONLY synthetic pipeline-mini opt-in; serial default unchanged','device_build_allowed':False}
 (P/'evidence/source-overlay.json').write_text(json.dumps(row,indent=2,sort_keys=True)+'\n');return row
if __name__=='__main__':print(json.dumps(generate(),indent=2,sort_keys=True))
