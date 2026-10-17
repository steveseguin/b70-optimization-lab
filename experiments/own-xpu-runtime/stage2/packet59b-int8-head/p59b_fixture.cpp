#include "p59b_head.hpp"
#include "p33_submit.hpp"
#include "round2_submit.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
using namespace ownrt;using namespace integrated;
#ifdef OWN_RT_HOST_ONLY
struct Cpu final:Backend {
 std::string identity()const override{return "CPU packet49d actual submitters";}
 void* allocate(size_t n,Memory)override{return ::operator new(n,std::align_val_t(64));}
 void release(void*p,Memory)override{::operator delete(p,std::align_val_t(64));}
 Event copy(void*a,const void*b,size_t n,std::span<const Event>)override{std::memcpy(a,b,n);return next_handle();}
 Event marker(std::span<const Event>)override{return next_handle();}
 Event compute(const Operation&op,std::span<void*const>p,std::span<const Event>)override{dynamic_cast<const HostOperation&>(op).run(p);return next_handle();}
 bool complete(Event)override{return true;}bool wait(Event,Deadline)override{return true;}
 EventTiming timing(Event)override{return {};}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};

int main(int argc,char**argv){try {
 if(argc!=2)throw std::invalid_argument("output directory required");std::filesystem::path out=argv[1];std::filesystem::create_directories(out);
 Device d(std::make_unique<Cpu>());unsigned serial=0;
 auto alloc=[&](size_t bytes){return d.arena.allocate("p59b-fixture-"+std::to_string(serial++),bytes,Memory::device,Category::scratch,Lifetime::transaction);};
 auto write=[&](const char* name,const void* ptr,size_t bytes){std::ofstream f(out/name,std::ios::binary);f.write(static_cast<const char*>(ptr),bytes);if(!f)throw std::runtime_error("fixture output");};
 constexpr unsigned rows=257,k=2560;size_t stride=arithmetic::row_bytes(iq3::Type::Q6_K,k,6);
 std::vector<uint8_t> expanded(rows*stride);std::vector<int8_t> codes(rows*k);std::vector<float> scales(rows),values(k);std::vector<uint16_t>x(k),ref(rows);
 uint32_t seed=59;
 for(auto& b:expanded){seed=1664525u*seed+1013904223u;b=seed>>24;}
 for(unsigned r=0;r<rows;++r){for(unsigned g=0;g<k/16;++g){float s=float(int((r+g)%7)-3)/256.f;std::memcpy(expanded.data()+r*stride+k+4*g,&s,4);}
  for(unsigned j=0;j<k;++j)values[j]=iq3::expanded::value(iq3::Type::Q6_K,expanded.data()+r*stride,k,j);
  if(r==0)std::fill(values.begin(),values.end(),0.f);
  p59b::quantize(values.data(),k,codes.data()+r*k,scales[r]);
 }
 for(unsigned j=0;j<k;++j)x[j]=iq3::bf16_bits(float(int((j*17)%127)-63)/128.f);
 auto w=alloc(codes.size()),sc=alloc(scales.size()*4),xx=alloc(x.size()*2),yy=alloc(rows*2),target=alloc(expanded.size()),ty=alloc(rows*2),ws=alloc(rows*32);
 auto ptr=[&](Allocation a){return d.arena.row(a).pointer;};
 std::memcpy(ptr(w),codes.data(),codes.size());std::memcpy(ptr(sc),scales.data(),scales.size()*4);std::memcpy(ptr(xx),x.data(),x.size()*2);std::memcpy(ptr(target),expanded.data(),expanded.size());
 // Independently expressed fixed lane order, reduction and FP32 row rescale.
 for(unsigned r=0;r<rows;++r){float partial[32]{};for(unsigned j=0;j<k;++j){unsigned lane=(j%256)/8;partial[lane]=partial[lane]+float(codes[r*k+j])*iq3::bits_float(uint32_t(x[j])<<16);}
  for(unsigned step=1;step<32;step*=2)for(unsigned l=0;l<32;l+=2*step)partial[l]=partial[l]+partial[l+step];ref[r]=iq3::bf16_bits(partial[0]*scales[r]);}
 p59b::head(d,{w,sc,xx,yy,rows,k});
 if(std::memcmp(ref.data(),ptr(yy),rows*2))throw std::runtime_error("INT8 production/reference logits differ");
 write("expected.bin",ref.data(),rows*2);write("actual.bin",ptr(yy),rows*2);write("codes.bin",codes.data(),codes.size());write("scales.bin",scales.data(),scales.size()*4);
 p59b::head(d,{w,sc,xx,yy,rows,k});if(std::memcmp(ref.data(),ptr(yy),rows*2))throw std::runtime_error("INT8 repeat differs");
 Matrix m{};m.w=target;m.x=xx;m.y=ty;m.workspace=ws;m.type=iq3::Type::Q6_K;m.rows=m.span=rows;m.columns=k;
 p33::submit(d,{m},"p33.dense.segment",false,6);write("target.bin",ptr(ty),rows*2);
 // Actual unchanged argmax, including lower-index ties across WG boundaries.
 auto token=alloc(4),scratch=alloc(rows*4),error=alloc(4),position=alloc(4),active=alloc(4),rope=alloc(4);
 *static_cast<int*>(ptr(error))=0;*static_cast<int*>(ptr(position))=0;*static_cast<int*>(ptr(active))=1;
 Spec s{};s.op=Op::argmax;s.implementation=2;s.ni=s.no=1;s.sizes[0]=rows;s.sizes[1]=1;s.types[0]=flash::Scalar::bf16;s.types[1]=flash::Scalar::i32;
 std::array<Allocation,7> bindings{yy,token,scratch,error,position,active,rope};
 round2::submit_simple(d,s,bindings,{});int expected=0;for(unsigned r=1;r<rows;++r)if(iq3::bits_float(uint32_t(ref[r])<<16)>iq3::bits_float(uint32_t(ref[expected])<<16))expected=r;
 if(*static_cast<int*>(ptr(error))||*static_cast<int*>(ptr(token))!=expected)throw std::runtime_error("draft proposal differs");write("proposal.bin",ptr(token),4);
 std::memset(ptr(yy),0,rows*2);round2::submit_simple(d,s,bindings,{});if(*static_cast<int*>(ptr(token))!=0)throw std::runtime_error("argmax tie differs");
 // Quantizer edges: zero, exact +/-127, nearest-even half ties, nonfinite refusal.
 float edge[5]{127.f,-127.f,0.5f,1.5f,-1.5f},scale;int8_t q[5];p59b::quantize(edge,5,q,scale);
 if(scale!=1.f||q[0]!=127||q[1]!=-127||q[2]!=0||q[3]!=2||q[4]!=-2)throw std::runtime_error("quantizer edge differs");
 bool refused=false;edge[0]=std::numeric_limits<float>::infinity();try{p59b::quantize(edge,5,q,scale);}catch(const std::invalid_argument&){refused=true;}if(!refused)throw std::runtime_error("nonfinite accepted");
 auto done=d.shutdown(std::chrono::seconds(30));if(!done.safe_to_exit||done.exit_code)throw std::runtime_error("fixture teardown");
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"rows\":257,\"columns\":2560,\"proposal\":"<<expected<<"}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
#else
int main(){std::cerr<<"CPU-only gate; no device entry\n";return 1;}
#endif
