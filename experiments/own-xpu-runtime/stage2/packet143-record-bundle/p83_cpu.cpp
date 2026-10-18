#include "p83_head.hpp"
#include <fstream>
#include <iostream>
#include <openssl/sha.h>
#include <iomanip>
struct Digest{SHA256_CTX c;Digest(){SHA256_Init(&c);}void add(const void*p,size_t n){SHA256_Update(&c,p,n);}std::string finish(){unsigned char b[32];SHA256_Final(b,&c);std::ostringstream s;for(auto v:b)s<<std::hex<<std::setfill('0')<<std::setw(2)<<unsigned(v);return s.str();}};
int main(int argc,char**argv){try{
 if(argc!=3)throw std::runtime_error("source offset");std::ifstream f(argv[1],std::ios::binary);f.seekg(std::stoull(argv[2]));if(!f)throw std::runtime_error("open source");
 constexpr unsigned K=2560,N=91392;std::vector<uint16_t>x(K);for(unsigned c=0;c<K;++c)x[c]=iq3::bf16_bits(float(int((c*17)%31)-15)/32.f);
 Digest source,quant,expected,actual;unsigned cases=0;
 for(unsigned begin=0;begin<N;begin+=256){unsigned nr=std::min(256u,N-begin);std::vector<uint8_t>raw(size_t(nr)*2100);f.read(reinterpret_cast<char*>(raw.data()),raw.size());if(!f)throw std::runtime_error("short source");source.add(raw.data(),raw.size());
  auto q=p83::quantize(iq3::Type::Q6_K,raw.data(),nr,K);quant.add(q.data(),q.size());std::vector<uint16_t>y(nr),ref(nr);p83::Head<K>op;op.rows=nr;std::array<void*,3>args{q.data(),x.data(),y.data()};op.run(args);
  for(unsigned r=0;r<nr;++r){float sums[32]{};for(unsigned c=0;c<K;++c){const auto*w=q.data()+size_t(r)*1600;float scale;std::memcpy(&scale,w+1280+(c/32)*4,4);int code=int((w[c/2]>>(4*(c%2)))&15)-8;if(code<-7||code>7||!std::isfinite(scale)||scale<=0)throw std::runtime_error("invalid Q4");float value=float(code)*scale;
   float original=iq3::decode(iq3::Type::Q6_K,raw.data()+size_t(r)*2100+(c/256)*210,c%256);
   if(std::abs(value-original)>scale*(0.50001f))throw std::runtime_error("quantization error exceeds half step");
   float product=value*iq3::bits_float(uint32_t(x[c])<<16);sums[c%32]=sums[c%32]+product;
  }
  for(unsigned width=1;width<32;width*=2)for(unsigned l=0;l<32;l+=2*width)sums[l]=sums[l]+sums[l+width];ref[r]=iq3::bf16_bits(sums[0]);}
  if(y!=ref)throw std::runtime_error("head reference mismatch");expected.add(ref.data(),ref.size()*2);actual.add(y.data(),y.size()*2);cases+=nr;
 }
 std::cout<<"{\"passed\":true,\"rows\":"<<cases<<",\"columns\":2560,\"source_sha256\":\""<<source.finish()<<"\",\"quantized_sha256\":\""<<quant.finish()<<"\",\"expected_sha256\":\""<<expected.finish()<<"\",\"actual_sha256\":\""<<actual.finish()<<"\"}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
