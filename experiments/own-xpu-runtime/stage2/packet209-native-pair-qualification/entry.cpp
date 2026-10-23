#include "native_guard.hpp"
#include <sycl/sycl.hpp>
#include <iostream>
#include <memory>
extern char **environ;
extern "C" int p208_future_qualification(const char*,void(*)());
namespace {p209::Guard* active=nullptr;void guard(){p209::need(active,"guard unavailable");active->check();}}
int main(int argc,char**argv){
  std::unique_ptr<p209::Guard> held;bool live_checked=false,enumerated=false,fixture_entered=false;
  try {
    p209::need(argc==6,"exact CLI required: --guard-check|--authorized-device-window --manifest PATH --manifest-sha256 SHA");
    std::string mode=argv[1];p209::need((mode=="--guard-check"||mode=="--authorized-device-window")&&std::string(argv[2])=="--manifest"&&std::string(argv[4])=="--manifest-sha256","CLI admission");
    held=std::make_unique<p209::Guard>(argv[3],argv[5]);auto& g=*held;
    if(mode=="--guard-check"){std::cout<<"{\"passed\":true,\"static_manifest_only\":true,\"device_enumerated\":false,\"device_executed\":false}\n";return 0;}
    const auto& env=p209::field(g.m,"environment");std::set<std::string> actual;for(char**p=environ;*p;++p){std::string e=*p;actual.insert(e.substr(0,e.find('=')));}p209::need(actual==std::set<std::string>(env.keys.begin(),env.keys.end()),"unexpected inherited environment");
    active=&g;std::signal(SIGTERM,p209::stop);std::signal(SIGINT,p209::stop);g.live_entry();live_checked=true;
    // The ONLY enumeration is inside this admitted child, before owner creation.
    std::vector<sycl::device> cards;for(const auto& platform:sycl::platform::get_platforms())if(platform.get_backend()==sycl::backend::ext_oneapi_level_zero)for(const auto& d:platform.get_devices(sycl::info::device_type::gpu))cards.push_back(d);
    enumerated=true;p209::need(cards.size()==1,"exactly one filtered Level Zero GPU required");
    p209::need(cards[0].get_info<sycl::ext::intel::info::device::pci_address>()=="0000:27:00.0","physical card1 BDF mismatch");guard();
    // Explicit admission descriptor: ACK does not pretend the backend already
    // exists. It proves this filtered child's exact target-node ownership before
    // the unchanged P208 fixture creates its native owner.
    std::string node;for(const auto& n:p209::field(g.m,"target_nodes").items){auto value=p209::str(n);if(p209::fs::path(value).filename().string().find("renderD")==0)node=value;}
    p209::need(!node.empty(),"admitted render node required");const auto& mapping=p209::field(p209::field(g.m,"topology"),node);
    p209::need(p209::str(p209::field(mapping,"bdf"))=="0000:27:00.0","admission node BDF");
    auto sys=p209::fs::path("/sys/class/drm")/p209::fs::path(node).filename();
    p209::need(p209::fs::canonical(sys/"device").filename()=="0000:27:00.0","render sysfs BDF");
    const std::string dev=p209::str(p209::field(mapping,"dev"));p209::need(p209::read(sys/"dev",64)==dev+"\n","render sysfs dev_t");
    int admission_fd=::open(node.c_str(),O_RDONLY|O_CLOEXEC|O_NOFOLLOW);p209::need(admission_fd>=0,"admission descriptor open");
    struct Close {int fd;~Close(){if(fd>=0)::close(fd);}} hold{admission_fd};struct stat info{};
    p209::need(!fstat(admission_fd,&info)&&S_ISCHR(info.st_mode)&&std::to_string(major(info.st_rdev))+":"+std::to_string(minor(info.st_rdev))==dev,"admission fstat dev_t");
    p209::exclusive(g.control/"identity.json","{\"pid\":"+std::to_string(getpid())+",\"start_ticks\":"+p209::ticks(getpid())+",\"bdf\":\"0000:27:00.0\",\"visible_devices\":1,\"manifest_sha256\":\""+g.digest+"\",\"admission_node\":\""+node+"\",\"admission_dev\":\""+dev+"\",\"observation_scope\":\"admission-descriptor\"}\n");
    g.acknowledged();fixture_entered=true;int rc=p208_future_qualification(g.output.c_str(),guard);
    p209::exclusive(g.control/"entry-result.json","{\"returncode\":"+std::to_string(rc)+",\"device_enumerated\":true,\"fixture_called\":true}\n");return rc;
  }catch(const std::exception& e){
    // Absence of an output is not a no-owner proof. Emit a positive, bound
    // pre-fixture refusal only after live checks established the control path.
    if(held&&live_checked&&!fixture_entered){try{p209::exclusive(held->control/"entry-refusal.json","{\"pid\":"+std::to_string(getpid())+",\"start_ticks\":"+p209::ticks(getpid())+",\"manifest_sha256\":\""+held->digest+"\",\"fixture_entered\":false,\"safe_no_owner\":true,\"device_enumerated\":"+(enumerated?"true":"false")+"}\n");}catch(...) {}}
    std::cerr<<e.what()<<'\n';return 1;
  }
}
