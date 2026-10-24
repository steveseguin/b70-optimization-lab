#define GSQ_BUNDLE_TESTING
#include "bundle.hpp"
#include <iostream>
static std::string fault;
static void fail_at(const char*point){if(fault==point)throw std::runtime_error("injected "+fault);}
int main(int argc,char**argv){
 try{
  gsq_bundle::need(argc==3,"fixture arguments");std::string mode=argv[1];std::filesystem::path dir=argv[2];std::filesystem::create_directories(dir);
  std::vector<uint8_t>a(mode.starts_with("tiny-")?257:70001),b={0,255,17,128};for(size_t i=0;i<a.size();++i)a[i]=uint8_t((i*37+11)%256);
  if(mode=="mismatch")a[27]^=1;
  if(mode.starts_with("fail:")){fault=mode.substr(5);gsq_bundle::test_hook=fail_at;}
  std::string state="{\"history0\":"+std::string(mode=="metadata-mismatch"?"9":"1")+",\"history1\":2,\"buffers\":{\"tensor\":\""+gsq_bundle::digest(a.data(),a.size())+"\",\"alternate:carry\":\""+gsq_bundle::digest(b.data(),b.size())+"\"},\"fp32_cache_valid\":false,\"fp32_extent\":0}";
  gsq_bundle::Writer writer(dir);writer.append("tensor.bin",a.data(),a.size());
  if(mode=="duplicate")writer.append("tensor.bin",a.data(),a.size());
  if(mode!="missing")writer.append("alternate-carry.bin",b.data(),b.size());
  writer.finish(state);std::cout<<"{\"passed\":true,\"reply_success\":true}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}
}
