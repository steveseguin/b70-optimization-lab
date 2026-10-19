#define main packet151_unused_entry
#include "../native-src/main.cpp"
#undef main
static std::string run_case(const fs::path&out,bool enabled){
 fs::create_directories(out);Options a;a.mini=true;a.pipeline_mini=true;a.rank=0;a.draft_rank=1;a.target_split=0;a.memory="resident";a.context=64;a.output=out;a.cards=1;
 Weights w(a);auto p=pipeline::split(plan(w,a),0,true,1,0);Engine e(w,a,p);
 e.sealed_selection.choices["miss"]="banks-batch";e.sealed_selection.choices["probe"]=enabled?"sibling":"off";
 e.initialize();pipeline::banks(e);p151s::Sibling sibling(e);pipeline::SpeculativeImage image(e);pipeline::Candidate candidate;std::vector<uint8_t>shared(pipeline::shared_bytes);
 std::vector<uint8_t>all;
 auto step=[&](int pos,int token,bool spec,bool corrected=false){pipeline::Request request{pipeline::half,token,pos,pos+1,int(spec),pos+1,{}};
  auto r=pipeline::half_step(e,candidate,request,shared.data(),image,false,corrected,&sibling);require(!r.error,"fixture sticky error");
 };
 step(0,2,false);candidate={};
 step(1,5,true);pipeline::undo(e,candidate,image,false);
 step(1,3,false);candidate={};
 step(2,7,true);image.accept();candidate={};
 step(3,2,false);candidate={};
 for(auto&[name,b]:e.buffers[0]){auto raw=e.readback(0,b.id,b.n*flash::scalar_bytes(b.type));all.insert(all.end(),raw.begin(),raw.end());}
 for(auto&[name,id]:e.state_spares){auto raw=e.readback(0,id,e.dev(0).arena.row(id).bytes);all.insert(all.end(),raw.begin(),raw.end());}
 require(e.history0==7&&e.history1==2,"sibling changed host history");auto digest=hash(all);e.shutdown();return digest;
}
int main(int argc,char**argv){try{require(argc==2,"output required");fs::path out=argv[1];auto a=run_case(out/"off",false),b=run_case(out/"sibling",true);require(a==b,"sibling changed kept state");std::cout<<"{\"passed\":true,\"device_executed\":false,\"state_sha256\":"<<ownrt::quote(a)<<",\"miniature_state_proof\":true,\"full_shape_arithmetic_separate\":true}\n";return 0;}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
