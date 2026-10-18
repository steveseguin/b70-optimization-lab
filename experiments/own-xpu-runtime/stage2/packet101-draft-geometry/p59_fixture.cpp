#ifndef OWN_RT_HOST_ONLY
#error CPU only
#endif
#include "p59_hc.hpp"
#include <fstream>
// Small synthetic production-K fixtures. At most 3 MB, no real model data.
static void write(std::ofstream&f,const std::vector<uint16_t>&v){f.write(reinterpret_cast<const char*>(v.data()),v.size()*2);}
template<unsigned K,bool I,bool Pair,unsigned V,unsigned Split>void dense(std::ofstream&out,p59::Tail tail,unsigned batch=1){
 constexpr unsigned rows=16,experts=2;size_t rb=I?K+K/16*4:K*2;
 std::vector<uint8_t>w(experts*rows*rb),peer(w.size());std::vector<uint16_t>x(batch*K),y(batch*rows),py(y.size()),fused(y.size()*(tail==p59::attention?4:1)),other(y.size()),inject(4,iq3::bf16_bits(.25f));
 for(unsigned e=0;e<experts;++e)for(unsigned r=0;r<rows;++r){auto off=(e*rows+r)*rb;for(unsigned k=0;k<K;++k){if constexpr(I){w[off+k]=uint8_t(int(k*7+r*3+e)%31-15);peer[off+k]=uint8_t(int(k*11+r+e)%31-15);}else{uint16_t v=iq3::bf16_bits(float(int((k*7+r*3+e)%31)-15)/64);std::memcpy(w.data()+off+2*k,&v,2);std::memcpy(peer.data()+off+2*k,&v,2);}}if constexpr(I)for(unsigned k=0;k<K/16;++k){float scale=float(1+k%3)/128;std::memcpy(w.data()+off+K+4*k,&scale,4);std::memcpy(peer.data()+off+K+4*k,&scale,4);}}
 for(unsigned i=0;i<x.size();++i)x[i]=iq3::bf16_bits(float(int(i%29)-14)/32);for(unsigned i=0;i<other.size();++i)other[i]=iq3::bf16_bits(float(int(i%7)-3)/16);
 std::vector<iq3::Route>routes(batch);for(unsigned i=0;i<batch;++i)routes[i]={i%2,0,rows};std::vector<uint32_t>status(batch),ps(batch);
 p59::Dense<K,I,Pair,V,Split>op;op.a.rows=rows;op.a.batch=batch;op.a.experts=experts;op.a.routes=1;op.a.tail=tail;
 std::array<void*,11>p{w.data(),peer.data(),x.data(),y.data(),py.data(),routes.data(),status.data(),ps.data(),fused.data(),other.data(),inject.data()};op.run(p);write(out,y);write(out,py);write(out,fused);
}
int main(int argc,char**argv){if(argc!=2)return 1;std::ofstream out(argv[1],std::ios::binary);
 dense<2560,true,true,8,1>(out,p59::product,2);dense<640,true,false,16,1>(out,p59::none,2);
 dense<10240,false,false,1,4>(out,p59::low);dense<6144,false,false,1,4>(out,p59::attention);
 dense<2560,false,false,1,1>(out,p59::merge_add,4);dense<2560,false,false,1,1>(out,p59::product);
 dense<320,false,false,4,1>(out,p59::none);dense<4,false,false,1,1>(out,p59::low);
 for(unsigned width:{16u,2560u,10240u}){std::vector<uint16_t>x(width*4),y(x.size());std::vector<float>gain(x.size());for(unsigned i=0;i<x.size();++i){x[i]=iq3::bf16_bits(float(int(i%47)-23)/64);gain[i]=1+float(i%3)/128;}p59::Norm op;op.rows=4;op.width=width;std::array<void*,3>p{x.data(),gain.data(),y.data()};op.run(p);write(out,y);}
 {constexpr unsigned width=16,k=320;std::vector<uint16_t>w(width*4*k),x(k),y(width*4),normed(width*4),mix(width);for(unsigned i=0;i<w.size();++i)w[i]=iq3::bf16_bits(float(int(i%31)-15)/64);for(unsigned i=0;i<k;++i)x[i]=iq3::bf16_bits(float(int(i%17)-8)/16);for(auto&v:normed)v=iq3::bf16_bits(.25f);p59::GateMix<k>op;op.width=width;std::array<void*,5>p{w.data(),x.data(),y.data(),normed.data(),mix.data()};op.run(p);write(out,y);write(out,mix);}
 return out?0:2;}
