// Native CPU oracle: share the frozen runtime's graph, reductions and libm.
// The included host adapter uses ordinary malloc/memcpy, never an accelerator.
#ifndef OWN_RT_HOST_ONLY
#error This oracle must only be built with OWN_RT_HOST_ONLY
#endif
#define main packet13_unused_main
#include "../../own-xpu-runtime/stage2/packet13-integrate/main.cpp"
#undef main
#include <numeric>
#include <iomanip>

int main(int argc,char** argv) {
  // INPUT_DIR OUTPUT_DIR SECONDS TOKENS [first-layer]
  std::unique_ptr<Weights> weights;
  std::unique_ptr<Engine> engine;
  std::vector<int> generated;
  std::string error, status="running";
  std::vector<double> costs;
  std::vector<std::string> steps;
  fs::path out;
  bool created_output=false;
  auto started=std::chrono::steady_clock::now();
  double prefill=0;
  auto persist=[&] {
    std::ostringstream r;r<<std::setprecision(12);
    r<<"{\"schema\":\"iq3-runtime-cpu-oracle.v1\",\"arithmetic\":"<<ownrt::quote(arithmetic::version)
      <<",\"status\":"<<ownrt::quote(status)<<",\"error\":"<<ownrt::quote(error)
      <<",\"device_executed\":false,\"prefill_seconds\":"<<prefill
      <<",\"seconds\":"<<Engine::ms(started)/1000<<",\"tokens\":[";
    for(size_t i=0;i<generated.size();++i)r<<(i?",":"")<<generated[i];
    r<<"],\"steps\":[";for(size_t i=0;i<steps.size();++i)r<<(i?",":"")<<steps[i];
    r<<"],\"decode_seconds_per_token\":";
    if(costs.size()>1)r<<std::accumulate(costs.begin()+1,costs.end(),0.)/(costs.size()-1);else r<<"null";
    rusage usage{};getrusage(RUSAGE_SELF,&usage);
    r<<",\"max_rss_kib\":"<<usage.ru_maxrss<<",\"model_bytes_read\":"<<(weights?weights->read_bytes:0)<<"}\n";
    save(out/"result.json.tmp",r.str());fs::rename(out/"result.json.tmp",out/"result.json");
  };
  try {
    require(argc==5 || argc==6,"INPUT OUTPUT SECONDS TOKENS [first-layer]");
    require(getpriority(PRIO_PROCESS,0)==19,"nice 19");
    require(getenv("OMP_NUM_THREADS") && std::string(getenv("OMP_NUM_THREADS"))=="8","eight numeric threads");
    rlimit limit{38'000'000'000ull,38'000'000'000ull};require(setrlimit(RLIMIT_AS,&limit)==0,"address cap");
    Options a;a.inputs=fs::path(argv[1])/"tokens.txt";a.plan=fs::path(argv[1])/"plan.tsv";
    a.auth=fs::path(argv[1])/"identity.tsv";a.output=out=argv[2];
    a.seconds=std::stoi(argv[3]);a.tokens=std::stoi(argv[4]);a.context=192;
    a.first=argc==6;require(!a.first || std::string(argv[5])=="first-layer","mode");
    require(a.seconds>0 && a.seconds<=10800 && a.tokens>0 && a.tokens<=64,"bounds");
    require(getenv("IQ3_MODEL_DIR"),"model directory");a.model=getenv("IQ3_MODEL_DIR");
    require(!fs::exists(out),"new output required");created_output=fs::create_directories(out);
    std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
    weights=std::make_unique<Weights>(a);auto p=plan(*weights,a);
    engine=std::make_unique<Engine>(*weights,a,p);engine->initialize();
    std::vector<int> input;std::ifstream f(a.inputs);int id;
    while(f>>id){require(id>=0 && id<p.g.vocab,"token bounds");input.push_back(id);}
    require(f.eof() && !input.empty() && input.size()+a.tokens-1<=size_t(a.context),"input");
    fs::copy_file(fs::path(argv[1])/"input.json",out/"input.json");
    std::ofstream progress(out/"positions.jsonl"),tokenlog(out/"tokens.jsonl");
    auto forward=[&](int token,int capture,size_t position) {
      auto t=std::chrono::steady_clock::now();engine->put(0,"token",&token,4);
      auto dir=out/("step"+std::to_string(capture));std::ofstream hashes;
      if(capture>0 && capture<=8){fs::create_directories(dir);hashes.open(dir/"layers.jsonl");}
      for(const auto& l:p.launches) {
        // Intermediate prefill predictions are unused; preserve commit/state.
        if(capture==0 && (l.label.starts_with("final.") || l.label=="logits" || l.label=="argmax"))continue;
        engine->enqueue(l,engine->logical);
        if(ends(l.label,".ffn.combine")) {
          int layer=std::stoi(l.label.substr(4));
          if(hashes.is_open()) {
            auto raw=engine->readback(0,engine->buffers[0].at("streams").id,4*p.g.h*2);
            char name[32];std::snprintf(name,sizeof name,"layer-%02d.bf16",layer);
            std::ofstream b(dir/name,std::ios::binary);b.write(reinterpret_cast<char*>(raw.data()),raw.size());
            hashes<<"{\"layer\":"<<layer<<",\"shape\":[1,4,2560],\"dtype\":\"BF16 little-endian\",\"sha256\":"<<ownrt::quote(hash(raw))<<"}\n";hashes.flush();
          }
          if(!a.first){engine->release_layer(0);engine->loaded_layer[0]=-1;}
        }
      }
      if(!a.first)engine->release_layer(0);
      double seconds=Engine::ms(t)/1000;
      progress<<"{\"position\":"<<position<<",\"input_token\":"<<token<<",\"seconds\":"<<seconds<<"}\n";progress.flush();
      std::cout<<"position "<<position<<" seconds "<<seconds<<std::endl;
      return seconds;
    };
    persist();double last=0;
    for(size_t i=0;i<input.size();++i)last=forward(input[i],i+1==input.size()?1:0,i);
    prefill=Engine::ms(started)/1000;
    if(!a.first)for(int step=1;step<=a.tokens;++step) {
      auto slot=engine->buffers[0].at("logits");auto raw=engine->readback(0,slot.id,slot.n*flash::scalar_bytes(slot.type));
      View logits{raw.data(),slot.n,slot.type};std::vector<int> rank(slot.n);std::iota(rank.begin(),rank.end(),0);
      for(size_t i=0;i<slot.n;++i)require(std::isfinite(logits.get(i)),"nonfinite logits");
      std::partial_sort(rank.begin(),rank.begin()+5,rank.end(),[&](int a,int b){return logits.get(a)==logits.get(b)?a<b:logits.get(a)>logits.get(b);});
      int next=engine->integer(0,"next_token");require(next==rank[0],"argmax mismatch");
      std::ostringstream row;row<<std::setprecision(12)<<"{\"step\":"<<step<<",\"token_id\":"<<next<<",\"seconds\":"<<(step==1?prefill:last)<<",\"top5_ids\":[";
      for(int j=0;j<5;++j)row<<(j?",":"")<<rank[j];row<<"],\"top5_logits\":[";
      for(int j=0;j<5;++j)row<<(j?",":"")<<logits.get(rank[j]);row<<"],\"logits_bf16_sha256\":"<<ownrt::quote(hash(raw))<<"}";
      steps.push_back(row.str());generated.push_back(next);costs.push_back(step==1?prefill:last);
      tokenlog<<row.str()<<'\n';tokenlog.flush();persist();
      if(step==8)fs::copy_file(out/"result.json",out/"pilot8.json");
      if(next==p.g.eos || next==248046){status="eos";break;}
      if(step==a.tokens){status="token-cap";break;}
      if(step==8 && std::accumulate(costs.begin()+1,costs.end(),0.)/7>=600){status="pilot-too-slow";break;}
      last=forward(next,step+1,input.size()+step-1);
    }
    if(a.first)status="first-layer-complete";
    persist();auto teardown=engine->shutdown();save(out/"teardown.json","["+teardown.at(0)+"]\n");engine.reset();
  } catch(const std::exception& ex) {
    error=ex.what();status="failed-or-stopped";std::cerr<<error<<std::endl;
    if(engine){engine->poisoned=true;engine->shutdown();engine.reset();}
    if(created_output)persist();return 1;
  }
  return 0;
}
