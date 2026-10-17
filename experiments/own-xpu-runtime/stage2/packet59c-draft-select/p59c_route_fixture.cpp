// Reuse the production-width bounded route fixture, bypassing unrelated target
// expert/recurrence suites and the parent's old selection-file schema checks.
#ifndef OWN_RT_HOST_ONLY
#error packet59c operator gate is CPU only
#endif
#define main inherited_p49d_fixture_main
#include "p49d_fixture.cpp"
#undef main
int main(int argc,char**argv){
 if(argc==4&&std::string(argv[1])=="--selection"){
  try {p49d::Selection selection;std::string digest=argv[3];if(digest.size()!=64)throw std::invalid_argument("hash required");selection.load(argv[2],digest);std::cout<<selection.draft.size()<<" selected entries\n";return 0;}
  catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}
 }
 if(argc!=2)return 2;
 try{
  std::filesystem::path out=argv[1];std::filesystem::create_directories(out);
  Runner r(0,60);Suite s(r,out,false);s.route();
  s.bytes.close();s.cases.close();s.events.close();check(bool(s.bytes)&&bool(s.cases)&&bool(s.events),"route fixture flush");
  auto end=r.d.shutdown(std::chrono::seconds(30));check(end.safe_to_exit&&end.exit_code==0,"route teardown");
  std::ofstream(out/"receipt.json")<<"{\"passed\":true,\"device_executed\":false,\"checks\":"<<s.checks<<"}\n";
  return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
}
