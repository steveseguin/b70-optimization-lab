// Packet183 real-weight S1 census (CPU only, host build). Reads the Q6_K
// tensors listed in a TSV (name, shard path, absolute file offset, K, rows)
// from the model's GGUF shards in bounded chunks, expands each chunk with the
// production loader (iq3::expanded::expand) and runs p183::census_q6 over every
// row: every fp16 d must be finite and every stored FP32 scale word must equal
// half(d)*float(signed8(sc)). On sampled real rows it also compares the S1 lanes
// with the production lanes bit for bit (all lanes, split 1 and 4, two inputs).
// No device, no write except the JSON on stdout; page cache dropped per chunk.
#include "s1_lanes.hpp"
#include <cstdio>
#include <fcntl.h>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <unistd.h>
#include <vector>
namespace {
void check(bool ok,const std::string& what){if(!ok)throw std::runtime_error(what);}
std::vector<uint16_t> input(unsigned K,unsigned pattern){std::vector<uint16_t> x(K);
 for(unsigned j=0;j<K;++j)x[j]=iq3::bf16_bits(pattern?float(int((j*37+11)%301)-150)/96.f:float(int((j*13)%257)-128)/64.f);return x;}
template<unsigned K> uint64_t lanes(const uint8_t* row){uint64_t n=0;
 for(unsigned pattern=0;pattern<2;++pattern){auto x=input(K,pattern);
  for(unsigned split:{1u,4u})for(unsigned part=0;part<split;++part){auto b=iq3::kopt2::bounds(K,part,split);
   for(unsigned lane=0;lane<32;++lane){
    float a=p33::dense_lane<iq3::Type::Q6_K,K>(row,x.data(),b.first,b.second,lane),m=p183::p33_lane<K>(row,x.data(),b.first,b.second,lane);
    float c=p49c::dense_lane<iq3::Type::Q6_K,K>(row,x.data(),b.first,b.second,lane),s=p183::p49c_lane<K>(row,x.data(),b.first,b.second,lane);
    check(std::bit_cast<uint32_t>(a)==std::bit_cast<uint32_t>(m)&&std::bit_cast<uint32_t>(c)==std::bit_cast<uint32_t>(s),"real-row lane mismatch");n+=2;}
   if constexpr(K==2560)for(unsigned physical=0;physical<8;++physical){
    auto u=p49dvirtual::dense_chains<iq3::Type::Q6_K,K,4>(row,x.data(),b.first,b.second,physical),v=p183::small_chains<K,4>(row,x.data(),b.first,b.second,physical);
    for(unsigned i=0;i<4;++i)check(std::bit_cast<uint32_t>(u[i])==std::bit_cast<uint32_t>(v[i]),"real-row small chain mismatch");n+=4;}
  }}
 return n;}
uint64_t lane_dispatch(unsigned K,const uint8_t* row){
 switch(K){case 2560:return lanes<2560>(row);case 6144:return lanes<6144>(row);case 10240:return lanes<10240>(row);}
 throw std::runtime_error("real census K outside S1 shapes");}
} // namespace
int main(int argc,char** argv){
 try{
  check(argc==2,"usage: real-census TENSORS.tsv");
  std::ifstream list(argv[1]);check(bool(list),"tensor list");
  p183::Census total;uint64_t tensors=0,lane_checks=0,sampled_rows=0,bytes_read=0;std::ostringstream per;
  std::string name,path;unsigned long long offset,K,rows;
  while(list>>name>>path>>offset>>K>>rows){
   check(K%256==0&&rows>0,"tensor geometry "+name);
   const size_t packed_row=size_t(K)/256*210,er=iq3::expanded::row_bytes(iq3::Type::Q6_K,K);
   int fd=open(path.c_str(),O_RDONLY|O_CLOEXEC);check(fd>=0,"open "+path);
   const size_t chunk=std::max<size_t>(1,(8u<<20)/packed_row);std::vector<uint8_t> raw;
   p183::Census t;std::vector<uint64_t> samples;
   for(uint64_t r:{0ull,1ull,rows/3,rows/2,rows-1}){if(r<rows&&(samples.empty()||samples.back()!=r))samples.push_back(r);}
   for(size_t first=0;first<rows;first+=chunk){const size_t n=std::min<size_t>(chunk,rows-first);raw.resize(n*packed_row);
    size_t got=0;const off_t at=off_t(offset+first*packed_row);
    while(got<raw.size()){ssize_t k=pread(fd,raw.data()+got,raw.size()-got,at+off_t(got));check(k>0,"short read "+name);got+=size_t(k);}
    posix_fadvise(fd,at,off_t(raw.size()),POSIX_FADV_DONTNEED);bytes_read+=raw.size();
    auto e=iq3::expanded::expand(iq3::Type::Q6_K,raw.data(),raw.size(),K);
    p183::census_add(t,p183::census_q6(e.data(),n,K));
    for(auto s:samples)if(s>=first&&s<first+n){lane_checks+=lane_dispatch(unsigned(K),e.data()+(s-first)*er);++sampled_rows;}
   }
   close(fd);p183::census_add(total,t);++tensors;
   per<<(tensors>1?",":"")<<"{\"name\":\""<<name<<"\",\"K\":"<<K<<",\"rows\":"<<rows<<",\"groups\":"<<t.groups<<",\"nonfinite_d\":"<<t.nonfinite<<",\"word_mismatches\":"<<t.mismatch<<"}";
  }
  check(tensors>0,"empty tensor list");
  const bool passed=!total.nonfinite&&!total.mismatch;
  std::cout<<"{\"passed\":"<<(passed?"true":"false")<<",\"device_executed\":false,\"tensors\":"<<tensors<<",\"rows\":"<<total.rows<<",\"blocks\":"<<total.blocks<<",\"groups\":"<<total.groups
           <<",\"nonfinite_d\":"<<total.nonfinite<<",\"word_mismatches\":"<<total.mismatch<<",\"packed_bytes_read\":"<<bytes_read<<",\"sampled_rows\":"<<sampled_rows<<",\"lane_checks\":"<<lane_checks<<",\"per_tensor\":["<<per.str()<<"]}"<<std::endl;
  return passed?0:3;
 }catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 1;}
}
