#include "expert_case.hpp"
#include <filesystem>
#include <memory>
using namespace iq3;
using namespace expert_test;
namespace {
void stop(int){stopping=1;}
struct NativeKernels {
  kopt6::Variant v;
  kopt6::Launch expert_gate_up(ownrt::Device& d,const kopt6::Matrix& g,const kopt6::Matrix& u,unsigned s){return kopt6::expert_gate_up(d,g,u,s,v);}
  kopt6::Launch expert_down(ownrt::Device& d,const kopt6::Matrix& m,unsigned s){return kopt6::expert_down(d,m,s,v);}
  decltype(&kopt6::epilogue) epilogue=kopt6::epilogue;
};
}
int main(int argc,char** argv) {
 if(argc!=7 || std::string(argv[1])!="--authorized-device-window")return 2;
 std::signal(SIGINT,stop);std::signal(SIGTERM,stop);
 std::unique_ptr<ownrt::Device> d;std::string error,failure_kind;unsigned checks=0;ownrt::Receipt teardown;
 try {
  require(std::string(argv[2])=="3","card3 only");std::string mode=argv[6];
  auto v=kopt6::variant(mode);unsigned split=1;
  std::vector<Fixture> fixtures;
  for(const auto* name:{"random0-IQ2_S.fixture","random1-IQ3_S.fixture","random0-IQ4_NL.fixture"})fixtures.emplace_back((std::filesystem::path(argv[3])/name).string());
  require(!stopping,"cooperative stop before device");d=std::make_unique<ownrt::Device>(ownrt::make_sycl_device(3));
  for(const auto& f:fixtures)for(unsigned mutation=0;mutation<8;++mutation){exercise(NativeKernels{v},*d,f,mutation,split);++checks;}
  for(unsigned mutation:{0u,1u}){exercise(NativeKernels{v},*d,fixtures[1],mutation,split,true);++checks;}
 }catch(const ExactnessFailure& e){error=e.what();failure_kind="exactness";}
 catch(const std::exception& e){error=e.what();failure_kind="infrastructure";}
 if(d){std::ofstream census(argv[5]);census<<d->arena.census()<<'\n';census.close();teardown=d->shutdown(std::chrono::seconds(10));}
 std::ofstream out(argv[4]);out<<"{\"checks\":"<<checks<<",\"error\":"<<ownrt::quote(error)<<",\"failure_kind\":"<<ownrt::quote(failure_kind)<<",\"teardown\":"<<teardown.json()<<"}\n";out.close();
 if(d && !teardown.safe_to_exit)ownrt::hold_for_supervisor();return !error.empty() || !teardown.safe_to_exit;
}
