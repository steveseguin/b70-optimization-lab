// The frozen packet17 host-only oracle; wrapper adds bounds, receipts and restart state.
#ifndef OWN_RT_HOST_ONLY
#error CPU only
#endif
#define main packet17_unused_main
#include "runtime_main.cpp"
#undef main
#include <numeric>
#include <iomanip>
#include <bit>

static void disk_guard() {
  FILE* f=popen("nice -n 19 ionice -c 3 df -B1 /","r");require(f,"df");
  char line[4096];std::string last;while(fgets(line,sizeof line,f))last=line;
  require(pclose(f)==0,"df exit");std::istringstream in(last);std::string device;uint64_t total,used,free;
  require(bool(in>>device>>total>>used>>free) && free>=8000000000ull,"STOP: root has less than 8 GB free");
}
template<class T> static void scalar(std::ostream& f,const T& v){f.write(reinterpret_cast<const char*>(&v),sizeof v);require(bool(f),"checkpoint write");}
template<class T> static void scalar(std::istream& f,T& v){f.read(reinterpret_cast<char*>(&v),sizeof v);require(bool(f),"checkpoint read");}
static void string_write(std::ostream& f,const std::string& s){uint64_t n=s.size();scalar(f,n);f.write(s.data(),n);require(bool(f),"string write");}
static std::string string_read(std::istream& f){uint64_t n;scalar(f,n);require(n<10000000,"string bound");std::string s(n,'\0');f.read(s.data(),n);require(bool(f),"string read");return s;}

