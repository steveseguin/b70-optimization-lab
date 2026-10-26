// CPU proof for OWNRT_DENSE_RAW (dense-raw lab, 2026-10-26). For every element of every affected tensor of the model
// (list_tensors.py: the GSQ logits head and every weight of the p33 attention-Q8 / QKV-Q6 / dense-Q6 policies), read
// from the GGUF:
//  1. expanded = iq3::expanded::expand(...)      the engine's load-time transform (the rows the default build uploads);
//  2. raw      = denseraw::repack(...)           the rows the raw build uploads;
//  3. the raw decoder's 8-column values (denseraw::decode8, the code the kernels run, host-compiled) must equal, as bits,
//     (a) scale*float(signed8(code)) read from the expanded row (what the p33 expanded kernels compute), and
//     (b) iq3::expanded::value(t,row,k,i)        (the engine's CPU reference value of an expanded element);
//  4. raw rows must be a permutation of the GGUF bytes: un-repacking them gives the GGUF rows back;
//  5. the p183 census over the expanded Q6_K rows (finite d, scale words equal the metadata product) must pass.
// Also counts the fp16 d classes (subnormal / zero / non-finite) that the device conversion must handle.
// Build: g++ -std=c++20 -O2 -fno-fast-math -ffp-contract=off -fopenmp -I engine/src prove_dense_raw.cpp
#include "stage2/packet10-kopt5/expanded.hpp"
#include "stage2/packet194-expert-diet-engine/dense_raw.hpp"
#include <algorithm>
#include <atomic>
#include <cstdio>
#include <fcntl.h>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <unistd.h>
#include <vector>
using iq3::Type;
static std::vector<uint8_t> unrepack(Type t,const uint8_t* raw,size_t rows,size_t k){
 // Inverse of denseraw::repack_row (the layout described in dense_raw.hpp), written independently of it.
 static constexpr unsigned high_bit[8]{6,14,2,10,4,12,0,8};
 const size_t rb=denseraw::row_bytes(t,k);std::vector<uint8_t> out(rows*rb,0);
 for(size_t r=0;r<rows;++r){const uint8_t* s=raw+r*rb;uint8_t* d=out.data()+r*rb;
  if(t==Type::Q8_0){for(size_t b=0;b<k/32;++b){d[34*b]=s[k+2*b];d[34*b+1]=s[k+2*b+1];std::memcpy(d+34*b+2,s+32*b,32);}continue;}
  for(size_t b=0;b<k/256;++b){uint8_t* blk=d+210*b;const size_t p=b/2,o=b%2;
   for(unsigned l=0;l<32;++l){uint32_t low;std::memcpy(&low,s+256*p+8*l+4*o,4);const uint32_t high=iq3::u16(s+k/2+128*p+4*l+2*o);
    for(unsigned j=0;j<8;++j){const unsigned i=8*l+j;const unsigned lo=(low>>(j<4?8*j:8*(j-4)+4))&15,hi=((high>>high_bit[j])&3)^2u;
     blk[(i/128)*64+i%64]|=uint8_t(lo<<(4*((i%128)/64)));blk[128+(i/128)*32+i%32]|=uint8_t(hi<<(2*((i%128)/32)));}}
   for(unsigned g=0;g<16;++g)blk[192+g]=s[3*(k/4)+32*p+2*g+o];blk[208]=s[13*(k/16)+4*p+2*o];blk[209]=s[13*(k/16)+4*p+2*o+1];}}
 return out;
}
struct Totals{uint64_t elements=0,bad_a=0,bad_b=0,bad_bytes=0,census_bad=0,d_total=0,d_sub=0,d_zero=0,d_nonfinite=0,tensors=0;size_t expanded=0,raw=0;};
int main(int argc,char** argv){
 if(argc<2){std::fprintf(stderr,"usage: %s affected.tsv\n",argv[0]);return 2;}
 std::ifstream list(argv[1]);std::string line;Totals all;std::map<std::string,Totals> by_class;
 while(std::getline(list,line)){
  std::istringstream f(line);std::string name,file;size_t offset,bytes,rows,cols;unsigned type;
  std::getline(f,name,'\t');std::getline(f,file,'\t');f>>offset>>bytes>>type>>rows>>cols;const Type t=Type(type);
  if(!denseraw::supported(t,cols)||bytes!=rows*denseraw::row_bytes(t,cols)){std::fprintf(stderr,"%s: unsupported geometry\n",name.c_str());return 1;}
  const int fd=::open(file.c_str(),O_RDONLY);if(fd<0){perror(file.c_str());return 1;}
  std::vector<uint8_t> src(bytes);for(size_t got=0;got<bytes;){ssize_t n=::pread(fd,src.data()+got,bytes-got,off_t(offset+got));if(n<=0){perror("pread");return 1;}got+=size_t(n);}::close(fd);
  const size_t rb=denseraw::row_bytes(t,cols),erb=iq3::expanded::row_bytes(t,cols);Totals tt;tt.tensors=1;tt.expanded=rows*erb;tt.raw=rows*rb;
  const size_t chunk=4096;uint64_t elements=0,bad_a=0,bad_b=0,bad_bytes=0,d_total=0,d_sub=0,d_zero=0,d_nonfinite=0;
  #pragma omp parallel for schedule(dynamic,1) reduction(+:elements,bad_a,bad_b,bad_bytes,d_total,d_sub,d_zero,d_nonfinite)
  for(size_t first=0;first<rows;first+=chunk){const size_t n=std::min(chunk,rows-first);const uint8_t* s=src.data()+first*rb;
   const auto expanded=iq3::expanded::expand(t,s,n*rb,cols);const auto raw=denseraw::repack(t,s,n*rb,cols);
   bad_a+=denseraw::check_rows(t,raw.data(),expanded.data(),n,cols,erb);elements+=uint64_t(n)*cols;
   for(size_t r=0;r<n;++r){const uint8_t* w=raw.data()+r*rb;const uint8_t* e=expanded.data()+r*erb;
    for(uint32_t tile=0;tile<cols;tile+=8){float v[8];if(t==Type::Q6_K)denseraw::decode8<Type::Q6_K>(w,uint32_t(cols),tile/256,(tile%256)/8,v);else denseraw::decode8<Type::Q8_0>(w,uint32_t(cols),tile/256,(tile%256)/8,v);
     for(unsigned j=0;j<8;++j){const float ref=iq3::expanded::value(t,e,cols,tile+j);bad_b+=std::bit_cast<uint32_t>(ref)!=std::bit_cast<uint32_t>(v[j]);}}
    const unsigned block=t==Type::Q6_K?256:32,dat=t==Type::Q6_K?13*(unsigned(cols)/16):unsigned(cols);
    for(size_t b=0;b<cols/block;++b){const uint32_t d=iq3::u16(w+dat+2*b),e5=(d>>10)&31,m=d&1023;++d_total;if(e5==31)++d_nonfinite;else if(!e5&&m)++d_sub;else if(!e5)++d_zero;}}
   const auto back=unrepack(t,raw.data(),n,cols);bad_bytes+=!std::equal(back.begin(),back.end(),s);
  }
  tt.elements=elements;tt.bad_a=bad_a;tt.bad_b=bad_b;tt.bad_bytes=bad_bytes;tt.d_total=d_total;tt.d_sub=d_sub;tt.d_zero=d_zero;tt.d_nonfinite=d_nonfinite;
  if(t==Type::Q6_K){ // p183 census, as the loader runs it (finite d; stored scale word == recomputed metadata product)
   for(size_t first=0;first<rows;first+=chunk){const size_t n=std::min(chunk,rows-first);const auto expanded=iq3::expanded::expand(t,src.data()+first*rb,n*rb,cols);
    const uint8_t* base=expanded.data();
    for(size_t r=0;r<n;++r){const uint8_t* w=base+r*erb;const uint8_t* meta=w+cols+4*(cols/16);
     for(size_t b=0;b<cols/256;++b){const uint32_t d=iq3::u16(meta+18*b);if(((d>>10)&31)==31)++tt.census_bad;
      for(unsigned g=0;g<16;++g){const float s=iq3::half(d)*float(iq3::signed8(meta[18*b+2+g]));if(std::bit_cast<uint32_t>(s)!=iq3::u32(w+cols+4*(b*16+g)))++tt.census_bad;}}}}
  }
  const std::string cls=name=="output.weight"?"head Q6_K":t==Type::Q8_0?"attention Q8_0":rows==10240?"gdn.qkv Q6_K":rows==6144?"gdn.z Q6_K":"qsa.qgate Q6_K";
  auto add=[&](Totals& a){a.elements+=tt.elements;a.bad_a+=tt.bad_a;a.bad_b+=tt.bad_b;a.bad_bytes+=tt.bad_bytes;a.census_bad+=tt.census_bad;a.d_total+=tt.d_total;a.d_sub+=tt.d_sub;a.d_zero+=tt.d_zero;a.d_nonfinite+=tt.d_nonfinite;a.tensors+=1;a.expanded+=tt.expanded;a.raw+=tt.raw;};
  add(all);add(by_class[cls]);
  std::printf("%-28s %-6s %6zu x %5zu  elements %10llu  value_mismatch %llu/%llu  byte_permutation_bad %llu  census_bad %llu  d sub %llu zero %llu nonfinite %llu\n",
   name.c_str(),t==Type::Q6_K?"Q6_K":"Q8_0",rows,cols,(unsigned long long)tt.elements,(unsigned long long)tt.bad_a,(unsigned long long)tt.bad_b,(unsigned long long)tt.bad_bytes,(unsigned long long)tt.census_bad,
   (unsigned long long)tt.d_sub,(unsigned long long)tt.d_zero,(unsigned long long)tt.d_nonfinite);std::fflush(stdout);
 }
 std::printf("\n%-16s %7s %14s %12s %12s %10s %10s %14s %14s %12s\n","class","tensors","elements","mismatch_a","mismatch_b","perm_bad","census","expanded_B","raw_B","d_subnormal");
 for(auto& [k,v]:by_class)std::printf("%-16s %7llu %14llu %12llu %12llu %10llu %10llu %14zu %14zu %12llu\n",k.c_str(),(unsigned long long)v.tensors,(unsigned long long)v.elements,(unsigned long long)v.bad_a,(unsigned long long)v.bad_b,(unsigned long long)v.bad_bytes,(unsigned long long)v.census_bad,v.expanded,v.raw,(unsigned long long)v.d_sub);
 std::printf("%-16s %7llu %14llu %12llu %12llu %10llu %10llu %14zu %14zu %12llu\n","ALL",(unsigned long long)all.tensors,(unsigned long long)all.elements,(unsigned long long)all.bad_a,(unsigned long long)all.bad_b,(unsigned long long)all.bad_bytes,(unsigned long long)all.census_bad,all.expanded,all.raw,(unsigned long long)all.d_sub);
 const bool pass=!all.bad_a&&!all.bad_b&&!all.bad_bytes&&!all.census_bad&&!all.d_nonfinite&&all.tensors==90;
 std::printf("PROOF %s: %llu elements of %llu tensors, d blocks %llu (subnormal %llu, zero %llu, non-finite %llu)\n",pass?"PASSED":"FAILED",(unsigned long long)all.elements,(unsigned long long)all.tensors,
  (unsigned long long)all.d_total,(unsigned long long)all.d_sub,(unsigned long long)all.d_zero,(unsigned long long)all.d_nonfinite);
 return pass?0:1;
}
