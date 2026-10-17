// Reference uses the sealed parent's implementation, not the candidate's copy.
#include "../packet56-draft-prefix/p33_candidates.hpp"
#include <fstream>
#include <vector>
int main(int argc,char**argv){
 if(argc!=2)return 2;
 constexpr unsigned rows=257,k=2560;size_t stride=iq3::expanded::row_bytes(iq3::Type::Q6_K,k);
 std::vector<uint8_t>w(rows*stride);uint32_t seed=59;
 for(auto&b:w){seed=1664525u*seed+1013904223u;b=seed>>24;}
 for(unsigned r=0;r<rows;++r)for(unsigned g=0;g<k/16;++g){float s=float(int((r+g)%7)-3)/256.f;std::memcpy(w.data()+r*stride+k+4*g,&s,4);}
 std::vector<uint16_t>x(k),y(rows);for(unsigned j=0;j<k;++j)x[j]=iq3::bf16_bits(float(int((j*17)%127)-63)/128.f);
 for(unsigned r=0;r<rows;++r){float sums[32];for(unsigned l=0;l<32;++l)sums[l]=p33::dense_lane<iq3::Type::Q6_K,k>(w.data()+r*stride,x.data(),0,k,l);y[r]=iq3::bf16_bits(iq3::tree32(sums));}
 std::ofstream f(argv[1],std::ios::binary);f.write(reinterpret_cast<const char*>(y.data()),y.size()*2);return f?0:1;
}
