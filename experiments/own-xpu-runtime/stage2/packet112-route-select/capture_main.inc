int main(int argc,char**argv){using namespace p107bench;try{
 require(argc==2,"CPU capture OUTPUT");fs::path output=argv[1];fs::create_directories(output);
 std::ofstream logits(output/"harness-logits.bin",std::ios::binary),meta(output/"harness-logits.jsonl");
 packet26::dispatch.load((packet/"dispatch-speed6.json").string());
 for(int layer:{4,3}){
  Options a;a.mini=true;Weights w(a);a.mini=false;a.cards=2;a.context=4096;a.memory="resident";a.legacy=false;a.rank=0;a.draft_rank=1;a.timing="class";a.seconds=600;a.selection=(packet/"selection.json").string();a.selection_sha256="6c58206cad748a8385b41389d5b9c05ff1891340b4bd0b12ce3611b5cddca739";a.output=output;
  auto p=layer_plan(w,a,layer);Engine e(w,a,p);e.devices.push_back(std::make_unique<ownrt::Device>(std::make_unique<Host>()));Fixture f(e,layer);f.setup();
  for(unsigned row=0;row<8;++row){unsigned seed=0x10700+row;f.input(seed,127);e.context_extent=128;
   for(const auto&l:e.p.launches)if(l.op=="qsa_attention"||l.op=="qsa_select")e.prepared[&l]=e.prepare_site(l);
   bool captured=false;
   for(const auto&g:f.groups){const auto&l=e.p.launches[g.first];
    if(l.op=="route"){
     auto b=e.buffers[0].at(l.inputs.at(0));require(b.n==512,"router extent");
     auto bytes=e.readback(0,b.id,b.n*flash::scalar_bytes(b.type));integrated::View v{bytes.data(),b.n,b.type};
     std::array<float,512>x{};for(unsigned i=0;i<512;++i)x[i]=v.get(i);
     logits.write(reinterpret_cast<const char*>(x.data()),sizeof x);
     meta<<"{\"layer\":"<<layer<<",\"seed\":"<<seed<<",\"position\":127,\"source_input\":"<<ownrt::quote(l.inputs.at(0))<<",\"source_type\":"<<int(b.type)<<",\"source_sha256\":"<<ownrt::quote(hash(bytes))<<",\"synthetic_layer\":true}\n";
     captured=true;break;
    }f.execute(g,false);
   }require(captured,"route not found");e.drain();e.pending.clear();e.tail=0;e.dev(0).retire_completed_events();
  }e.shutdown();
 }
 require(bool(logits)&&bool(meta),"capture write");std::cout<<"16 CPU packet107 harness router rows captured; no model/device run\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
