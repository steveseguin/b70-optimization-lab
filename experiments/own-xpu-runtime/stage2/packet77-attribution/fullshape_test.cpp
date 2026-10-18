// Included after the CPU-only allocation mirror of main.cpp.
int main(int argc,char**argv){try{
 require(argc==5,"packet, output, selection and target split required");
 fs::path packet=argv[1],out=argv[2];fs::create_directories(out);
 packet26::dispatch.load(packet/"dispatch-speed6.json");
 for(int rank=0;rank<2;++rank){
  Options a;a.cards=1;a.card=0;a.rank=rank;a.draft_rank=1;a.target_split=std::stoi(argv[4]);a.context=4096;a.memory="resident";a.mtp=true;a.timing="attribution";a.output=out/("rank"+std::to_string(rank));fs::create_directories(a.output);
  a.selection=argv[3];{std::ifstream f(a.selection);std::vector<uint8_t>b((std::istreambuf_iterator<char>(f)),{});a.selection_sha256=hash(b);}
  Options metadata;metadata.mini=true;Weights weights(metadata);
  weights.directory=flash::directory_from_loader(iq3::read_plan(packet.parent_path()/"suite-inputs-20261012/incident-retrospective/plan.tsv"));
  auto p=pipeline::split(plan(weights,a),rank,false,1,a.target_split);
  require(p.g.h==2560&&p.g.experts==512,"full-shape geometry");
  Engine engine(weights,a,p);engine.initialize();
  if(rank==0)pipeline::banks(engine);else {engine.prepare_plan();engine.prepare_commands();}
  pipeline::SpeculativeImage image(engine);
  const auto target_allocations=engine.allocations.size();
  std::unique_ptr<mtp36::DraftRuntime> draft;
  if(rank==1)draft=std::make_unique<mtp36::DraftRuntime>(engine);
  // The real post-load provider constructor has allocated and prepared the draft.
  // Replay target prepared bindings AFTER those allocations; mock callbacks only
  // append completed event IDs, so no model arithmetic runs.
  size_t launches=0;
  for(auto&site:engine.issue_sites)for(auto&cmd:site.commands){engine.tail=engine.dev(0).issue(cmd);++launches;}
  engine.drain();
  const size_t boundary=a.target_split?size_t(a.target_split):24;
  size_t layers=0;for(const auto&site:engine.issue_sites)layers+=site.layer_end;
  require(engine.issue_sites.size()==engine.p.launches.size()&&layers==(rank==0?boundary:48-boundary)&&launches>500,"full target sequence missing");
  auto* mock=dynamic_cast<P77AllocationMock*>(&*p77_last_mock);
  require(mock&&mock->payload_reads==0&&mock->kernels_executed==0,"CPU model execution forbidden");
  require(rank==0||engine.allocations.size()>target_allocations,"post-load draft allocations missing");
  save(a.output/"census.json",engine.dev(0).arena.census());
  save(a.output/"result.json","{\"passed\":true,\"device_executed\":false,\"cpu_model_executed\":false,\"rank\":"+std::to_string(rank)+",\"target_split\":"+std::to_string(a.target_split)+",\"prepared_commands\":"+std::to_string(launches)+",\"postload_device_allocations\":"+std::to_string(engine.allocations.size()-target_allocations)+",\"backing_bytes\":"+std::to_string(mock->backing_bytes)+",\"ordered_retirement\":"+"false"+"}\n");
  draft.reset();auto done=engine.dev(0).shutdown(std::chrono::seconds(5));require(done.safe_to_exit&&done.exit_code==0,"allocation-only teardown");save(a.output/"teardown.json",done.json());
 }
 return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
