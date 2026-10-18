// CPU-only streaming generator/replay of the unchanged single-row draft chain.
#include "token_input.hpp"
#include "kernels.hpp"
#include "p28/dense.hpp"
#include "../packet2/loader/gguf.hpp"
#include <fstream>
#include <iostream>
#include <filesystem>
#include <cstring>
#include <omp.h>
using namespace std;
static vector<uint8_t> bytes(const char* path,size_t expected){ifstream f(path,ios::binary);vector<uint8_t>b(expected);f.read((char*)b.data(),b.size());if(!f||f.peek()!=EOF)throw runtime_error("input extent");return b;}
static void row(const uint8_t* raw,const float* gain,const uint8_t* weight,uint16_t* out){
 array<uint16_t,2560> embedding{},candidate{},norm{};array<float,2560> scratch{};
 for(unsigned k=0;k<2560;++k)embedding[k]=iq3::bf16_bits(iq3::element(iq3::Type::Q6_K,raw,k));
 p137::decode(iq3::Type::Q6_K,raw,2560,candidate.data());
 if(candidate!=embedding)throw runtime_error("embedding block decode differs");
 int error=0,pos=0,active=1;ng::Shape s{ng::norm};s.width=2560;s.heads=1;s.flags=8;
 ng::Args a;a.p[0]=embedding.data();a.p[1]=const_cast<float*>(gain);a.p[2]=norm.data();a.p[15]=&error;a.p[17]=&pos;a.p[18]=&active;
 ng::group(s,a,0,ng::HostTeam{scratch.data()});
 for(unsigned r=0;r<2560;++r)out[r]=iq3::bf16_bits(p28::dense_row<iq3::Type::BF16,2560>(weight+size_t(r)*5120,norm.data(),1));
}
int main(int argc,char**argv){try{
 if(argc!=9)throw runtime_error("mode model-root identity plan norm projection table count");
 string mode=argv[1];if(mode!="generate"&&mode!="verify")throw runtime_error("mode");
 unsigned count=stoul(argv[8]);if(count>p137::vocab||!count)throw runtime_error("count");
 ifstream ids(argv[3]);string name;uint64_t size,dev,ino,mtime,ctime;vector<filesystem::path>paths;
 while(ids>>name>>size>>dev>>ino>>mtime>>ctime)paths.push_back(filesystem::path(argv[2])/name);
 if(!ids.eof()||paths.size()!=3)throw runtime_error("identity");
 iq3::Model model(paths,iq3::read_plan(argv[4]));auto n=bytes(argv[5],5120),w=bytes(argv[6],13107200);
 array<float,2560> gain{};for(unsigned i=0;i<2560;++i)gain[i]=1.f+iq3::bits_float(uint32_t(iq3::u16(n.data()+2*i))<<16);
 fstream file(argv[7],ios::binary|(mode=="generate"?ios::out|ios::trunc:ios::in));if(!file)throw runtime_error("table open");
 constexpr unsigned chunk=32;array<uint16_t,chunk*2560> output{},expected{};
 for(unsigned begin=0;begin<count;begin+=chunk){unsigned rows=min(chunk,count-begin);auto raw=model.slice("token_embd.weight",size_t(begin)*2100,rows*2100);
  #pragma omp parallel for schedule(static) num_threads(8)
  for(unsigned i=0;i<rows;++i)row(raw.data()+i*2100,gain.data(),w.data(),output.data()+i*2560);
  if(mode=="generate")file.write((char*)output.data(),rows*5120);
  else {file.read((char*)expected.data(),rows*5120);if(memcmp(output.data(),expected.data(),rows*5120))throw runtime_error("table replay differs at chunk "+to_string(begin));}
  if(!file)throw runtime_error("table I/O");
  if(begin%4096==0)cout<<"rows "<<begin+rows<<"/"<<count<<endl;
 }
 if(mode=="verify"&&file.peek()!=EOF)throw runtime_error("trailing table data");
 cout<<"{\"passed\":true,\"rows\":"<<count<<",\"bytes\":"<<uint64_t(count)*5120<<",\"original_single_row_chain\":true}"<<endl;return 0;
 }catch(const exception&e){cerr<<e.what()<<endl;return 1;}}
