#include "compile_smoke.hpp"
#include "gate_mode.hpp"
#include "stop.hpp"
#include "adapter_fixture.hpp"
#include "owner.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
int main(int argc,char**argv){
 std::filesystem::path out;unsigned card=0,repetitions=200;bool auth=false,smoke=false;
 try {
  for(int i=1;i<argc;++i){std::string a=argv[i];if(a=="--authorized-device-window")auth=true;else if(a=="--compile-smoke")smoke=true;else if(a=="--card"&&i+1<argc)card=std::stoul(argv[++i]);else if(a=="--repetitions"&&i+1<argc)repetitions=std::stoul(argv[++i]);else if(a=="--output"&&i+1<argc)out=argv[++i];else throw std::invalid_argument("argument");}
  if(!auth||out.empty()||repetitions!=200)throw std::invalid_argument("authorization/output/200 repetitions required");
  std::filesystem::create_directories(out);p42::install_stop();
  if(smoke){auto n=p42_compile_smoke(card);std::ofstream f(out/"receipt.json");f.exceptions(std::ios::badbit|std::ios::failbit);f<<"{\"passed\":true,\"infrastructure_passed\":true,\"kernel_execution\":false,\"kernels\":"<<n<<"}\n";f.close();return 0;}
  auto r=gemv_timing_gate(card,out);
  std::ofstream f(out/"receipt.json");f.exceptions(std::ios::badbit|std::ios::failbit);
  f<<"{\"passed\":true,\"infrastructure_passed\":true,\"device_executed\":" P42_DEVICE_EXECUTED ",\"reference_exact\":true,\"checks\":"<<r.checks<<",\"teardown\":"<<r.teardown<<"}\n";f.close();return 0;
 }catch(const std::exception&e){std::cerr<<"FAILED WINDOW: "<<e.what()<<std::endl;try{if(!out.empty()){std::ofstream f(out/"receipt.json");f.exceptions(std::ios::badbit|std::ios::failbit);f<<"{\"passed\":false,\"infrastructure_passed\":false,\"error\":"<<ownrt::quote(e.what())<<"}\n";f.close();}}catch(const std::exception&w){std::cerr<<"FAILED RECEIPT WRITE: "<<w.what()<<std::endl;}return 1;}
}
