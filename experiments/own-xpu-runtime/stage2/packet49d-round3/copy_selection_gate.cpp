// Reuse actual K2 owners and submissions; zero CPU timing is never speed evidence.
#define main unused_fixture_entry
#include "fixture_driver.cpp"
#undef main
AdapterFixtureReceipt gemv_adoption_gate(const std::filesystem::path&,const std::string&);
int main(int argc,char**argv){try{
 check(argc==3,"selection manifest and output required");
 fixture_validation::only=true;
 std::ifstream manifest(argv[1]);std::string klass,path;int context;
 std::filesystem::path root=argv[2];std::filesystem::create_directories(root);unsigned rows=0,checks=0;
 while(manifest>>klass>>context>>path){
  packet26::dispatch.load(path);auto out=root/std::to_string(rows);std::filesystem::create_directories(out);
  unsigned count=0;
  if(klass.starts_with("gemv:"))count=gemv_adoption_gate(out,klass.substr(5)).checks;
  else {
   check(klass=="qsa.attention","unknown selection class");Runner r(0);
   std::vector<int> lengths=context==256?std::vector<int>{88,104,120,136,152,256}:context==4096?std::vector<int>{88,152,1024,2048,2049,4096}:std::vector<int>{88,152,1024,2048,4096,8192,32767};
   for(int n:lengths){
    ng::Shape s{ng::attention_score,1,2560,4,std::min(n/4,512)*4+n%4,0,context,2048};s.extent=std::min(context,((n+31)/32)*32);
    Fixture f(s,"adopted-attention");f.data[17]=Fixture::integer(n-1);
    auto a=f.args();std::fill_n(a.i(4),s.budget+3,-1);for(int j=0;j<s.extra;++j)a.i(4)[j]=j;
    auto bindings=r.prepare(f);std::vector<Allocation> staging(19);
    for(int j=0;j<19;++j)if(f.outputs[j])staging[j]=r.allocate(f.data[j].size(),Memory::pinned);
    r.run(f,packet26::dispatch.implementation_for(klass,integrated::Op::qsa_attention),-1,0,"adopted",&bindings);
    r.download(f,bindings,&staging);r.clear();++count;
   }
   auto end=r.device.shutdown(std::chrono::seconds(60));check(end.safe_to_exit&&!end.exit_code,"attention adoption teardown");
  }
  check(count>0,"selection did not submit");checks+=count;++rows;
  std::cout<<"{\"class\":"<<ownrt::quote(klass)<<",\"context\":"<<context<<",\"checks\":"<<count<<",\"dispatch\":"<<ownrt::quote(path)<<",\"passed\":true}\n";
 }
 check(rows>0,"empty selection sweep");
 std::cout<<"{\"passed\":true,\"rows\":"<<rows<<",\"checks\":"<<checks<<",\"device_executed\":false}\n";
 return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
