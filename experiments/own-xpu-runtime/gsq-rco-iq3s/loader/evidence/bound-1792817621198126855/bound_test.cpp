// Pure CPU authority/read helper tests. Never calls authenticate on real model root.
#include "gguf.hpp"
#include "bound.hpp"
#include <algorithm>
#include <fstream>
#include <iostream>
#include <sstream>
unsigned checks=0;
void check(bool ok){if(!ok)throw std::runtime_error("bound fixture assertion");++checks;}
template<class F>void refuses(F f){bool failed=false;try{f();}catch(const std::runtime_error&){failed=true;}check(failed);}
std::string read(const std::filesystem::path&p){std::ifstream in(p,std::ios::binary);return {std::istreambuf_iterator<char>(in),{}};}
void put(const std::filesystem::path&p,std::string_view bytes){std::ofstream out(p,std::ios::binary|std::ios::trunc);out<<bytes;}
int main(int argc,char**argv){try{
  if(argc!=2)throw std::runtime_error("temporary root required");namespace b=gsq::bound;namespace fs=std::filesystem;fs::path root=argv[1],file=root/"data";
  auto plan=b::expected_plan();check(plan.size()==1224);std::ostringstream text;
  for(const auto&r:plan){text<<r.shard<<' '<<r.name<<' '<<r.component<<' '<<unsigned(r.type)<<' '<<r.offset<<' '<<r.bytes<<' '<<r.layer<<' '<<r.mask<<' '<<r.dimensions.size();for(auto d:r.dimensions)text<<' '<<d;text<<'\n';}
  check(text.str()==read(b::placement_path));std::ostringstream auth;
  for(const auto&s:b::shards)auth<<s.basename<<' '<<s.bytes<<' '<<s.dev<<' '<<s.ino<<' '<<s.mtime_ns<<' '<<s.ctime_ns<<'\n';
  check(auth.str()==read(b::auth_path));check(b::headers[0].bytes+b::headers[1].bytes==11024528);
  check(std::count_if(plan.begin(),plan.end(),[](const auto&r){return r.mask==3&&r.type==iq3::Type::BF16;})==194);
  put(file,"headerPAYLOAD");
  {b::HeldFile f(file);auto bytes=f.prefix(6,6);check(std::string(bytes.begin(),bytes.end())=="header");refuses([&]{f.prefix(7,6);});refuses([&]{f.prefix(100,100);});
   const auto&s=f.before;iq3::ShardIdentity identity{"data",uint64_t(s.st_size),uint64_t(s.st_dev),uint64_t(s.st_ino),uint64_t(s.st_mtim.tv_sec)*1000000000ULL+uint64_t(s.st_mtim.tv_nsec),uint64_t(s.st_ctim.tv_sec)*1000000000ULL+uint64_t(s.st_ctim.tv_nsec)};
   f.matches(identity);++checks;
   for(unsigned i=0;i<5;++i){auto bad=identity;if(i==0)++bad.bytes;if(i==1)++bad.dev;if(i==2)++bad.ino;if(i==3)++bad.mtime_ns;if(i==4)++bad.ctime_ns;refuses([&]{f.matches(bad);});}
   put(file,"changed");refuses([&]{f.stable();});refuses([&]{f.prefix(6,6);});
  }
  fs::create_symlink(file,root/"link");refuses([&]{b::HeldFile f(root/"link");});refuses([&]{b::HeldFile f(root);});
  put(file,"abc");auto identity_hash=[](const auto&bytes){return std::string(bytes.begin(),bytes.end());};
  auto name=file.string();b::verify_text(file,name.c_str(),"abc",identity_hash);++checks;
  refuses([&]{b::verify_text(file,"wrong","abc",identity_hash);});refuses([&]{b::verify_text(file,name.c_str(),"bad",identity_hash);});
  auto mutation_hash=[&](const auto&bytes){put(file,"abcd");return std::string(bytes.begin(),bytes.end());};
  refuses([&]{b::verify_text(file,name.c_str(),"abc",mutation_hash);});
  put(file,std::string(2*1024*1024+1,'x'));refuses([&]{b::verify_text(file,name.c_str(),"bad",identity_hash);});
  refuses([&]{b::authenticate(b::placement_path,b::auth_path,root,identity_hash);});
  std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"compiled_descriptors\":1224,\"actual_model_reads\":0,\"device_executed\":false,\"hash_scope\":\"injected string identity only for read-helper tests; no SHA implementation qualification\"}\n";
  return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