static void capture_selection(Engine& e,const flash::Launch& l,const fs::path& dir,size_t position) {
  fs::create_directories(dir);
  const int layer=std::stoi(l.label.substr(4));auto slot=e.buffers[0].at(l.outputs[0]);
  auto raw=e.readback(0,slot.id,slot.n*4);std::vector<int32_t> ids(slot.n);std::memcpy(ids.data(),raw.data(),raw.size());
  std::string stem="layer-"+(layer<10?std::string("0"):std::string())+std::to_string(layer);
  std::ofstream bin(dir/(stem+".ids.i32"),std::ios::binary);bin.write(reinterpret_cast<char*>(raw.data()),raw.size());bin.close();require(bool(bin),"selection write");
  auto get=[&](const std::string& n){auto s=e.buffers[0].at(n);auto b=e.readback(0,s.id,s.n*flash::scalar_bytes(s.type));View v{b.data(),s.n,s.type};std::vector<float> x(s.n);for(size_t j=0;j<x.size();++j)x[j]=v.get(j);return x;};
  auto q=get(l.inputs[0]),pooled=get(l.inputs[1]);int n=(position+1)/4;
  // Audit scores with the SAME Core::dot and detmath::sqrt; no write to model state.
  std::vector<float> scratch(8192),scores(n,0);Core c;c.pool={scratch.data(),0,scratch.size()};
  for(int h=0;h<e.p.g.ih;++h)for(int b=0;b<n;++b){c.pool.used=0;c.pool.failed=0;
    float d=c.dot(std::span<const float>(q).subspan(h*e.p.g.id,e.p.g.id),std::span<const float>(pooled).subspan(b*e.p.g.id,e.p.g.id));
    require(!c.pool.failed,"selection audit scratch");scores[b]=scores[b]+std::max(0.f,d);}
  for(auto& s:scores)s=s/detmath::sqrt(float(e.p.g.id));
  std::vector<int> rank(n);std::iota(rank.begin(),rank.end(),0);std::stable_sort(rank.begin(),rank.end(),[&](int a,int b){return scores[a]>scores[b];});
  std::vector<int32_t> expected;for(int j=0;j<std::min(n,e.p.g.budget/4);++j)for(int k=0;k<4;++k)expected.push_back(rank[j]*4+k);
  for(size_t j=n*4;j<=position;++j)expected.push_back(j);size_t admitted=expected.size();expected.resize(e.p.g.budget+3,-1);
  require(expected==ids,"selection score audit disagrees");
  int tied_pairs=0;for(int j=1;j<n;++j)if(scores[rank[j]]==scores[rank[j-1]])++tied_pairs;
  bool cutoff=n>e.p.g.budget/4 && scores[rank[e.p.g.budget/4-1]]==scores[rank[e.p.g.budget/4]];
  std::ostringstream row;row<<"{\"layer\":"<<layer<<",\"position\":"<<position<<",\"prompt_ordinal\":"<<position+1
    <<",\"budget\":"<<e.p.g.budget<<",\"valid_positions\":"<<position+1<<",\"admitted\":"<<admitted<<",\"dropped\":"<<position+1-admitted
    <<",\"complete_pools\":"<<n<<",\"trailing_positions\":"<<(position+1)%4<<",\"tied_adjacent_score_pairs\":"<<tied_pairs<<",\"cutoff_tie\":"<<(cutoff?"true":"false")
    <<",\"selection_sha256\":"<<ownrt::quote(hash(raw))<<",\"ids\":[";
  for(size_t j=0;j<admitted;++j)row<<(j?",":"")<<ids[j];row<<"],\"pool_score_f32_bits\":[";
  for(int j=0;j<n;++j)row<<(j?",":"")<<std::bit_cast<uint32_t>(scores[j]);row<<"]}\n";
  save(dir/(stem+".json"),row.str());
}
int main(int argc,char** argv) {
  std::unique_ptr<Weights> weights;std::unique_ptr<Engine> engine;
  std::vector<int> generated;std::vector<double> costs;std::vector<std::string> steps;
  std::string error,status="running";fs::path out;bool created=false;
  auto started=std::chrono::steady_clock::now();double prefill=0,prior_seconds=0,prior_cpu=0;
  uint64_t next_position=0,positions_bytes=0,tokens_bytes=0;
  auto persist=[&]{std::ostringstream r;r<<std::setprecision(12);
    r<<"{\"schema\":\"iq3-runtime-cpu-oracle.v1\",\"arithmetic\":"<<ownrt::quote(arithmetic::version)<<",\"status\":"<<ownrt::quote(status)<<",\"error\":"<<ownrt::quote(error)
     <<",\"device_executed\":false,\"context\":4096,\"next_position\":"<<next_position<<",\"prefill_seconds\":"<<prefill<<",\"seconds\":"<<prior_seconds+Engine::ms(started)/1000<<",\"tokens\":[";
    for(size_t j=0;j<generated.size();++j)r<<(j?",":"")<<generated[j];r<<"],\"steps\":[";for(size_t j=0;j<steps.size();++j)r<<(j?",":"")<<steps[j];
    r<<"],\"decode_seconds_per_token\":";if(costs.size()>1)r<<std::accumulate(costs.begin()+1,costs.end(),0.)/(costs.size()-1);else r<<"null";
    rusage u{};getrusage(RUSAGE_SELF,&u);double cpu=u.ru_utime.tv_sec+u.ru_utime.tv_usec/1e6+u.ru_stime.tv_sec+u.ru_stime.tv_usec/1e6;
    r<<",\"cpu_seconds\":"<<prior_cpu+cpu<<",\"max_rss_kib\":"<<u.ru_maxrss<<",\"model_bytes_read\":"<<(weights?weights->read_bytes:0)<<"}\n";
    save(out/"result.json.tmp",r.str());fs::rename(out/"result.json.tmp",out/"result.json");};
  try {
    require(argc==5 || argc==6,"INPUT OUTPUT SECONDS TOKENS [resume]");bool resume=argc==6;require(!resume || std::string(argv[5])=="resume","resume flag");
    require(getpriority(PRIO_PROCESS,0)==19,"nice 19");require(getenv("OMP_NUM_THREADS") && std::string(getenv("OMP_NUM_THREADS"))=="2","two numeric threads");
    rlimit limit{38000000000ull,38000000000ull};require(setrlimit(RLIMIT_AS,&limit)==0,"address cap");
    Options a;a.inputs=fs::path(argv[1])/"tokens.txt";a.plan=fs::path(argv[1])/"plan.tsv";a.auth=fs::path(argv[1])/"identity.tsv";a.output=out=argv[2];
    a.seconds=std::stoi(argv[3]);a.tokens=std::stoi(argv[4]);a.context=4096;
    require(a.seconds>0 && a.seconds<=259200 && a.tokens>0 && a.tokens<=64,"bounds");
    require(getenv("IQ3_MODEL_DIR"),"model dir");a.model=getenv("IQ3_MODEL_DIR");
    disk_guard();require(resume?fs::exists(out/"checkpoint.bin"):!fs::exists(out),"output/checkpoint exists");if(!resume)fs::create_directories(out);created=true;
    std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
    // Keep previous verbose logs on resume: they are evidence, not numerical state.
    if(resume)for(auto name:{"progress.jsonl","timings.jsonl"})if(fs::exists(out/name))fs::rename(out/name,out/(std::string(name)+".interrupted-"+std::to_string(getpid())));
    weights=std::make_unique<Weights>(a);auto p=plan(*weights,a);require(a.context<=rope_constants::positions,"frozen RoPE bounds");
    engine=std::make_unique<Engine>(*weights,a,p);engine->initialize();
    std::vector<int> input;std::ifstream f(a.inputs);int id;while(f>>id){require(id>=0 && id<p.g.vocab,"token bounds");input.push_back(id);}
    require(f.eof() && !input.empty() && input.size()+a.tokens-1<=size_t(a.context),"input");
    auto filehash=[](const fs::path& path){std::ifstream f(path,std::ios::binary);return hash(std::vector<uint8_t>(std::istreambuf_iterator<char>(f),{}));};
    std::string binding=std::string(arithmetic::version)+filehash(a.inputs)+filehash(a.plan)+filehash(a.auth)+std::to_string(a.tokens)+":4096";
    if(!resume)fs::copy_file(fs::path(argv[1])/"input.json",out/"input.json");
    auto checkpoint=[&]{
      disk_guard();std::ofstream cp(out/"checkpoint.bin.tmp",std::ios::binary);string_write(cp,"iq3-long-state-v1");string_write(cp,binding);
      scalar(cp,next_position);scalar(cp,positions_bytes);scalar(cp,tokens_bytes);scalar(cp,prefill);
      double elapsed=prior_seconds+Engine::ms(started)/1000;scalar(cp,elapsed);rusage u{};getrusage(RUSAGE_SELF,&u);
      double cpu=prior_cpu+u.ru_utime.tv_sec+u.ru_utime.tv_usec/1e6+u.ru_stime.tv_sec+u.ru_stime.tv_usec/1e6;scalar(cp,cpu);
      uint64_t n=generated.size();scalar(cp,n);for(size_t j=0;j<n;++j){scalar(cp,generated[j]);scalar(cp,costs[j]);string_write(cp,steps[j]);}
      n=engine->buffers[0].size();scalar(cp,n);
      for(auto& [name,s]:engine->buffers[0]){string_write(cp,name);auto raw=engine->readback(0,s.id,s.n*flash::scalar_bytes(s.type));string_write(cp,hash(raw));uint64_t bytes=raw.size();scalar(cp,bytes);cp.write(reinterpret_cast<char*>(raw.data()),bytes);require(bool(cp),"state write");}
      string_write(cp,"complete");cp.flush();require(bool(cp),"checkpoint flush");cp.close();
      // Full readback before atomically replacing the prior checkpoint.
      std::ifstream verify(out/"checkpoint.bin.tmp",std::ios::binary);require(string_read(verify)=="iq3-long-state-v1" && string_read(verify)==binding,"checkpoint header");
      uint64_t q;double d;for(int j=0;j<3;++j)scalar(verify,q);for(int j=0;j<3;++j)scalar(verify,d);scalar(verify,q);
      for(uint64_t j=0;j<q;++j){int t;scalar(verify,t);scalar(verify,d);string_read(verify);}scalar(verify,q);require(q==engine->buffers[0].size(),"buffer count");
      for(auto& [name,s]:engine->buffers[0]){require(string_read(verify)==name,"buffer name");auto digest=string_read(verify);uint64_t n;scalar(verify,n);require(n==s.n*flash::scalar_bytes(s.type),"buffer size");std::vector<uint8_t> raw(n);verify.read(reinterpret_cast<char*>(raw.data()),n);require(bool(verify)&&hash(raw)==digest,"checkpoint bytes");}
      require(string_read(verify)=="complete" && verify.peek()==EOF,"checkpoint footer");verify.close();fs::rename(out/"checkpoint.bin.tmp",out/"checkpoint.bin");
      save(out/"checkpoint.json.tmp","{\"next_position\":"+std::to_string(next_position)+",\"bytes\":"+std::to_string(fs::file_size(out/"checkpoint.bin"))+"}\n");fs::rename(out/"checkpoint.json.tmp",out/"checkpoint.json");
    };
    if(resume){
      std::ifstream cp(out/"checkpoint.bin",std::ios::binary);require(string_read(cp)=="iq3-long-state-v1" && string_read(cp)==binding,"resume identity");
      scalar(cp,next_position);scalar(cp,positions_bytes);scalar(cp,tokens_bytes);scalar(cp,prefill);scalar(cp,prior_seconds);scalar(cp,prior_cpu);uint64_t n;scalar(cp,n);require(n<=size_t(a.tokens),"resume token count");
      for(size_t j=0;j<n;++j){int t;double cost;scalar(cp,t);scalar(cp,cost);generated.push_back(t);costs.push_back(cost);steps.push_back(string_read(cp));}
      scalar(cp,n);require(n==engine->buffers[0].size(),"resume buffers");
      for(auto& [name,s]:engine->buffers[0]){require(string_read(cp)==name,"resume buffer name");auto digest=string_read(cp);uint64_t bytes;scalar(cp,bytes);require(bytes==s.n*flash::scalar_bytes(s.type),"resume buffer size");std::vector<uint8_t> raw(bytes);cp.read(reinterpret_cast<char*>(raw.data()),bytes);require(bool(cp)&&hash(raw)==digest,"resume buffer hash");engine->put(0,name,raw.data(),bytes);}
      require(string_read(cp)=="complete" && cp.peek()==EOF,"resume footer");require(engine->integer(0,"position")==int(next_position),"resume position");
      fs::resize_file(out/"positions.jsonl",positions_bytes);fs::resize_file(out/"tokens.jsonl",tokens_bytes);
      for(auto& entry:fs::directory_iterator(out)){auto name=entry.path().filename().string();if(name.starts_with("step") && entry.is_directory() && std::stoul(name.substr(4))>generated.size())fs::remove_all(entry.path());}
      if(fs::exists(out/"midprompt"))for(auto& entry:fs::directory_iterator(out/"midprompt"))if(std::stoul(entry.path().filename().string())>=next_position)fs::remove_all(entry.path());
    }
    std::ofstream progress(out/"positions.jsonl",std::ios::app),tokenlog(out/"tokens.jsonl",std::ios::app);
    auto rotate=[&]{for(auto pair:{std::pair{&engine->progress,"progress.jsonl"},std::pair{&engine->timings,"timings.jsonl"}}){pair.first->close();auto dest=out/(std::string(pair.second)+".segment-"+std::to_string(next_position)+"-"+std::to_string(getpid()));fs::rename(out/pair.second,dest);pair.first->open(out/pair.second);}};
    persist();int interval=getenv("IQ3_CHECKPOINT_INTERVAL")?std::stoi(getenv("IQ3_CHECKPOINT_INTERVAL")):100;require(interval>0,"checkpoint interval");
    while(generated.size()<size_t(a.tokens) && (generated.empty() || (generated.back()!=p.g.eos && generated.back()!=248046))){
      size_t pos=next_position;int token=pos<input.size()?input[pos]:generated.back();int capture=pos+1>=input.size()?int(pos-input.size()+2):0;
      bool mid=pos<input.size() && (pos==2040 || pos==2047 || pos==2048 || pos==2049 || pos==2050 || pos==2051 || pos==2100 || pos+1==input.size());
      auto mid_dir=out/"midprompt"/std::to_string(pos);auto t=std::chrono::steady_clock::now();engine->put(0,"token",&token,4);
      auto dir=out/("step"+std::to_string(capture));std::ofstream hashes;
      if(capture>0 && capture<=8){fs::create_directories(dir);hashes.open(dir/"layers.jsonl");}
      for(const auto& l:p.launches){
        if(capture==0 && (l.label.starts_with("final.") || l.label=="logits" || l.label=="argmax"))continue;
        engine->enqueue(l,engine->logical);
        if(mid && l.op=="qsa_select")capture_selection(*engine,l,mid_dir,pos);
        if(ends(l.label,".ffn.combine")){int layer=std::stoi(l.label.substr(4));
          if(hashes.is_open() || (mid && layer==47)){
            auto raw=engine->readback(0,engine->buffers[0].at("streams").id,4*p.g.h*2);char name[32];std::snprintf(name,sizeof name,"layer-%02d.bf16",layer);
            if(hashes.is_open()){std::ofstream b(dir/name,std::ios::binary);b.write(reinterpret_cast<char*>(raw.data()),raw.size());hashes<<"{\"layer\":"<<layer<<",\"shape\":[1,4,2560],\"dtype\":\"BF16 little-endian\",\"sha256\":"<<ownrt::quote(hash(raw))<<"}\n";hashes.flush();}
            if(mid && layer==47){fs::create_directories(mid_dir);std::ofstream b(mid_dir/name,std::ios::binary);b.write(reinterpret_cast<char*>(raw.data()),raw.size());save(mid_dir/"stream.json","{\"layer\":47,\"position\":"+std::to_string(pos)+",\"prompt_ordinal\":"+std::to_string(pos+1)+",\"shape\":[1,4,2560],\"dtype\":\"BF16 little-endian\",\"sha256\":"+ownrt::quote(hash(raw))+"}\n");}
          }
          engine->release_layer(0);engine->loaded_layer[0]=-1;
        }
      }
      engine->release_layer(0);double seconds=Engine::ms(t)/1000;next_position=pos+1;
      progress<<"{\"position\":"<<pos<<",\"input_token\":"<<token<<",\"seconds\":"<<seconds<<"}\n";progress.flush();positions_bytes=progress.tellp();
      std::cout<<"position "<<pos<<" seconds "<<seconds<<std::endl;
      if(capture){
        if(capture==1)prefill=prior_seconds+Engine::ms(started)/1000;
        auto slot=engine->buffers[0].at("logits");auto raw=engine->readback(0,slot.id,slot.n*flash::scalar_bytes(slot.type));View logits{raw.data(),slot.n,slot.type};std::vector<int> rank(slot.n);std::iota(rank.begin(),rank.end(),0);
        for(size_t j=0;j<slot.n;++j)require(std::isfinite(logits.get(j)),"nonfinite logits");
        std::partial_sort(rank.begin(),rank.begin()+5,rank.end(),[&](int a,int b){return logits.get(a)==logits.get(b)?a<b:logits.get(a)>logits.get(b);});
        int next=engine->integer(0,"next_token");require(next==rank[0],"argmax mismatch");
        std::ostringstream row;row<<std::setprecision(12)<<"{\"step\":"<<capture<<",\"token_id\":"<<next<<",\"seconds\":"<<(capture==1?prefill:seconds)<<",\"top5_ids\":[";
        for(int j=0;j<5;++j)row<<(j?",":"")<<rank[j];row<<"],\"top5_logits\":[";for(int j=0;j<5;++j)row<<(j?",":"")<<logits.get(rank[j]);row<<"],\"logits_bf16_sha256\":"<<ownrt::quote(hash(raw))<<"}";
        steps.push_back(row.str());generated.push_back(next);costs.push_back(capture==1?prefill:seconds);tokenlog<<row.str()<<'\n';tokenlog.flush();tokens_bytes=tokenlog.tellp();
      }
      persist();
      if(next_position%interval==0){checkpoint();rotate();if(getenv("IQ3_STOP_AT_CHECKPOINT") && next_position==std::stoull(getenv("IQ3_STOP_AT_CHECKPOINT"))){status="checkpoint-stopped";break;}}
    }
    if(status!="checkpoint-stopped")status=(!generated.empty() && (generated.back()==p.g.eos || generated.back()==248046))?"eos":"token-cap";
    persist();disk_guard();auto teardown=engine->shutdown();disk_guard();save(out/"teardown.json","["+teardown.at(0)+"]\n");engine.reset();
  }catch(const std::exception& ex){error=ex.what();status="failed-or-stopped";std::cerr<<error<<std::endl;if(engine){engine->poisoned=true;engine->shutdown();engine.reset();}if(created)persist();return 1;}
}
