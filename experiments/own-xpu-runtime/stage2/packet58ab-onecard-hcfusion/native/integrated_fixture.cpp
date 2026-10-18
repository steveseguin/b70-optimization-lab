// CPU-only: exercise the actual Engine target hook and prepared capture slots
// at production HC shapes. Reuse the primitive fixture's production reference.
#define main p60_unused_engine_main
#include "main.cpp"
#undef main
#define P60_FIXTURE_DATA_ONLY
#include "fixture.cpp"
#undef P60_FIXTURE_DATA_ONLY
int main(int argc,char**argv){try{
 require(argc==4,"output directory, retained metadata and dispatch");fs::create_directories(argv[1]);
 std::ofstream expected(fs::path(argv[1])/"expected.bin",std::ios::binary),actual(fs::path(argv[1])/"actual.bin",std::ios::binary);
 unsigned cases=0,commands_count=0;
 for(unsigned row=0;row<3;++row){
  Options options;options.mini=true;Weights weights(options);
  options.hc="p60fusion";options.mini=false;options.memory="resident";options.nongemv="parallel";options.timing="token";options.seconds=120;options.output=argv[1];
  flash::Plan plan;plan.g.context=4096;Engine engine(weights,options,plan);
  engine.devices.push_back(std::make_unique<ownrt::Device>(std::make_unique<Host>()));
  engine.owned_bytes={0};engine.buffers.resize(1);engine.weights.resize(1);
  engine.fp32_sources={0};engine.fp32_extents={0};
  std::vector<Allocation> allocations;
  auto alloc=[&](const std::string&name,void*data,size_t bytes){
   auto id=engine.allocate(0,name,bytes,Category::scratch,Lifetime::transaction);
   std::memcpy(engine.dev(0).arena.row(id).pointer,data,bytes);allocations.push_back(id);return id;
  };
  float unit=1;engine.one={alloc("one",&unit,4)};
  auto staging=engine.allocate(0,"staging",4*1024*1024,Category::pinned_slab,Lifetime::transfer,Memory::pinned);engine.slab={staging};allocations.push_back(staging);
  std::vector<ownrt::PreparedCompute> last_commands;
  Data baseline;baseline.init(765+row);baseline.position=row?4093+row:127;Data candidate=baseline;
  auto buf=[&](const std::string&name,void*data,size_t n,flash::Scalar type){engine.buffers[0][name]={alloc(name,data,n*flash::scalar_bytes(type)),n,type};};
  buf("streams",candidate.x.data(),K,flash::Scalar::bf16);
  buf("error",&candidate.error,1,flash::Scalar::u32);buf("active",&candidate.active,1,flash::Scalar::u32);buf("position",&candidate.position,1,flash::Scalar::u32);
  engine.scratch={alloc("scratch",candidate.scratch.data(),320*4)};
  engine.workspace={alloc("workspace",candidate.workspace.data(),32*4)};
  for(unsigned side=0;side<2;++side){
   const std::string tag=side?"blk.23.hc.f":"blk.23.hc.a",wt=side?"blk.23.hc_ffn_":"blk.23.hc_attn_";
   auto weight=[&](const std::string&suffix,void*data,size_t bytes,const std::string&grid){std::string name=wt+suffix;weights.directory[name]={name,grid,"hc",{},bytes};auto id=engine.allocate(0,name,bytes,Category::weights,Lifetime::process);std::memcpy(engine.dev(0).arena.row(id).pointer,data,bytes);allocations.push_back(id);engine.weights[0][name]=id;};
   weight("norm.weight",candidate.gain.data(),K*4,"F32");weight("down.weight",candidate.lw.data(),candidate.lw.size(),"Q8_0");
   weight("up.weight",candidate.gw.data(),candidate.gw.size(),"Q8_0");weight("inject.weight",candidate.iw.data(),candidate.iw.size(),"F32");
   for(auto pair:{std::pair{"norm",&candidate.norm},{"low",&candidate.low},{"act",&candidate.act},{"gate",&candidate.gate},{"mix",&candidate.mix},{"inject",&candidate.inject}})
    buf(tag+"."+pair.first,pair.second->data(),pair.second->size(),flash::Scalar::bf16);
   std::vector<ownrt::PreparedCompute> captured;
   for(const auto&suffix:{"norm","low","act","gate","mix","inject"}){
    flash::Launch launch;launch.label=tag+"."+suffix;launch.outputs={launch.label};
    engine.fp32_sources[0]=engine.buffers[0].at(launch.label).id;
    std::vector<ownrt::PreparedCompute> slot;engine.preparing_commands=true;engine.dev(0).begin_capture(slot);
    engine.execute_site(launch);engine.dev(0).end_capture();engine.preparing_commands=false;
    require(engine.fp32_sources[0]==0,"HC writes invalidate cached FP32 input");
    require(slot.size()==size_t(p60::stage(launch.label)<3),"one original capture slot per stage/follower");
    captured.insert(captured.end(),slot.begin(),slot.end());
   }
   require(captured.size()==3,"three commands per side");last_commands=captured;
   for(const auto&command:captured)engine.finish(0,engine.dev(0).issue(command));engine.drain();commands_count+=captured.size();
   reference(baseline.bound());
   for(auto pair:{std::pair{"norm",&candidate.norm},{"low",&candidate.low},{"act",&candidate.act},{"gate",&candidate.gate},{"mix",&candidate.mix},{"inject",&candidate.inject}})
    std::memcpy(pair.second->data(),engine.dev(0).arena.row(engine.buffers[0].at(tag+"."+pair.first).id).pointer,pair.second->size()*2);
   std::memcpy(candidate.scratch.data(),engine.dev(0).arena.row(engine.scratch[0]).pointer,320*4);
   std::memcpy(candidate.workspace.data(),engine.dev(0).arena.row(engine.workspace[0]).pointer,32*4);
   std::memcpy(&candidate.error,engine.dev(0).arena.row(engine.buffers[0].at("error").id).pointer,4);
   baseline.write(expected);candidate.write(actual);++cases;
  }
  // Real request reset: sticky failure cannot be erased; clean reset preserves
  // weight bytes, HC choice and allocations, then the same capture can run.
  const auto identity=engine.bracket_arena_hash();
  auto* error=static_cast<uint32_t*>(engine.dev(0).arena.row(engine.buffers[0].at("error").id).pointer);
  *error=37;bool refused=false;try{p58_reset_request(engine,fs::path(argv[1])/"bad-reset");}catch(const std::exception&){refused=true;}
  require(refused&&*error==37,"request reset erased sticky error");*error=0;
  engine.poisoned=true;refused=false;try{p58_reset_request(engine,fs::path(argv[1])/"poison-reset");}catch(const std::exception&){refused=true;}
  require(refused&&engine.poisoned,"request reset erased poisoned owner");engine.poisoned=false;
  p58_reset_request(engine,fs::path(argv[1])/("reset-"+std::to_string(row)));
  require(engine.a.hc=="p60fusion"&&engine.bracket_arena_hash()==identity&&engine.fp32_sources[0]==0,"reset changed HC/allocations or retained FP32 cache");
  engine.put(0,"streams",candidate.x.data(),K*2);
  for(const auto&command:last_commands)engine.finish(0,engine.dev(0).issue(command));engine.drain();
  for(auto pair:{std::pair{"norm",&baseline.norm},{"low",&baseline.low},{"act",&baseline.act},{"gate",&baseline.gate},{"mix",&baseline.mix},{"inject",&baseline.inject}}) {
    auto* actual=engine.dev(0).arena.row(engine.buffers[0].at(std::string("blk.23.hc.f.")+pair.first).id).pointer;
    require(std::memcmp(actual,pair.second->data(),pair.second->size()*2)==0,"HC differs after request reset");
  }
  for(auto id:allocations){if(id==staging)engine.dev(0).arena.release(id);else engine.release(0,id);}engine.dev(0).shutdown(std::chrono::seconds(5));
 }
 expected.close();actual.close();require(bool(expected)&&bool(actual),"fixture writes");
 require(p60::stage("blk.bad.hc.a.norm")==-1&&p60::stage("blk.0.hc.a.bad")==-1&&p60::stage("draft.hc.a.norm")==-1&&p60::stage("final.norm")==-1,"draft/final excluded");
 for(unsigned layer=0;layer<48;++layer)for(const auto&side:{"a","f"})for(const auto&op:{"norm","low","act","gate","mix","inject"}) {
   const std::string name=op;int expected=name=="norm"?0:name=="low"?1:name=="gate"?2:3;
   require(p60::stage("blk."+std::to_string(layer)+".hc."+side+"."+op)==expected,"every target label admitted");
 }
 Options production;production.mini=true;Weights metadata(production);
 metadata.directory=flash::directory_from_loader(iq3::read_plan(argv[2]));
 production.hc="p60fusion";production.mini=false;production.memory="resident";production.context=4096;production.cards=1;
 packet26::dispatch.load(argv[3]);auto target_plan=plan(metadata,production);
 std::array<unsigned,3> stages{};
 for(const auto&launch:target_plan.launches){int stage=p60::stage(launch.label);if(stage>=0&&stage<3)++stages[stage];}
 require(stages==std::array<unsigned,3>{96,96,96},"three stages on both sides of all 48 target layers");
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"cases\":"<<cases<<",\"prepared_commands\":"<<commands_count<<",\"production_target_sides\":96,\"production_hc_commands_per_row\":288}\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
