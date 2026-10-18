#include <cxxabi.h>
#define main packet75_unexecuted_model_entry
#include "main.cpp"
#undef main
int main(int argc,char**argv){std::unique_ptr<Engine> e;std::unique_ptr<mtp36::DraftRuntime> draft;std::function<void()> restore=[]{};try{
 require(argc==8,"view hash rank output negative draft_rank split");Options a;a.context=4096;a.cards=1;a.card=0;a.rank=std::stoi(argv[3]);a.draft_rank=std::stoi(argv[6]);a.target_split=std::stoi(argv[7]);a.mtp=true;a.memory="resident";a.gemv="r5";a.nongemv="parallel";a.selection=argv[1];a.selection_sha256=argv[2];a.output=argv[4];fs::create_directories(a.output);
 a.plan=fs::path("/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet100-down-locality")/"../suite-inputs-20261012/code-review/plan.tsv";a.draft_manifest=fs::path("/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet100-down-locality")/"mtp-manifest.tsv";
 packet26::dispatch.load((fs::path("/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet100-down-locality")/"dispatch-speed6.json").string());Weights w(a);auto p=pipeline::split(plan(w,a),a.rank,false,a.draft_rank,a.target_split);
 require(arithmetic::row_bytes(iq3::Type::Q6_K,2560,6)==3380,"real expanded Q6 head stride");
 const std::string negative=argv[5];
 if(negative=="serial")a.nongemv="serial";
 if(negative=="gemv")a.gemv="r4";
 if(negative=="streaming")a.memory="layer-streaming";
 if(negative=="draft-rank")a.draft_rank=0;
 if(negative=="split")a.target_split=23;
 if(negative=="context")a.context=256;
 if(negative=="legacy")a.legacy=true;
 e=std::make_unique<Engine>(w,a,p);e->initialize();
 if(a.rank==1)p93_target_head=e->dev(0).arena.row(e->weights[0].at("output.weight")).pointer;
 write_plan(a.output/"native-plan.json",p,w,a.cards,a);
 if(negative!="positive"){
  auto found=std::find_if(e->weights[0].begin(),e->weights[0].end(),[](const auto&v){return v.first.ends_with(".ffn_down_exps.weight");});require(found!=e->weights[0].end(),"negative expert missing");
  auto &r=const_cast<std::remove_const_t<std::remove_reference_t<decltype(e->dev(0).arena.row(found->second))>>&>(e->dev(0).arena.row(found->second));
  auto saved=r;auto id=found->second;restore=[&,id,saved]{auto &row=const_cast<std::remove_const_t<std::remove_reference_t<decltype(e->dev(0).arena.row(id))>>&>(e->dev(0).arena.row(id));row=saved;};
  if(negative=="short")--r.bytes;else if(negative=="misaligned")r.pointer=reinterpret_cast<void*>(uintptr_t(r.pointer)+1);else throw std::invalid_argument("negative mode");
 }
 if(a.rank==0)pipeline::banks(*e);else{e->prepare_plan();e->prepare_commands();}
 {pipeline::SpeculativeImage image(*e);if(a.rank==a.draft_rank)draft=std::make_unique<mtp36::DraftRuntime>(*e);
 auto count=[](const std::string& key){unsigned n=0;for(const auto&[name,value]:p80_operations)if(name.find(key)!=std::string::npos)n+=value;return n;};
 const auto& choice=e->sealed_selection.choices;
 require((count("p82rec::Kernel<true>")>0)==(choice.at("recurrence")=="rec-parallel"),"rec-parallel consumer");
 require((count("p82brec::Kernel<true>")>0)==(choice.at("recurrence")=="rec-both-plus"),"rec-both-plus consumer");
 const auto& head=choice.at("head");const bool packed=head!="production";
 require((count("p93::Kernel<2u>")>0)==(a.rank==1&&packed),"transposed head consumer");
 const auto& expert=choice.at("experts");const auto gate=p100::gate_choice(expert);
 require((count("p95exp::Kernel")>0)==(gate=="exp-grid-prefetch"||gate=="exp-grid-prefetch+halfcache"),"prefetch consumer");
 require((count("p90exp::Kernel")>0)==(gate=="exp-halfcache"),"halfcache consumer");
 const bool interleave=expert=="down-interleave"||expert.ends_with("+down-interleave"),tile=p100::tiled(expert);
 require((count("p65::Kernel<(iq3::Type)20, 640u, 64u, false, true, 0u>")>0)==(!interleave&&!tile),"down production consumer");
 require((count("p100::Kernel<1u>")>0)==interleave,"down interleave consumer");
 require((count("p100::Kernel<2u>")>0)==tile,"down transpose consumer");
 const bool table=gate.starts_with("exp-slm")||gate.starts_with("exp-compact");
 require((count("p99::Kernel<(iq3::Type)22, 2560u,")>0)==table,"IQ2 table consumer");
 const bool cached=gate=="exp-halfcache"||gate.ends_with("+halfcache");
 unsigned transformed=0;for(const auto&[name,id]:e->weights[0])if(e->p90_expert_weight(name)){require(e->dev(0).arena.row(id).bytes==size_t(512)*640*840,"real cached IQ2 extent");++transformed;}
 require(transformed==(cached?(a.rank==0?46u:48u):0u),"cached expert allocation count");
 require(count("p60::Kernel<2, true, false, false, false>")>0,"HC wide consumer");
 require((count("p60::Kernel<1, false, false, false, true>")>0)==(choice.at("hc_norm")=="consumer"),"norm fusion consumer");
 require((count("p60::Kernel<0, false, false, false, false>")>0)==(choice.at("hc_norm")!="consumer"),"norm skip consumer");
 require((count("p78route::Kernel")>0)==(choice.at("route")=="route-fast"),"route consumer");
 require(e->reply_report.enabled==(a.rank==1&&choice.at("host_retire")=="reply-first"),"reply-first consumer");
 if(a.rank==1){
  auto id=e->weights[0].at("output.weight");const auto&r=e->dev(0).arena.row(id);
  require(r.bytes==size_t(248320)*(packed?2100:3380),"real selected target-head allocation extent");
  require(count("p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>")>0,"unchanged expanded draft head consumer");
  const std::string expected=head=="head-plane"?"p93::Kernel<1u>":head=="head-transpose"?"p93::Kernel<2u>":"p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>";
  require(p93_head_operations.size()==1&&p93_head_operations.contains(expected),"selected kernel bound to real target head allocation");
 }
 std::ofstream selected(a.output/"selected-operations.txt");for(const auto&[name,value]:p80_operations)selected<<name<<" "<<value<<"\n";selected.close();
 require(e->ordered_retirement==(a.rank==1&&(choice.at("host_retire")=="ordered"||choice.at("host_retire")=="reply-first")),"host retirement selection consumer");
 save(a.output/"census.json",e->dev(0).arena.census());save(a.output/"result.json","{\"passed\":true,\"device_executed\":false,\"rank\":"+std::to_string(a.rank)+",\"postload_device_bytes\":"+std::to_string(e->owned_bytes[0])+",\"expanded_head_stride\":3380}");draft.reset();}
 e->shutdown();e.reset();return 0;
 }catch(const std::exception&x){std::cerr<<x.what()<<'\n';restore();draft.reset();if(e){try{e->shutdown();}catch(...){}e.reset();}return 1;}}
