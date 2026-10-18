// CPU byte oracle: compare decoded FP32, every ordered lane sum, tree, BF16,
// argmax and reversible storage. No backend or device is created.
#include "p93_kernel.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
int main(int argc,char**argv){try{
 if(argc!=3)throw std::runtime_error("view output");std::string view=argv[1];unsigned mode=view=="production"?0:view=="head-plane"?1:view=="head-transpose"?2:99;
 if(mode==99)throw std::runtime_error("view");std::filesystem::path dir=argv[2];
 // Exercise the loader's plane scatter across a full chunk and a remainder.
 {constexpr size_t blocks=4100;std::vector<uint8_t>raw(blocks*210),scattered(raw.size());for(size_t i=0;i<raw.size();++i)raw[i]=uint8_t(i*73+i/211);
  auto whole=p93::transpose(raw.data(),blocks);
  for(size_t first=0;first<blocks;first+=4096){size_t n=std::min(size_t(4096),blocks-first);auto chunk=p93::transpose(raw.data()+first*210,n);const size_t widths[4]={128,64,16,2},starts[4]={0,128,192,208};for(unsigned plane=0;plane<4;++plane)std::memcpy(scattered.data()+starts[plane]*blocks+first*widths[plane],chunk.data()+starts[plane]*n,n*widths[plane]);}
  if(whole!=scattered||p93::untranspose(scattered.data(),blocks)!=raw)throw std::runtime_error("chunked loader scatter failed");
 }
 std::ofstream expected(dir/"expected.bin",std::ios::binary),actual(dir/"candidate.bin",std::ios::binary),cases(dir/"cases.jsonl");
 uint64_t chains=0,trees=0,values=0;unsigned count=0;
 auto compare=[&](const void*a,const void*b,size_t n){expected.write(static_cast<const char*>(a),n);actual.write(static_cast<const char*>(b),n);if(std::memcmp(a,b,n))throw std::runtime_error("FP32/logit/argmax byte mismatch case "+std::to_string(count));};
 for(unsigned rows:{1u,2u,17u,33u})for(unsigned phase:{0u,2u})for(unsigned scenario=0;scenario<4;++scenario){
  const size_t blocks=size_t(rows)*10;std::vector<uint8_t> raw(blocks*210+phase);uint8_t*w=raw.data()+phase;uint32_t seed=93+rows+scenario;
  auto next=[&]{seed=seed*1664525u+1013904223u;return seed;};
  for(size_t i=0;i<blocks*210;++i)w[i]=next()>>24;
  for(size_t b=0;b<blocks;++b){uint16_t scale=scenario==0?uint16_t(0x2400+(next()%1024)):scenario==1?uint16_t(b%2?0x8001:1):scenario==2?uint16_t(b%2?0x8000:0):uint16_t(0x4000+(next()%512));std::memcpy(w+b*210+208,&scale,2);}
  auto expanded=iq3::expanded::expand(iq3::Type::Q6_K,w,blocks*210,p93::K);auto trans=p93::transpose(w,blocks);auto inverse=p93::untranspose(trans.data(),blocks);
  if(inverse.size()!=blocks*210||std::memcmp(w,inverse.data(),inverse.size()))throw std::runtime_error("reversible layout failed");
  std::vector<uint16_t>x(p93::K),ey(rows),ay(rows);
  for(unsigned k=0;k<p93::K;++k)x[k]=scenario==1?uint16_t(k%2?0x8001:1):scenario==2?uint16_t(k%2?0x8000:0):iq3::bf16_bits(float(int(next()%63)-31)/32.f);
  for(unsigned row=0;row<rows;++row){const auto*er=expanded.data()+size_t(row)*3380;
   for(unsigned k=0;k<p93::K;k+=8){float ev[8],av[8];float scale=iq3::bits_float(p74::word(er+p93::K+4*(k/16)));
    for(unsigned j=0;j<8;++j)ev[j]=scale*float(iq3::signed8(er[k+j]));
    if(mode==1)p93::decode8<1>(w,blocks,row,k,av);else if(mode==2)p93::decode8<2>(trans.data(),blocks,row,k,av);else std::memcpy(av,ev,sizeof ev);
    compare(ev,av,sizeof ev);values+=8;
   }
   // Both production head split1 and historical split4 traversal boundaries.
   for(unsigned split:{1u,4u}){float ep[4]{},ap[4]{};
    for(unsigned part=0;part<split;++part){auto bounds=iq3::kopt2::bounds(p93::K,part,split);float el[32],al[32];
     for(unsigned lane=0;lane<32;++lane){el[lane]=p33::dense_lane<iq3::Type::Q6_K,p93::K>(er,x.data(),bounds.first,bounds.second,lane);
      al[lane]=mode==1?p93::lane<1>(w,blocks,row,x.data(),bounds.first,bounds.second,lane):mode==2?p93::lane<2>(trans.data(),blocks,row,x.data(),bounds.first,bounds.second,lane):el[lane];}
     compare(el,al,sizeof el);chains+=32;
     for(unsigned width=1;width<32;width*=2){for(unsigned l=0;l<32;l+=2*width){el[l]=el[l]+el[l+width];al[l]=al[l]+al[l+width];}compare(el,al,sizeof el);trees+=32;}
     ep[part]=el[0];ap[part]=al[0];
    }
    float e=split==1?ep[0]:(ep[0]+ep[1])+(ep[2]+ep[3]),a=split==1?ap[0]:(ap[0]+ap[1])+(ap[2]+ap[3]);compare(&e,&a,4);
    uint16_t eb=iq3::bf16_bits(e),ab=iq3::bf16_bits(a);compare(&eb,&ab,2);if(split==1){ey[row]=eb;ay[row]=ab;}
   }
  }
  // Exercise the actual candidate host operation, including its output extent.
  if(mode){std::vector<uint16_t> y(rows);std::array<void*,3>p{mode==1?w:trans.data(),x.data(),y.data()};if(mode==1){p93::Kernel<1>op;op.rows=rows;op.run(p);}else{p93::Kernel<2>op;op.rows=rows;op.run(p);}compare(ey.data(),y.data(),rows*2);}
  auto argmax=[](const auto&y){unsigned best=0;for(unsigned i=1;i<y.size();++i)if(iq3::bits_float(uint32_t(y[i])<<16)>iq3::bits_float(uint32_t(y[best])<<16))best=i;return best;};unsigned ei=argmax(ey),ai=argmax(ay);compare(&ei,&ai,4);
  cases<<"{\"rows\":"<<rows<<",\"raw_alignment_phase\":"<<phase<<",\"scenario\":"<<scenario<<",\"split1_and_split4\":true,\"reversible\":true,\"passed\":true}\n";++count;
 }
 std::ofstream(dir/"native.json")<<"{\"passed\":true,\"cases\":"<<count<<",\"raw_fp32_chain_checks\":"<<chains<<",\"raw_fp32_tree_checks\":"<<trees<<",\"decoded_value_checks\":"<<values<<"}\n";
 std::cout<<"PASS "<<view<<" cases="<<count<<"\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
