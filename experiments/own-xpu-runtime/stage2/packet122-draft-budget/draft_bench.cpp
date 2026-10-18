#define main packet122_unused_entry
#include "main.cpp"
#undef main
struct Capture{int token;std::vector<uint8_t> hidden;};
static const fs::path packet=fs::path(__FILE__).parent_path();
int main(int argc,char**argv){std::unique_ptr<Weights>w;std::unique_ptr<Engine>e;std::unique_ptr<mtp36::DraftRuntime>d;fs::path out;std::string error;bool ran=false;std::vector<std::string>teardown;
try{
 require(argc==4&&std::string(argv[1])=="--authorized-device-window"&&std::string(argv[2])=="--output","coordinator admission required");out=argv[3];fs::create_directories(out);
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
 packet26::dispatch.load((packet/"dispatch-speed6.json").string());
 std::ifstream table(packet/"inputs/captures.tsv");require(bool(table),"capture table");std::vector<Capture>captures;int token;std::string file;
 while(table>>token>>file){std::ifstream f(packet/"inputs"/file,std::ios::binary);std::vector<uint8_t>b((std::istreambuf_iterator<char>(f)),{});require(b.size()==20480,"capture extent");captures.push_back({token,std::move(b)});}require(table.eof()&&captures.size()>1,"real captured inputs required");
 Options a;a.rank=1;a.draft_rank=1;a.context=4096;a.cards=2;a.memory="resident";a.timing="class";a.seconds=1200;a.output=out;a.selection=packet/"selection.json";
 {std::ifstream f(a.selection,std::ios::binary);std::vector<uint8_t>b((std::istreambuf_iterator<char>(f)),{});a.selection_sha256=hash(b);}
 a.draft_capture=packet/"inputs/captures.tsv";a.draft_manifest=packet/"mtp-manifest.tsv";
 a.model="/mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS";a.plan=packet/"inputs/plan.tsv";a.auth=packet/"inputs/identity.tsv";
 w=std::make_unique<Weights>(a);auto p=plan(*w,a);e=std::make_unique<Engine>(*w,a,p);
#ifdef OWN_RT_HOST_ONLY
 throw std::runtime_error("full-shape device attribution is not a CPU benchmark");
#else
 ran=true;e->devices.push_back(std::make_unique<ownrt::Device>(ownrt::make_sycl_device(0,true)));
#endif
 e->owned_bytes={0};e->buffers.resize(1);e->weights.resize(1);e->selected.resize(1);e->loaded_layer={-1};e->fp32_sources={0};e->fp32_extents={0};e->submission_card=0;
 e->slab={e->allocate(0,"bounded-copy",4194304,Category::pinned_slab,Lifetime::transfer,Memory::pinned)};
 e->ropes={e->allocate(0,"rope",rope_constants::bytes,Category::weights,Lifetime::process)};
 {std::ifstream f(packet/"rope.bf16",std::ios::binary);std::vector<uint8_t>b((std::istreambuf_iterator<char>(f)),{});require(hash(b)==rope_constants::sha256,"rope identity");e->upload(0,e->ropes[0],0,b.data(),b.size());}
 // Only the immutable prefix is needed. No target layer or service is loaded.
 constexpr size_t rows=80128,rb=3380;auto head=e->allocate(0,"prefix-head",rows*rb,Category::weights,Lifetime::process);e->weights[0]["output.weight"]=head;
 for(size_t row=0;row<rows;row+=256){auto n=std::min(size_t(256),rows-row);auto raw=w->read("output.weight",row*2100,n*2100);auto expanded=iq3::expanded::expand(iq3::Type::Q6_K,raw.data(),raw.size(),2560);require(expanded.size()==n*rb,"prefix stride");e->upload(0,head,row*rb,expanded.data(),expanded.size());}
 d=std::make_unique<mtp36::DraftRuntime>(*e);std::ofstream times(out/"iterations.jsonl");size_t checks=0,filled=0;
 for(unsigned context:{128u,4096u}){
  for(;filled<context-1;++filled){auto&c=captures[filled%captures.size()];d->micro_prefill(c.hidden,c.token);}
  auto initial=d->micro_snapshot();
  for(unsigned iteration=0;iteration<50;++iteration){auto&c=captures[(context+iteration)%captures.size()];std::optional<mtp36::DraftRuntime::MicroSnapshot>expected;
   for(unsigned repeat=0;repeat<2;++repeat){d->micro_restore(initial,context-1);d->micro_inputs(c.hidden,c.token);auto first=e->submitted;d->micro_issue(true);if(e->tail)e->wait(0,e->tail);
    std::map<std::string,uint64_t>classes;uint64_t sum=0,events=0;std::ostringstream event_rows;
#ifndef OWN_RT_HOST_ONLY
    for(auto pending:e->pending)for(auto id=pending.launch.first;id<=pending.launch.last;++id){auto t=e->dev(0).timing(id);require(t.start_ns&&t.end_ns>t.start_ns&&t.end_ns-t.start_ns<=4000000000ull,"bounded event");auto cls=e->class_names.at(pending.cls);auto ns=t.end_ns-t.start_ns;sum+=ns;classes[cls]+=ns;event_rows<<(events?",":"")<<"{\"class\":"<<ownrt::quote(cls)<<",\"start_ns\":"<<t.start_ns<<",\"end_ns\":"<<t.end_ns<<"}";++events;}
#endif
    require(events==e->submitted-first&&events>0,"complete draft event coverage");e->drain();require(d->micro_status()==0,"draft error");auto actual=d->micro_snapshot();
    if(expected){require(actual==*expected,"byte-exact full mutable draft replay");++checks;}else expected=std::move(actual);
    if(repeat==0){times<<"{\"context\":"<<context<<",\"iteration\":"<<iteration<<",\"warmup\":"<<(iteration<10?"true":"false")<<",\"gpu_ns\":"<<sum<<",\"submissions\":"<<events<<",\"classes_ns\":{";bool comma=false;for(auto&[cls,ns]:classes){times<<(comma?",":"")<<ownrt::quote(cls)<<":"<<ns;comma=true;}times<<"},\"events\":["<<event_rows.str()<<"]}\n";times.flush();require(bool(times),"event output");}
   }
  }
  d->micro_restore(initial,context-1);
 }
 require(checks==100,"complete context budget");save(out/"checks.json","{\"byte_exact_pairs\":100,\"contexts\":[128,4096],\"prefix_rows\":80128,\"context_fill\":\"cyclic replay of captured real hidden states and confirmed tokens\"}\n");
}catch(const std::exception&ex){error=ex.what();}
d.reset();if(e){try{teardown=e->shutdown();}catch(const std::exception&ex){error+="; "+std::string(ex.what());ownrt::hold_for_supervisor();}e.reset();}
std::ostringstream receipt;receipt<<"{\"passed\":"<<(error.empty()?"true":"false")<<",\"safe_to_exit\":"<<(!ran||teardown.size()==1?"true":"false")<<",\"device_executed\":"<<(ran?"true":"false")<<",\"diagnostic_only\":true,\"error\":"<<ownrt::quote(error)<<"}";if(!out.empty())save(out/"receipt.json",receipt.str());std::cout<<receipt.str()<<'\n';return error.empty()?0:1;
}
