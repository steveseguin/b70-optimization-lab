#pragma once
#include "p104_small.hpp"
// Included after the shared micro helpers. Preserve the complete selected tuple.
template<iq3::Type T,bool Tiled>inline float small_raw(const uint8_t*w,const uint16_t*x,unsigned row,size_t rb){
 float partial[4]{};
 for(unsigned part=0;part<4;++part){auto bounds=iq3::kopt2::bounds(2560,part,4);float lanes[8];
  for(unsigned p=0;p<8;++p){
   if constexpr(Tiled)lanes[p]=p49dvirtual::local_tree<4>(p104small::dense_chains<T,2560,4,true>(w,x,bounds.first,bounds.second,p,row,rb));
   else lanes[p]=p49dvirtual::local_tree<4>(p49dvirtual::dense_chains<T,2560,4>(w+size_t(row)*rb,x,bounds.first,bounds.second,p));
  }
  for(unsigned width=1;width<8;width*=2)for(unsigned p=0;p<8;p+=2*width)lanes[p]=lanes[p]+lanes[p+width];partial[part]=lanes[0];
 }
 return (partial[0]+partial[1])+(partial[2]+partial[3]);
}
template<bool Q6,bool Router>void benchmark_small(sycl::queue&q){
 constexpr unsigned n=1793;constexpr size_t scrub_words=size_t(128)*1024*1024;
 const char*name=Q6?"target-shared-q6-tile16":"target-router-tile16";
 constexpr unsigned rows[4]={512,640,640,1};constexpr size_t rb[4]={10240,3380,3380,10240};
 Buffers b{q,{}};auto*x=b.alloc<uint16_t>(2560);auto*out=b.alloc<uint16_t>(n+16);auto*f=b.alloc<float>(n);auto*scrub=b.alloc<uint32_t>(scrub_words);
 std::array<void*,12> pp{},tp{};p49dvirtual::SmallKernel<4>prod;p104small::SmallKernel<4,Q6,Router>tile;
 uint32_t seed=104;auto next=[&]{seed=seed*1664525u+1013904223u;return seed;};unsigned off=0;
 for(unsigned j=0;j<4;++j){guard();std::vector<uint8_t>raw(rows[j]*rb[j]);
  if(j==0||j==3){for(size_t k=0;k<raw.size()/4;++k){float v=float(int(next()%63)-31)/32.f;std::memcpy(raw.data()+4*k,&v,4);}}
  else{for(auto&v:raw)v=next()>>24;for(unsigned r=0;r<rows[j];++r)for(unsigned k=0;k<160;++k){float v=float(1+next()%63)/128.f;std::memcpy(raw.data()+r*rb[j]+2560+4*k,&v,4);}}
  auto changed=(Q6&&(j==1||j==2))?p104::small_q6(raw.data(),rows[j]):(Router&&j==0)?p104::small_router(raw.data(),rows[j]):raw;
  auto*w=b.alloc<uint8_t>(raw.size());auto*t=b.alloc<uint8_t>(changed.size());q.memcpy(w,raw.data(),raw.size()).wait_and_throw();q.memcpy(t,changed.data(),changed.size()).wait_and_throw();
  pp[j*3]=w;tp[j*3]=t;pp[j*3+1]=tp[j*3+1]=x;pp[j*3+2]=tp[j*3+2]=out+off;
  prod.shapes[j].rows=tile.shapes[j].rows=rows[j];prod.shapes[j].rb=tile.shapes[j].rb=rb[j];off+=rows[j];
 }
 auto launch=[&](bool tiled){return tiled?tile.submit(q,tp,{}):prod.submit(q,pp,{});};
 auto cold=[&]{q.parallel_for(sycl::range<1>(scrub_words),[=](sycl::id<1>id){scrub[id]=uint32_t(id[0]);}).wait_and_throw();};
 std::vector<uint16_t>hx(2560),ey(n+16),ay(n+16);std::vector<float>ef(n),af(n);
 for(unsigned ri=0;ri<8;++ri){guard();for(auto&v:hx)v=iq3::bf16_bits(float(int(next()%63)-31)/32.f);q.memcpy(x,hx.data(),hx.size()*2).wait_and_throw();
  for(unsigned arm=0;arm<2;++arm){q.memset(out,0x5a,(n+16)*2).wait_and_throw();unsigned offset=0;
   for(unsigned j=0;j<4;++j){auto*w=(const uint8_t*)(arm?tp:pp)[3*j];auto*dst=f+offset;auto width=rb[j];auto nr=rows[j];bool tiled=arm&&((Q6&&(j==1||j==2))||(Router&&j==0));
    q.parallel_for(sycl::range<1>(nr),[=](sycl::id<1>id){unsigned r=id[0];
     if(j==0||j==3)dst[r]=tiled?small_raw<iq3::Type::F32,true>(w,x,r,width):small_raw<iq3::Type::F32,false>(w,x,r,width);
     else dst[r]=tiled?small_raw<iq3::Type::Q6_K,true>(w,x,r,width):small_raw<iq3::Type::Q6_K,false>(w,x,r,width);
    }).wait_and_throw();offset+=nr;
   }
   launch(arm).wait_and_throw();q.memcpy(arm?af.data():ef.data(),f,n*4).wait_and_throw();q.memcpy(arm?ay.data():ey.data(),out,(n+16)*2).wait_and_throw();
  }
  if(std::memcmp(ef.data(),af.data(),n*4)||ey!=ay)throw std::runtime_error(std::string(name)+" tuple FP32/BF16 mismatch");
  for(unsigned i=n;i<n+16;++i)if(ay[i]!=0x5a5a)throw std::runtime_error("small tuple output guard");
  for(unsigned i=0;i<n;++i)if(iq3::bf16_bits(af[i])!=ay[i])throw std::runtime_error("small tuple FP32 does not match actual kernel output");
  auto shape=[&]{std::cout<<",\"rows\":1793,\"columns\":2560,\"count\":1,\"experts\":1";};
  std::cout<<"{\"kind\":\"correctness\",\"view\":\""<<name<<"\",\"route\":"<<ri<<",\"fp32_exact\":true,\"bf16_exact\":true,\"status_exact\":true";shape();std::cout<<"}\n";
  for(unsigned rep=0;rep<40;++rep)for(unsigned pos=0;pos<2;++pos){guard();bool arm=bool(pos^(rep&1));cold();auto e=launch(arm);e.wait_and_throw();auto ns=e.template get_profiling_info<sycl::info::event_profiling::command_end>()-e.template get_profiling_info<sycl::info::event_profiling::command_start>();
   std::cout<<"{\"kind\":\"sample\",\"pair\":\""<<name<<"\",\"view\":\""<<(arm?name:"production")<<"\",\"route\":"<<ri<<",\"repeat\":"<<rep<<",\"position\":"<<pos<<",\"event_ns\":"<<ns;shape();std::cout<<",\"wg\":128,\"sg\":32,\"scrub_bytes\":536870912,\"diagnostic_only\":true}\n";}
  std::cout<<std::flush;
 }
 q.wait_and_throw();guard();
}
