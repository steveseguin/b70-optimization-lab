#pragma once
#include "../kernels.hpp"
#include "../../packet9-kopt4/tests/expert_case.hpp"
namespace dense_test {
using namespace iq3;
using namespace expert_test;
template<class Launch> void exercise_dense(Launch launch,ownrt::Device& d,const Fixture& f,unsigned mutation,unsigned split,bool head=false){
 Buffers b(d,"dense/"+std::to_string(unsigned(f.type))+"/"+std::to_string(mutation)+"/"+std::to_string(split)+"/"+std::to_string(head));
 auto ex=expanded::expand(f.type,f.packed.data(),f.packed.size(),f.columns);size_t rb=expanded::row_bytes(f.type,f.columns);unsigned n=head?248320:f.rows-(mutation?1:0);
 kopt3::Matrix m; m.type=f.type;m.rows=n;m.columns=f.columns;m.activation=f.activation;m.output_type=f.output_type;
 auto alloc=[&](const char* name,size_t bytes){return b.allocate(name,bytes,ownrt::Category::scratch);};
 m.w=b.allocate("weights",n*rb,ownrt::Category::weights);
 if(!head)b.upload(m.w,ex.data(),n*rb,"weight-stage");
 else{constexpr size_t chunk=8*1024*1024;auto slab=b.slab("head-stage",chunk);auto ptr=static_cast<uint8_t*>(d.arena.row(slab).pointer);
  for(size_t off=0;off<n*rb;){require(!stopping,"stop during head upload");size_t len=std::min(chunk,n*rb-off);for(size_t i=0;i<len;++i)ptr[i]=ex[(off+i)%ex.size()];wait(d,b.copy.copy(m.w,off,slab,0,len,{}));off+=len;}
 }
 auto x=f.x;if(mutation)for(auto& v:x)v^=0x8000;
 m.x=alloc("x",x.size()*2);b.upload(m.x,x.data(),x.size()*2,"x-stage");m.y=alloc("y",n*2);m.fp32=alloc("fp",n*4);
 std::vector<float> expected(n);std::vector<uint16_t> rounded(n);
 for(unsigned r=0;r<std::min(n,f.rows);++r)expected[r]=kopt2::row(f.type,f.packed.data()+r*f.row_bytes(),x.data(),f.activation,f.columns,split==1?kopt2::Variant::wide32:kopt2::Variant::split4);
 for(unsigned r=0;r<n;++r){expected[r]=expected[r%f.rows];rounded[r]=output_bits(expected[r],f.output_type);}
 require(!stopping,"cooperative stop before dense");wait(d,launch(d,m,split).last);
 b.equal(m.fp32,expected.data(),n*4,"FP32");b.equal(m.y,rounded.data(),n*2,"rounded");b.release();
}
}
