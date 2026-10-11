#include "expert_case.hpp"
#include <filesystem>
#include <memory>
using namespace iq3;
using namespace expert_test;
namespace {
void stop(int){stopping=1;}
struct NativeKernels {
  decltype(&kopt4::expert_gate_up) expert_gate_up=kopt4::expert_gate_up;
  decltype(&kopt4::expert_down) expert_down=kopt4::expert_down;
  decltype(&kopt4::epilogue) epilogue=kopt4::epilogue;
};
}
int main(int argc,char** argv) {
 if(argc!=7 || std::string(argv[1])!="--authorized-device-window")return 2;
 std::signal(SIGINT,stop);std::signal(SIGTERM,stop);
 std::unique_ptr<ownrt::Device> d;std::string error,failure_kind;unsigned checks=0;ownrt::Receipt teardown;
 try {
  require(std::string(argv[2])=="3","card3 only");std::string mode=argv[6];
  require(mode=="experts_sg32" || mode=="experts_split4","mode");unsigned split=mode=="experts_split4"?4:1;
  std::vector<Fixture> fixtures;
  for(const auto* name:{"random0-IQ2_S.fixture","random1-IQ3_S.fixture","random0-IQ4_NL.fixture"})fixtures.emplace_back((std::filesystem::path(argv[3])/name).string());
  require(!stopping,"cooperative stop before device");d=std::make_unique<ownrt::Device>(ownrt::make_sycl_device(3));
  for(const auto& f:fixtures)for(unsigned mutation=0;mutation<4;++mutation){exercise(NativeKernels{},*d,f,mutation,split);++checks;}
  for(unsigned mutation:{0u,1u}){exercise(NativeKernels{},*d,fixtures[1],mutation,split,true);++checks;}
 }catch(const ExactnessFailure& e){error=e.what();failure_kind="exactness";}
 catch(const std::exception& e){error=e.what();failure_kind="infrastructure";}
 if(d){std::ofstream census(argv[5]);census<<d->arena.census()<<'\n';census.close();teardown=d->shutdown(std::chrono::seconds(10));}
 std::ofstream out(argv[4]);out<<"{\"checks\":"<<checks<<",\"error\":"<<ownrt::quote(error)<<",\"failure_kind\":"<<ownrt::quote(failure_kind)<<",\"teardown\":"<<teardown.json()<<"}\n";out.close();
 if(d && !teardown.safe_to_exit)ownrt::hold_for_supervisor();return !error.empty() || !teardown.safe_to_exit;
}
