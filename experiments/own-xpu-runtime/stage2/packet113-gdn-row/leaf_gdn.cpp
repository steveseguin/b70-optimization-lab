#include "recurrence_cases.hpp"
#include "failure.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
using p113test::Data;
void check(bool x,const std::string&s){if(!x)throw std::runtime_error(s);}
int main(int argc,char**argv){try{
 check(argc==3,"view output");std::filesystem::path out=argv[2];
 std::ofstream expected(out/"expected.txt"),actual(out/"candidate.txt"),cases(out/"cases.jsonl");
 unsigned guard_checks=0;
 for(int active:{-1,0,1})for(int error:{0,1,7})for(int pos:{-1,0,4093,4095,4096})for(int tokens:{1,4}){
  int expected_guard=(!active||error)?1:(pos<0||pos>4096-tokens)?2:0;
  check(p82brec::entry_decision(active,error,pos,4096,tokens)==expected_guard,"guard semantics");++guard_checks;
 }
 check(guard_checks==90,"guard coverage");
 unsigned checks=0,tokens_checked=0;size_t bytes_checked=0;
 auto compare=[&](const Data&a,const Data&b,const std::string&desc,unsigned tokens){auto x=a.bytes(),y=b.bytes();
  // Raw comparison comes first. Digest transcripts bound the exact compared bytes
  // without retaining hundreds of MB of synthetic state copies.
  if(x!=y){unsigned printed=0;for(size_t j=0;j<x.size()&&printed<12;++j)if(x[j]!=y[j]){std::cerr<<desc<<" byte="<<j<<" expected="<<unsigned(x[j])<<" actual="<<unsigned(y[j])<<"\n";++printed;}}check(x==y,desc);if(desc.find("-s6-")!=std::string::npos&&std::getenv("P82_EXCEPTION_DUMP")){std::ofstream raw(out/(desc+".raw"),std::ios::binary);raw.write(reinterpret_cast<const char*>(x.data()),x.size());}expected<<packet26::hash(x.data(),x.size())<<'\n';actual<<packet26::hash(y.data(),y.size())<<'\n';
  cases<<"{\"case\":\""<<desc<<"\",\"bytes\":"<<x.size()<<",\"tokens\":"<<tokens<<",\"passed\":true}\n";++checks;tokens_checked+=tokens;bytes_checked+=x.size();};
 auto run=[](bool candidate,ng::Shape s,Data&d,bool alias){if(candidate)p113rec::host(s,d.args(alias));else p82brec::host<true>(s,d.args(alias));};
 check(p113test::cases(run,compare)==768,"case coverage");
 std::ofstream(out/"native.json")<<"{\"passed\":true,\"cases\":"<<checks<<",\"tokens_checked\":"<<tokens_checked<<",\"bytes_compared\":"<<bytes_checked<<",\"full_state_elements\":786432,\"raw_bytes_compared\":true,\"transcript\":\"sha256 after raw equality\"}\n";
 std::cout<<checks<<" full-state checks PASS\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
