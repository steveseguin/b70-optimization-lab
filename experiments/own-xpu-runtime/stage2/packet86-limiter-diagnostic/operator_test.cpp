#include "p86_expert.hpp"
#include "p86_hc.hpp"
#include <fstream>
#include <iostream>
void check(bool x,const char*s){if(!x)throw std::runtime_error(s);}
template<iq3::Type T,unsigned K,unsigned V>void expert(){
 auto l=p49bgemv::layout(T,K);std::vector<uint8_t>w(l.row_bytes);std::vector<uint16_t>x(K);
 for(unsigned i=0;i<w.size();++i)w[i]=(i*13+7)%251;
 for(unsigned i=0;i<K;++i)x[i]=iq3::bf16_bits(float(int(i%13)-6)/16.f);
 for(unsigned i=0;i<K/(T==iq3::Type::IQ2_S?256:32);++i){w[l.halves+2*i]=0;w[l.halves+2*i+1]=0x28;}
 bool changed_raw=false,changed_grid=false;
 for(unsigned lane=0;lane<32/V;++lane){
  auto expected=p65::wide_chains<T,K,V>(w.data(),x.data(),lane);
  auto keep=p86exp::diagnostic_chains<T,K,V,4>(w.data(),x.data(),lane);
  auto raw=p86exp::diagnostic_chains<T,K,V,1>(w.data(),x.data(),lane);
  auto grid=p86exp::diagnostic_chains<T,K,V,2>(w.data(),x.data(),lane);
  for(unsigned j=0;j<V;++j){check(std::bit_cast<uint32_t>(expected[j])==std::bit_cast<uint32_t>(keep[j]),"loadkeep changed production chain bits");changed_raw|=raw[j]!=expected[j];changed_grid|=grid[j]!=expected[j];}
 }
 check(changed_raw,"raw byte view unchanged");
 check(changed_grid==(T==iq3::Type::IQ2_S),"grid scope must be IQ2 only");
 // Same-expert address override must retain invalid-route status checks.
 unsigned rows=1,count=2;std::vector<uint8_t>bank(2*w.size());std::copy(w.begin(),w.end(),bank.begin());std::copy(w.begin(),w.end(),bank.begin()+w.size());
 std::vector<uint16_t>input(K*2,iq3::bf16_bits(.125f)),y(2),peer(2);uint32_t status[2]{},ps[2]{},error=0,active=1;
 iq3::Route routes[2]={{0,0,1},{2,0,1}};std::array<void*,19> args{};args[0]=bank.data();args[1]=bank.data();args[2]=input.data();args[3]=y.data();args[4]=peer.data();args[5]=routes;args[6]=status;args[7]=ps;args[16]=&error;args[17]=&active;
 p86exp::Kernel<T,K,64,false,true,0,3>op;op.rows=rows;op.count=count;op.experts=2;op.run(args);check(error==1&&status[1]==1,"same-expert diagnostic bypassed route safety");
}
int main(){try{
 expert<iq3::Type::IQ2_S,2560,8>();expert<iq3::Type::IQ4_NL,640,16>();
 std::vector<uint8_t>w(iq3::expanded::row_bytes(iq3::Type::Q8_0,320));std::vector<uint16_t>x(320);
 for(unsigned i=0;i<320;++i){w[i]=uint8_t(i*19+3);x[i]=iq3::bf16_bits(float(int(i%11)-5)/16.f);}
 for(unsigned i=0;i<10;++i){float scale=.03125f*(i+1);std::memcpy(w.data()+320+4*i,&scale,4);}
 bool raw_changed=false,scale_changed=false;
 for(unsigned lane=0;lane<32;++lane){float a=p49c::dense_lane<iq3::Type::Q8_0,320>(w.data(),x.data(),0,320,lane),b=p86hc::lane_value<3>(w.data(),x.data(),lane);
 check(std::bit_cast<uint32_t>(a)==std::bit_cast<uint32_t>(b),"HC loadkeep differs");raw_changed|=a!=p86hc::lane_value<1>(w.data(),x.data(),lane);scale_changed|=a!=p86hc::lane_value<2>(w.data(),x.data(),lane);}
 check(raw_changed&&scale_changed,"HC ablations unchanged");
 std::cout<<"{\"passed\":true,\"diagnostic_nonexact\":true,\"device_executed\":false,\"production_and_loadkeep_exact\":true,\"diagnostic_mismatches_observed\":true,\"invalid_routes_rejected\":true}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
