#define main packet75_unexecuted_model_entry
#include "main.cpp"
#undef main
int main(int argc,char**argv){std::unique_ptr<Engine> e;std::unique_ptr<mtp36::DraftRuntime> draft;try{
 require(argc==8,"view hash rank output negative draft_rank split");Options a;a.context=4096;a.cards=1;a.card=0;a.rank=std::stoi(argv[3]);a.draft_rank=std::stoi(argv[6]);a.target_split=std::stoi(argv[7]);a.mtp=true;a.memory="resident";a.gemv="r5";a.nongemv="parallel";a.selection=argv[1];a.selection_sha256=argv[2];a.output=argv[4];fs::create_directories(a.output);
 a.plan=fs::path("/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet79-draft-rank0")/"../suite-inputs-20261012/code-review/plan.tsv";a.draft_manifest=fs::path("/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet79-draft-rank0")/"mtp-manifest.tsv";
 packet26::dispatch.load((fs::path("/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet79-draft-rank0")/"dispatch-speed6.json").string());Weights w(a);auto p=pipeline::split(plan(w,a),a.rank,false,a.draft_rank,a.target_split);
 require(arithmetic::row_bytes(iq3::Type::Q6_K,2560,6)==3380,"real expanded Q6 head stride");
 e=std::make_unique<Engine>(w,a,p);e->initialize();
 if(std::string(argv[5])=="negative"&&a.rank==1){auto id=e->weights[0].at("output.weight");auto &r=const_cast<std::remove_const_t<std::remove_reference_t<decltype(e->dev(0).arena.row(id))>>&>(e->dev(0).arena.row(id));r.bytes-=2100;}
 if(a.rank==0)pipeline::banks(*e);else{e->prepare_plan();e->prepare_commands();}
 {pipeline::SpeculativeImage image(*e);if(a.rank==a.draft_rank)draft=std::make_unique<mtp36::DraftRuntime>(*e);
 save(a.output/"census.json",e->dev(0).arena.census());save(a.output/"result.json","{\"passed\":true,\"device_executed\":false,\"rank\":"+std::to_string(a.rank)+",\"postload_device_bytes\":"+std::to_string(e->owned_bytes[0])+",\"expanded_head_stride\":3380}");draft.reset();}
 e->shutdown();e.reset();return 0;
 }catch(const std::exception&x){std::cerr<<x.what()<<'\n';draft.reset();if(e){try{e->shutdown();}catch(...){}e.reset();}return 1;}}
