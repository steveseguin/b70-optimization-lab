"""Additive HOST_ONLY mini cache integration over frozen P207 generated sources."""
from pathlib import Path
import hashlib,json
P=Path(__file__).resolve().parent;ROOT=P.parents[3];PARENT=P.parent/'packet207-host-paired-projections'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def once(s,a,b):
 assert s.count(a)==1,(a[:100],s.count(a))
 return s.replace(a,b)
def generate():
 pins=json.loads((P/'parent-pins.json').read_text())
 for path,want in pins.items():assert sha(ROOT/path)==want,path
 parent=PARENT/'build/native';main=(parent/'main.cpp').read_text()
 # Keep parent generated code/source immutable; only this local translation unit changes.
 main=main.replace('p207_','p211_').replace('p207::','p211::').replace('p207 chunk','p211 cache').replace('p207 host','p211 host').replace('p207-prefill','p211-prefill')
 main=once(main,'  bool p211_host_chunk2=false,p211_fail_after_row0=false,p211_observe=false;','  bool p211_host_chunk2=false,p211_fail_after_row0=false,p211_observe=false;\n  std::string p211_cache_mode="off";')
 main=once(main,'if(!a.p211_host_chunk2 && !a.p211_fail_after_row0 && !a.p211_observe)return;','if(a.p211_cache_mode=="off" && !a.p211_host_chunk2 && !a.p211_fail_after_row0 && !a.p211_observe)return;')
 main=once(main,'require((!a.p211_fail_after_row0 || a.p211_host_chunk2) && a.mini', 'require((a.p211_cache_mode=="off"||a.p211_cache_mode=="serial"||a.p211_cache_mode=="paired") && a.cache_maintenance=="serial" && (!a.p211_fail_after_row0 || a.p211_host_chunk2) && a.mini')
 main=once(main,'    else if (k == "--p207-host-chunk2") a.p211_host_chunk2=true;\n    else if (k == "--p207-host-fail-after-row0") a.p211_fail_after_row0=true;\n    else if (k == "--p207-host-observe") a.p211_observe=true;', '    else if(k=="--p211-host-cache"){a.p211_cache_mode=value();a.p211_host_chunk2=a.p211_cache_mode=="paired";}\n    else if(k=="--p211-host-observe")a.p211_observe=true;\n    else if(k=="--p211-host-fail-after-row0")a.p211_fail_after_row0=true;')
 main=once(main,'class Engine final : public flash::Backend {', '#ifdef OWN_RT_HOST_ONLY\n#include "'+str(P/'cache_runtime.hpp')+'"\n#endif\nclass Engine final : public flash::Backend {')
 main=once(main,'  std::unique_ptr<p58::Cache> expert_cache;', '  std::unique_ptr<p58::Cache> expert_cache;\n#ifdef OWN_RT_HOST_ONLY\n  std::unique_ptr<p211::MiniCache> mini_cache;\n#endif')
 methods='''#ifdef OWN_RT_HOST_ONLY
  void initialize_mini_cache(){
    require(a.mini&&a.pipeline_mini&&a.cards==1&&a.memory=="resident"&&a.cache_maintenance=="serial","p211 tiny cache admission");drain();
    std::vector<p211::BankSpec> specs;std::set<std::string> expert_names;
    for(const auto&launch:p.launches)if(launch.op=="expert_gate_up"||launch.op=="routed_gemv")for(const auto&name:launch.weights)expert_names.insert(name);
    require(expert_names.size()==12,"p211 twelve planned expert banks");
    for(const auto&name:expert_names){auto id=weights[0].at(name);const auto&t=w.directory.at(name);
      require(t.shape.size()==3&&flash::grid_type(t.grid)==iq3::Type::F32&&t.shape[0]==p.g.experts,"p211 tiny F32 bank");
      unsigned layer=std::stoul(name.substr(4));unsigned projection=name.find("ffn_gate_")!=std::string::npos?0:name.find("ffn_up_")!=std::string::npos?1:2;
      specs.push_back({name,layer,projection,id,size_t(t.bytes)/size_t(p.g.experts)});
    }
    auto allocator=[this](const std::string&name,size_t bytes,Category category,Lifetime life,Memory memory){return allocate(0,name,bytes,category,life,memory);};
    mini_cache=std::make_unique<p211::MiniCache>(dev(0),allocator,specs,p.g.experts,p.g.top);
    for(const auto&s:specs)weights[0][s.name]=mini_cache->table(s.name);
  }
  void retain_mini_routes(const flash::Launch& l){if(mini_cache&&l.op=="expert_gate_up"){
    require(mini_cache->running(),"p211 routed use without frozen interval");
    tail=mini_cache->retain(unsigned(std::stoul(l.label.substr(4))),buffers[0].at(l.inputs[1]).id);
  }}
#endif
'''
 main=once(main,'  void load_expert_bank(const std::string& name) {',methods+'  void load_expert_bank(const std::string& name) {')
 main=once(main,'    if(caching())initialize_cache();','    if(caching())initialize_cache();\n#ifdef OWN_RT_HOST_ONLY\n    if(a.p211_cache_mode!="off")initialize_mini_cache();\n#endif')
 needle='    auto m=a.memory=="resident"?it->second[0]:matrix(l);'
 main=once(main,needle,needle+'''
#ifdef OWN_RT_HOST_ONLY
    if(mini_cache && (l.op=="expert_gate_up"||l.op=="routed_gemv")){
      std::vector<Matrix> selected{m};std::vector<p211::Span> payload{mini_cache->pinned(l.weights[0])};
      if(l.op=="expert_gate_up"){selected.push_back(it->second[1]);payload.push_back(mini_cache->pinned(l.weights[1]));}
      mini_cache->admit();finish(c,p211::indirect_experts(dev(c),selected,l.op=="expert_gate_up",payload,mini_cache->cache_span()),true);return;
    }
#endif''')
 main=once(main,'    auto& site=issue_sites.at(index);int c=site.card;', '''#ifdef OWN_RT_HOST_ONLY
    if(mini_cache)mini_cache->admit();
#endif
    auto& site=issue_sites.at(index);int c=site.card;''')
 main=once(main,'    if(prepared_path){auto index=size_t(&l-p.launches.data());audit_issue_site(index);return issue_site(index,dep);}', '''    if(prepared_path){auto index=size_t(&l-p.launches.data());audit_issue_site(index);auto result=issue_site(index,dep);
#ifdef OWN_RT_HOST_ONLY
      retain_mini_routes(l);
#endif
      return result;
    }''')
 main=once(main,'    if(!devices.empty())dev(0).retire_completed_events();','#ifdef OWN_RT_HOST_ONLY\n    if(mini_cache)mini_cache->consume_route_events();\n#endif\n    if(!devices.empty())dev(0).retire_completed_events();')
 main=main.replace('      dev(c).retire_completed_events();','#ifdef OWN_RT_HOST_ONLY\n      if(mini_cache)mini_cache->consume_route_events();\n#endif\n      dev(c).retire_completed_events();')
 main=once(main,'      e->poisoned = true;','      e->poisoned = true;\n#ifdef OWN_RT_HOST_ONLY\n      if(e->mini_cache){e->mini_cache->poison();try{e->mini_cache->failure_receipt(output);}catch(const std::exception& evidence_error){std::cerr<<"p211 failure evidence: "<<evidence_error.what()<<std::endl;}}\n#endif')
 main=once(main,'  void submission_failed() noexcept override { poisoned = true; }','''  void submission_failed() noexcept override { poisoned = true;
#ifdef OWN_RT_HOST_ONLY
    if(mini_cache)mini_cache->poison();
#endif
  }''')
 main=once(main,'    std::vector<std::string> receipts;\n    for (auto &d : devices)', '''    std::vector<std::string> receipts;
#ifdef OWN_RT_HOST_ONLY
    if(mini_cache){drain();mini_cache->close();}
#endif
    for (auto &d : devices)''')
 main=once(main,'#include "'+str(PARENT/'chunk_runtime.hpp')+'"','#include "'+str(P/'chunk_runtime.hpp')+'"')
 main=once(main,'#include "'+str(PARENT/'pair_proof.hpp')+'"','#include "'+str(P/'indirect_proof.hpp')+'"')
 old='  if(argc==3 && std::string(argv[1])=="--p207-pair-proof") {try{return p211::pair_proof(argv[2]);}catch(const std::exception& ex){std::cerr<<ex.what()<<std::endl;return 1;}}'
 main=once(main,old,'  if(argc==3 && std::string(argv[1])=="--p211-indirect-proof") {try{return p211::indirect_proof(argv[2]);}catch(const std::exception& ex){std::cerr<<ex.what()<<std::endl;return 1;}}')
 main=once(main,'    p58_reset_request(*e,output);','''#ifdef OWN_RT_HOST_ONLY
    const auto p211_reset_before=e->mini_cache?e->mini_cache->normalized():std::string{};
#endif
    p58_reset_request(*e,output);
#ifdef OWN_RT_HOST_ONLY
    if(e->mini_cache)e->mini_cache->request_reset(output,p211_reset_before);
#endif''')
 main=once(main,'      auto token_start=std::chrono::steady_clock::now();e->cache_begin_position();','''      auto token_start=std::chrono::steady_clock::now();e->cache_begin_position();
#ifdef OWN_RT_HOST_ONLY
      const bool p211_single=e->mini_cache&&!e->mini_cache->running();
      if(p211_single){e->drain();e->mini_cache->begin(token_index,1,output);}
#endif''')
 main=once(main,'      e->cache_after_position();','''      e->cache_after_position();
#ifdef OWN_RT_HOST_ONLY
      if(p211_single){e->drain();try{e->mini_cache->end();}catch(...){e->poisoned=true;throw;}}
#endif''')
 old='''        if(host_chunks && i+2<input.size() && i/32==(i+1)/32) {
          require(token_index==i,"p211 host token index");
          e->request_token_index=i;e->checkpoint("p211-prefill-chunk-start");
          host_chunks->run(input,i);++p211_chunk_count;token_index+=2;i+=2;
          e->request_token_index=token_index;e->checkpoint("p211-prefill-chunk-complete");
          continue;
        }'''
 new='''        if(e->mini_cache && i+2<input.size() && i/32==(i+1)/32) {
          require(token_index==i,"p211 host token index");e->drain();e->mini_cache->begin(i,2,output);
          e->request_token_index=i;e->checkpoint("p211-prefill-chunk-start");
          try {
            if(host_chunks){host_chunks->run(input,i);token_index+=2;}
            else {e->mini_cache->row(0);step(input[i],0);e->mini_cache->row(1);step(input[i+1],0);}
            e->drain();e->mini_cache->end();
          }catch(...){e->poisoned=true;e->mini_cache->poison();throw;}
          ++p211_chunk_count;i+=2;e->request_token_index=token_index;e->checkpoint("p211-prefill-chunk-complete");continue;
        }'''
 main=once(main,old,new)
 main=once(main,'      <<",\\\"p211_host_chunk2\\\":"', '      <<",\\\"p211_cache_mode\\\":"<<ownrt::quote(a.p211_cache_mode)<<",\\\"p211_host_chunk2\\\":"')
 main=once(main,'a.p211_host_chunk2?"host-layer-major-paired-projection-chunk2-with-serial-tail":pipeline::CHECKPOINT_PREFILL_PATH','a.p211_cache_mode=="serial"?"host-row-serial-frozen-cache2-with-serial-tail":a.p211_host_chunk2?"host-layer-major-paired-projection-frozen-cache2-with-serial-tail":pipeline::CHECKPOINT_PREFILL_PATH')
 checkpoint=(parent/'checkpoint.hpp').read_text().replace('v1.2+p207','v1.2+p211').replace('packet207-host-paired-projections','packet211-host-engine-cache').replace('experimental-host-paired-projections','experimental-host-engine-cache')
 out=P/'build/native';out.mkdir(parents=True,exist_ok=True);(P/'evidence').mkdir(exist_ok=True)
 outputs={'main.cpp':main,'checkpoint.hpp':checkpoint,'request_front.hpp':(parent/'request_front.hpp').read_text(),'entry-main.cpp':(parent/'entry-main.cpp').read_text()}
 for name,text in outputs.items():(out/name).write_text(text)
 local=('source_overlay.py','host_indirect.hpp','cache_runtime.hpp','chunk_runtime.hpp','indirect_proof.hpp','parent-pins.json')
 receipt={'schema':'packet211.source-overlay.v1','parent_source_sha256':pins,'source_sha256':{str((P/n).relative_to(ROOT)):sha(P/n) for n in local},'outputs':{str((out/n).relative_to(P)):sha(out/n) for n in outputs},'scope':'HOST_ONLY pipeline-mini cache binding and frozen interval; normal default unchanged','device_build_allowed':False}
 (P/'evidence/source-overlay.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n');return receipt
if __name__=='__main__':print(json.dumps(generate(),indent=2))
