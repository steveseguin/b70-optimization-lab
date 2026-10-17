// Real linked head/argmax operations on small CPU allocations; no model/device.
#ifndef OWN_RT_HOST_ONLY
#error CPU only
#endif
#define main unused_p33_fixture_entry
#include "p33_linked_fixture.cpp"
#undef main
#include "p69_head.hpp"
#include "p56_prefix.hpp"
#include "round2_submit.hpp"

int packet26_model_entry(int argc,char**argv) {
 try {
  if(argc!=2)return 2;
  std::ofstream out(argv[1],std::ios::binary);
  Runner r(0,120);unsigned checks=0;
  for(unsigned rows:{1u,2u,3u,33u,65u,1025u})for(unsigned mode:{0u,1u,2u,3u}) {
   Matrix m{};m.type=iq3::Type::Q6_K;m.columns=2560;m.rows=m.span=rows;
   auto w=weights(m.type,m.columns,rows,6,mode);auto x=inputs(m.columns,mode);
   m.w=r.upload(w.data(),w.size());m.x=r.upload(x.data(),x.size()*2);
   std::vector<uint16_t> poisoned(rows+16,0x7fc1);
   m.y=r.upload(poisoned.data(),poisoned.size()*2);m.workspace=r.alloc(size_t(rows)*32);
   auto data=[&](Allocation a){return r.device.arena.row(a).pointer;};
   r.finish(p33::submit(r.device,{m},"p33.dense.segment",false,6).last);
   std::vector<uint16_t> expected(rows);std::memcpy(expected.data(),data(m.y),rows*2);
   Spec s{};s.op=Op::argmax;s.implementation=2;s.ni=s.no=1;
   s.sizes[0]=rows;s.sizes[1]=1;s.types[0]=flash::Scalar::bf16;s.types[1]=flash::Scalar::i32;
   auto token=r.alloc(4),scratch=r.alloc(size_t(rows+128)*4),error=r.alloc(4),position=r.alloc(4),active=r.alloc(4),rope=r.alloc(4);
   *static_cast<uint32_t*>(data(error))=0;*static_cast<uint32_t*>(data(position))=0;
   *static_cast<uint32_t*>(data(active))=1;*static_cast<uint32_t*>(data(rope))=0;
   std::array<Allocation,7> bindings{m.y,token,scratch,error,position,active,rope};
   for(const char* choice:{"wide64","wide128"})for(unsigned prefix:{rows,std::max(1u,rows/2)}) {
    auto mm=m;p56::restrict_matrix(mm,prefix);auto ss=s;p56::restrict_argmax(ss,prefix);
    std::memcpy(data(m.y),poisoned.data(),poisoned.size()*2);
    *static_cast<uint32_t*>(data(error))=0;
    r.finish(p69::head(r.device,mm,choice).last);
    auto actual=static_cast<uint16_t*>(data(m.y));
    if(std::memcmp(expected.data(),actual,prefix*2)) {
     std::cerr<<"rows="<<rows<<" mode="<<mode<<" choice="<<choice<<" prefix="<<prefix<<'\n';
     for(unsigned j=0;j<prefix;++j)if(expected[j]!=actual[j]) {
      auto scalar=p69::row(w.data()+size_t(j)*p69::row_bytes(),x.data());
      std::cerr<<"row="<<j<<" expected="<<std::hex<<expected[j]<<" actual="<<actual[j]
               <<" scalar="<<iq3::bf16_bits(scalar)<<std::dec<<'\n';break;
     }
     r.finish(round2::submit_simple(r.device,ss,bindings,{}).last);
     std::cerr<<"production argmax sticky error="<<*static_cast<uint32_t*>(data(error))<<'\n';
     throw std::runtime_error("wide head bytes differ");
    }
    for(unsigned j=prefix;j<poisoned.size();++j)check(actual[j]==0x7fc1,"head overwrote prefix/sentinel");
    r.finish(round2::submit_simple(r.device,ss,bindings,{}).last);
    check(!*static_cast<uint32_t*>(data(error)),"finite head raised sticky error");
    int best=0;for(unsigned j=1;j<prefix;++j)if(iq3::bits_float(uint32_t(expected[j])<<16)>iq3::bits_float(uint32_t(expected[best])<<16))best=j;
    check(*static_cast<int*>(data(token))==best,"argmax/tie rule differs");
    out.write(reinterpret_cast<char*>(actual),prefix*2);out.write(reinterpret_cast<char*>(&best),4);
    // Exercise the actual sticky writer, including suffix exclusion and reset
    // refusal semantics: fixing logits must never clear an existing error.
    actual[0]=0x7fc1;
    r.finish(round2::submit_simple(r.device,ss,bindings,{}).last);
    check(*static_cast<uint32_t*>(data(error))==1,"argmax failed to reject NaN");
    actual[0]=expected[0];
    r.finish(round2::submit_simple(r.device,ss,bindings,{}).last);
    check(*static_cast<uint32_t*>(data(error))==1,"argmax cleared sticky error");
    ++checks;
   }
   r.clear();
  }
  check(r.device.shutdown(std::chrono::seconds(5)).safe_to_exit,"CPU teardown");
  std::cout<<"PASS "<<checks<<" linked head/prefix/argmax/status cases\n";
  return out?0:1;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
}
