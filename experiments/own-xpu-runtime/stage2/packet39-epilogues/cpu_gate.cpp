#include "fused.hpp"
#include "../packet29-merged/core_v2.hpp"
#include <iostream>
#include <cstring>
#include <vector>
#include <cstdlib>
#include <map>
using namespace p39;
static unsigned comparisons=0,fixtures=0,diagnostic_comparisons=0,diagnostic_mismatches=0;
static bool diagnostic=false;
static unsigned guards=0;
static uint64_t finite_hash=1469598103934665603ULL,diagnostic_hash=1469598103934665603ULL;
void digest(const void* p,size_t n){auto bytes=static_cast<const unsigned char*>(p);auto& hash=diagnostic?diagnostic_hash:finite_hash;for(size_t i=0;i<n;++i){hash^=bytes[i];hash*=1099511628211ULL;}}
static std::string current_class;
static std::map<std::string,std::array<unsigned,3>> classes;
void check_equal(const auto&a,const auto&b,const char* field){if(diagnostic){++diagnostic_comparisons;++classes[current_class][1];if(a!=b){++diagnostic_mismatches;++classes[current_class][2];}return;}++comparisons;++classes[current_class][0];if(a!=b)throw std::runtime_error(std::string("bytes differ: ")+field);}
struct Fixture {
 std::vector<uint8_t>w,peer;std::vector<float>conv_weights,scratch;std::vector<uint16_t>x,y,py,out,other,mixture,shared_gate,inject,streams,history;
 std::vector<iq3::Route> routes;std::vector<uint32_t>status,ps;float one=1.f;uint32_t error=0,active=1,position=0;unsigned rows,count,rb,experts;
 Bound bound(){Bound b;b.one=&one;b.scratch=scratch.data();b.conv_weights=conv_weights.data();b.history=history.data();b.w=w.data();b.peer=peer.data();b.x=x.data();b.y=y.data();b.py=py.data();b.out=out.data();b.other=other.data();b.mixture=mixture.data();b.shared_gate=shared_gate.data();b.inject=inject.data();b.streams=streams.data();b.routes=routes.data();b.status=status.data();b.peer_status=ps.data();b.error=&error;b.active=&active;b.position=&position;b.rb=rb;b.rows=rows;b.count=count;b.experts=experts;return b;}
};
void original_tail(Fixture&f,Kind kind){
 if(!f.active||f.error)return;
 if(kind==Kind::expert_act||kind==Kind::expert_checks||kind==Kind::down_status){for(auto s:f.status)if(s){f.error=1;return;}if(kind==Kind::expert_act||kind==Kind::expert_checks)for(auto s:f.ps)if(s){f.error=1;return;}}
 if(kind==Kind::down_status||kind==Kind::expert_checks)return;
 if(kind!=Kind::attention_combine&&(std::bit_cast<int32_t>(f.position)<0||f.position>=128)){f.error=1;return;}
 std::vector<float>arena(100000);integrated::Core c;c.pool={arena.data(),0,arena.size(),0};c.s[1]=int(f.rows);
 auto input=[&](unsigned slot,const std::vector<uint16_t>&v){c.inputs[slot]=c.make(v.size());for(size_t i=0;i<v.size();++i)c.inputs[slot][i]=widen(v[i]);};
 auto extract=[&](std::vector<uint16_t>&v){for(size_t i=0;i<v.size();++i)v[i]=iq3::bf16_bits(c.outputs[0][i]);};
 if(kind==Kind::expert_act||kind==Kind::shared_act||kind==Kind::silu_div4){
  ng::Shape shape{ng::activation};shape.width=int(f.rows*f.count);shape.extra=kind!=Kind::silu_div4;
  ng::Args args;args.p[0]=(kind==Kind::shared_act?f.other:f.y).data();args.p[1]=(kind==Kind::expert_act?f.py:f.y).data();args.p[2]=f.out.data();args.p[15]=&f.error;uint32_t position=0;args.p[17]=&position;args.p[18]=&f.active;ng::cpu(shape,args);
 }
 if(kind==Kind::gdn_conv){ng::Shape shape{ng::conv};shape.width=int(f.rows);shape.extra=1;shape.flags=8;
 ng::Args args;args.p[0]=f.y.data();args.p[1]=f.history.data();args.p[2]=f.conv_weights.data();args.p[3]=f.out.data();args.p[4]=f.history.data();args.p[15]=&f.error;args.p[17]=&f.position;args.p[18]=&f.active;ng::cpu(shape,args);}
 if(kind==Kind::shared_combine){c.op=integrated::Op::moe_combine;c.s[0]=1;input(0,f.mixture);c.inputs[1]=c.make(1,1.f);input(2,f.y);input(3,f.shared_gate);c.run();extract(f.out);}
 if(kind==Kind::attention_combine||kind==Kind::shared_combine){c.op=integrated::Op::hc_combine;input(0,f.streams);input(1,kind==Kind::shared_combine?f.out:f.y);input(2,f.inject);c.run();extract(f.streams);}
 if(c.failed||c.pool.failed)throw std::runtime_error("reference pool/error");
}
template<Type T,unsigned K,Kind E,unsigned Split=1>void run(unsigned rows,unsigned mode){
 current_class=std::to_string(int(E))+":"+std::to_string(int(T))+":"+std::to_string(K)+":"+std::to_string(Split);
 constexpr bool routed=E==Kind::expert_act||E==Kind::expert_checks||E==Kind::down_status;
 Fixture f;f.rows=rows;f.count=routed?10:1;f.experts=routed?2:1;
 if constexpr(T==Type::Q6_K||T==Type::Q8_0)f.rb=K+4*(K/(T==Type::Q6_K?16:32));else f.rb=K/iq3::layout(T).elements*iq3::layout(T).bytes;
 f.w.resize(f.experts*rows*f.rb);f.peer.resize(f.w.size());
 uint32_t state=0x713246ab;auto byte=[&](){state=1664525*state+1013904223;return uint8_t(state>>24);};for(auto&v:f.w)v=byte();
 for(unsigned row=0;row<f.experts*rows;++row){auto p=f.w.data()+row*f.rb;
  if constexpr(T==Type::Q6_K||T==Type::Q8_0){for(unsigned k=K;k<f.rb;k+=4){float scale=0.001f;std::memcpy(p+k,&scale,4);}}
  else if constexpr(T==Type::F32){for(unsigned k=0;k<K;++k){float value=(int(byte())-128)*.001f;std::memcpy(p+4*k,&value,4);}}
  else {for(unsigned k=0;k<f.rb;k+=iq3::layout(T).bytes){p[k]=0x00;p[k+1]=0x20;}}
 }
 f.peer=f.w;for(unsigned r=0;r<f.experts*rows;++r)f.peer[r*f.rb+2]^=0x71;
 auto fill=[&](std::vector<uint16_t>&v,unsigned n){v.resize(n);for(auto&a:v)a=iq3::bf16_bits((int(byte())-128)*.01f);};
 fill(f.x,K*(E==Kind::down_status?f.count:1));fill(f.other,rows*f.count);fill(f.mixture,rows);fill(f.shared_gate,1);fill(f.inject,4);fill(f.streams,rows*4);
 fill(f.history,rows*3);for(unsigned i=0;i<rows*4;++i)f.conv_weights.push_back((int(byte())-128)*.01f);
 f.scratch.resize(rows*f.count*8);
 f.y.assign(rows*f.count,0x5577);f.py=f.y;f.out=f.y;f.status.assign(f.count,0xdead);f.ps=f.status;
 for(unsigned i=0;i<f.count;++i)f.routes.push_back({i%f.experts,0,rows});
 if(mode==1&&routed)f.routes[7].expert_id=99;
 if(mode==2)f.error=7;
 if(mode==3)f.active=0;
 if(mode==4){f.x[0]=0x7fc1;f.other[0]=0xffc2;f.shared_gate[0]=0x7f80;}
 if(mode==5){f.x[0]=0x7f80;f.x[1]=0xff80;}
 if(mode==6&&routed)f.routes[8].row_count=rows-1;
 if(mode==8)f.position=UINT32_MAX;
 if(mode==9)f.position=128;
 if(mode==7&&routed){f.routes[0].row_begin=UINT32_MAX;f.error=7;}
 diagnostic=mode==4||mode==5;
 if(diagnostic)std::cerr<<"diagnostic T="<<int(T)<<" K="<<K<<" E="<<int(E)<<" Split="<<Split<<" rows="<<rows<<" mode="<<mode<<"\n";
 auto original=f.bound();validate<T,K,E,Split>(original);
 for(unsigned bad=0;bad<5;++bad){auto bound=original;if(bad==0)bound.y=nullptr;if(bad==1)bound.y=const_cast<uint16_t*>(bound.x);if(bad==2)bound.rb++;if(bad==3)bound.capacity=0;if(bad==4)bound.position=nullptr;bool rejected=false;try{validate<T,K,E,Split>(bound);}catch(const std::invalid_argument&){rejected=true;}if(!rejected)throw std::runtime_error("guard admitted invalid binding");++guards;}
 Fixture reference=f,candidate=f;
 host_gemv<T,K,E,false,Split>(reference.bound());original_tail(reference,E);
 host_gemv<T,K,E,true,Split>(candidate.bound());
 if(reference.out!=candidate.out)for(unsigned i=0;i<reference.out.size();++i)if(reference.out[i]!=candidate.out[i]){std::cerr<<"i="<<i<<" ref="<<std::hex<<reference.out[i]<<" got="<<candidate.out[i]<<" gate="<<reference.y[i]<<" up="<<reference.py[i]<<std::dec<<"\n";break;}
 check_equal(reference.history,candidate.history,"history");check_equal(reference.y,candidate.y,"y");check_equal(reference.py,candidate.py,"peer");check_equal(reference.out,candidate.out,"epilogue");check_equal(reference.streams,candidate.streams,"streams");check_equal(reference.status,candidate.status,"status");check_equal(reference.ps,candidate.ps,"peer status");check_equal(reference.error,candidate.error,"sticky");check_equal(reference.active,candidate.active,"active");
 for(auto* v:{&candidate.y,&candidate.py,&candidate.out,&candidate.streams,&candidate.history})digest(v->data(),v->size()*2);for(auto* v:{&candidate.status,&candidate.ps})digest(v->data(),v->size()*4);digest(&candidate.error,4);digest(&candidate.active,4);++fixtures;
}
int main(){try{
 for(unsigned rows:{1u,3u,17u})for(unsigned mode=0;mode<10;++mode){
 run<Type::IQ2_S,2560,Kind::expert_act>(rows,mode);run<Type::IQ3_S,2560,Kind::expert_act>(rows,mode);
 run<Type::IQ4_NL,640,Kind::down_status>(rows,mode);
 run<Type::IQ2_S,2560,Kind::expert_checks>(rows,mode);run<Type::IQ3_S,2560,Kind::expert_checks>(rows,mode);
 run<Type::Q8_0,10240,Kind::silu_div4,4>(rows,mode);
 run<Type::Q6_K,2560,Kind::shared_act,4>(rows,mode);run<Type::Q8_0,2560,Kind::shared_act>(rows,mode);
 run<Type::Q6_K,2560,Kind::gdn_conv>(rows,mode);run<Type::Q8_0,2560,Kind::gdn_conv>(rows,mode);
 run<Type::Q6_K,6144,Kind::attention_combine,4>(rows,mode);run<Type::Q8_0,640,Kind::shared_combine>(rows,mode);
 }
 diagnostic=false;current_class="bf16-rounding";
 // Rounding ties, signed zero, infinities and representative NaN payloads.
 for(unsigned bits:{0x3f808000u,0x3f818000u,0x80000000u,0x00000000u,0x7f800000u,0xff800000u,0x7fa00001u,0xffc10000u}){float f=iq3::bits_float(bits);check_equal(iq3::bf16_bits(f),ng::Args::bits(f),"BF16 boundary");}
 std::cout<<"{\"finite_and_control_passed\":true,\"passed\":"<<(diagnostic_mismatches?"false":"true")<<",\"fixtures\":"<<fixtures<<",\"observable_comparisons\":"<<comparisons<<",\"nonfinite_diagnostic_comparisons\":"<<diagnostic_comparisons<<",\"nonfinite_diagnostic_mismatches\":"<<diagnostic_mismatches<<",\"finite_output_fnv64\":\""<<std::hex<<finite_hash<<"\",\"nonfinite_output_fnv64\":\""<<diagnostic_hash<<std::dec<<"\",\"guard_rejections\":"<<guards<<",\"nonfinite_qualified\":false,\"nan_tolerance\":false,\"device_ran\":false,\"classes\":{";
 bool first=true;for(auto&[name,counts]:classes){if(!first)std::cout<<',';first=false;std::cout<<'"'<<name<<"\":{\"finite_checks\":"<<counts[0]<<",\"nonfinite_checks\":"<<counts[1]<<",\"nonfinite_mismatches\":"<<counts[2]<<'}';}std::cout<<"}}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
