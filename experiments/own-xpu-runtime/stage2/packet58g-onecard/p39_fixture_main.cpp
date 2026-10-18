#include "adapter_fixture.hpp"
#include <iostream>
#include <fstream>
int main(int argc,char**argv){if(argc!=2)return 2;try{std::filesystem::create_directories(argv[1]);auto r=p39_fixture_gate(0,argv[1],false);std::ofstream(std::filesystem::path(argv[1])/"receipt.json")<<"{\"passed\":true,\"device_executed\":false,\"checks\":"<<r.checks<<",\"teardown\":"<<r.teardown<<"}\n";std::cout<<r.checks<<" merged epilogue exactness checks passed\n";return 0;}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
