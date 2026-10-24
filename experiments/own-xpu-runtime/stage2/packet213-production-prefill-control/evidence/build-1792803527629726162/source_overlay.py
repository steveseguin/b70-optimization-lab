"""Additive P198 production future-entry source; public executable always refuses."""
from pathlib import Path
import hashlib,json
P=Path(__file__).resolve().parent;ROOT=P.parents[3];PARENT=P.parent/'packet198-postreply-checkpoint'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def once(text,old,new):
 assert text.count(old)==1,(old[:120],text.count(old))
 return text.replace(old,new)
def generate():
 pins=json.loads((P/'parent-pins.json').read_text())
 for name,want in pins.items():assert sha(ROOT/name)==want,name
 parent=PARENT/'build/native';main=(parent/'main.cpp').read_text()
 main=once(main,'struct Options {','struct Options {\n  bool p213_prefill=false;std::string p213_mode;')
 gate='''static void p213_options(const Options& a){
 require(a.p213_prefill&&(a.p213_mode=="serial-frozen2"||a.p213_mode=="paired-frozen2")&&!a.mini&&!a.pipeline_mini&&!a.pipeline_canary&&!a.canary&&!a.first&&!a.record&&!a.priority_probe&&!a.mtp&&a.draft_capture.empty()&&a.bracket_inputs.empty()&&a.cards==1&&a.rank==-1&&!a.legacy&&a.context==4096&&a.memory=="resident"&&a.miss_path=="zero-copy"&&a.cache_maintenance=="serial"&&a.cache_cap=="max"&&a.cache_bytes==21552729600ull&&a.hc=="p60fusion"&&a.hc_geometry=="hc-wide"&&a.experts=="wide64+halfcache"&&a.other_fusion=="fused"&&a.retirement=="ordered-foreground"&&a.nongemv=="parallel"&&a.gemv=="r5"&&a.retain_steps.ranges.empty(),"p213 future-entry exact production configuration");
}
'''
 main=once(main,'static Options parse(int argc, char **argv) {',gate+'static Options parse(int argc, char **argv) {')
 main=once(main,'    if(k=="--request-front")a.request_front=true;','    if(k=="--p213-future-prefill"){a.p213_prefill=true;a.p213_mode=value();}\n    else if(k=="--request-front")a.request_front=true;')
 main=once(main,'  if (a.canary && !seconds_supplied)','  p213_options(a);\n  if (a.canary && !seconds_supplied)')
 main=once(main,'class Engine final : public flash::Backend {','#include "'+str(P/'cache_interval.hpp')+'"\nclass Engine final : public flash::Backend {')
 main=once(main,'  std::unique_ptr<p58::Cache> expert_cache;','  std::unique_ptr<p58::Cache> expert_cache;\n  std::unique_ptr<p213::CacheInterval> prefill_interval;')
 main=once(main,'    if(!devices.empty())dev(0).retire_completed_events();','    if(prefill_interval)prefill_interval->consume();\n    if(!devices.empty())dev(0).retire_completed_events();')
 assert main.count('      dev(c).retire_completed_events();')==2
 main=main.replace('      dev(c).retire_completed_events();','      if(prefill_interval)prefill_interval->consume();\n      dev(c).retire_completed_events();')
 main=once(main,'    auto& site=issue_sites.at(index);int c=site.card;','    if(prefill_interval)prefill_interval->admit();\n    auto& site=issue_sites.at(index);int c=site.card;')
 main=once(main,'    if(prepared_path){auto index=size_t(&l-p.launches.data());audit_issue_site(index);return issue_site(index,dep);}', '''    if(prepared_path){auto index=size_t(&l-p.launches.data());audit_issue_site(index);auto result=issue_site(index,dep);
      if(prefill_interval&&prefill_interval->running()&&l.op=="expert_gate_up")tail=prefill_interval->retain(unsigned(std::stoul(l.label.substr(4))),buffers[0].at(l.inputs[1]).id);
      return result;
    }''')
 main=once(main,'else cache_epoch=expert_cache->begin_position();','else cache_epoch=p213_cache_begin();')
 main=once(main,'auto epoch=expert_cache->begin_position();expert_cache->finish_position(epoch,true);','auto epoch=p213_cache_begin();p213_cache_finish(epoch,true);')
 main=once(main,'else expert_cache->finish_position(cache_epoch,true);','else p213_cache_finish(cache_epoch,true);')
 main=once(main,'auto plan=expert_cache->prepare(routes);','auto plan=p213_cache_prepare(routes);')
 main=once(main,'expert_cache->commit(plan.epoch,true,true);','p213_cache_commit(plan.epoch,true,true);')
 wrappers='''  uint64_t p213_cache_begin(){return prefill_interval?prefill_interval->begin_position():expert_cache->begin_position();}
  void p213_cache_finish(uint64_t epoch,bool complete){if(prefill_interval)prefill_interval->finish_position(epoch,complete);else expert_cache->finish_position(epoch,complete);}
  p58::Plan p213_cache_prepare(const std::vector<uint32_t>&routes){if(prefill_interval)return prefill_interval->prepare_update(routes);return expert_cache->prepare(routes);}
  void p213_cache_commit(uint64_t epoch,bool copies,bool publication){if(prefill_interval)prefill_interval->commit_update(epoch,copies,publication);else expert_cache->commit(epoch,copies,publication);}
'''
 main=once(main,'  void cache_begin_position(){',wrappers+'  void cache_begin_position(){')
 # Exclusive mutation entry points: no active frozen interval may publish/fill,
 # switch cache configuration or overwrite protected weights/table allocations.
 for signature in ('  void cache_quiesce() {','  void cache_plan_during_position() {','  void cache_mode(const std::string& mode) {','  void cache_capacity(const std::string& cap) {','  void cache_boundary() {','  void publish_cache_table(const std::vector<p58::Entry>& table) {','  void fill_cache(const std::vector<uint32_t>& routes) {','  void stream_layer(int layer,Allocation source){','  void cache_begin_position(){','  void cache_after_position(){'):
  main=once(main,signature,signature+'\n    require(!prefill_interval||!prefill_interval->running(),"p213 cache mutation/ordinary-step during frozen interval");')
 main=once(main,'static void p58_reset_request(Engine& e,const fs::path& destination) {','static void p58_reset_request(Engine& e,const fs::path& destination) {\n  require(!e.prefill_interval||!e.prefill_interval->running(),"p213 request reset during frozen interval");')
 main=once(main,'  void upload(int c, Allocation dst, size_t offset, const void *src, size_t n) {','  void upload(int c, Allocation dst, size_t offset, const void *src, size_t n) {\n    require(!prefill_interval||!prefill_interval->running()||!prefill_interval->protects(dst),"p213 protected payload upload during interval");')
 main=once(main,'  void submission_failed() noexcept override { poisoned = true; }','  void submission_failed() noexcept override { poisoned = true;if(prefill_interval)prefill_interval->poison(); }')
 main=once(main,'    std::vector<std::string> receipts;\n    for (auto &d : devices)','    std::vector<std::string> receipts;\n    if(prefill_interval){drain();prefill_interval->close_after_drain();}\n    for (auto &d : devices)')
 main=once(main,'#include "checkpoint.hpp"','#include "checkpoint.hpp"\n#include "'+str(P/'production_runtime.hpp')+'"')
 main=once(main,'    e->initialize();\n    // Keep a complete owner available','    e->initialize();\n    std::unique_ptr<p213::ProductionChunks> prefill_chunks=std::make_unique<p213::ProductionChunks>(*e);\n    // Keep a complete owner available')
 main=once(main,'    e->prepare_plan();\n    e->prepare_commands();\n    residency_json=','    e->prepare_plan();\n    e->prepare_commands();\n    prefill_chunks->prepare();\n    residency_json=')
 needle='    int next=-1;auto prefill_start=std::chrono::steady_clock::now();'
 main=once(main,needle,'''    auto p213_prefill_range=[&](size_t begin){int result=-1;for(size_t i=begin;i<input.size();){
      if(i+2<input.size()&&i/32==(i+1)/32){require(token_index==i,"p213 logical prompt position");e->request_token_index=i;prefill_chunks->run(input,i);token_index+=2;i+=2;e->request_token_index=token_index;}
      else {result=step(input[i],i+1==input.size()?1:0);++i;}
    }return result;};
'''+needle)
 main=once(main,'for(size_t i=size_t(restored.position);i<input.size();++i)next=step(input[i],i+1==input.size()?1:0);','next=p213_prefill_range(size_t(restored.position));')
 main=once(main,'else for(size_t i=0;i<input.size();++i)next=step(input[i],i+1==input.size()?1:0);','else next=p213_prefill_range(0);')
 main=once(main,'      e->poisoned = true;','      e->poisoned = true;if(e->prefill_interval)e->prefill_interval->poison();')
 checkpoint=(parent/'checkpoint.hpp').read_text().replace('v1.2+p198','v1.2+p213').replace('experimental-postreply-front','experimental-production-prefill')
 checkpoint=once(checkpoint,'CHECKPOINT_PREFILL_PATH="incremental"','CHECKPOINT_PREFILL_PATH="unqualified-production-frozen2-prefill"')
 # Existing CLI/frontend entry object is omitted by the linker recipe. All
 # executable invocations reject; only this externally visible future body links.
 entry='''#define main p213_model_body
#include "main.cpp"
#undef main
extern "C" int p213_future_entry(int argc,char**argv){return p213_model_body(argc,argv);}
int main(int,char**){std::cerr<<"P213 compile-only: all executable invocations disabled; native qualification pending\\n";return 64;}
'''
 out=P/'build/native';out.mkdir(parents=True,exist_ok=True)
 files={'main.cpp':main,'checkpoint.hpp':checkpoint,'request_front.hpp':(parent/'request_front.hpp').read_text(),'entry-main.cpp':entry}
 for name,data in files.items():(out/name).write_text(data)
 receipt={'schema':'packet213.source-overlay.v1','parent_source_sha256':pins,'source_sha256':{str((P/n).relative_to(ROOT)):sha(P/n) for n in ('source_overlay.py','cache_interval.hpp','production_runtime.hpp','production_control.hpp','cache_transition.hpp','parent-pins.json')},'outputs':{str((out/n).relative_to(P)):sha(out/n) for n in files},'entry_disabled':True,'native_execution_allowed':False}
 (P/'evidence/source-overlay.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n');return receipt
if __name__=='__main__':print(json.dumps(generate(),indent=2))
