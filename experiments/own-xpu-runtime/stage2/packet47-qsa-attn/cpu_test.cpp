#define OWN_RT_HOST_ONLY
#include "qsa_reference.hpp"
#include <fstream>
#include <iostream>
#include <iomanip>
#include <unistd.h>

namespace {
unsigned long checks=0;
void check(bool condition,const char* message){++checks;if(!condition)throw std::runtime_error(message);}
// Recursive specification independently evaluates the complete dyadic tree.
// This shares neither the vector reduction nor partial construction of oracle.
float node(const float* x,int length,int first,int width){
 if(first>=length)return 0.f;
 if(width==1)return x[first];
 return node(x,length,first,width/2)+node(x,length,first+width/2,width/2);
}
float tree(const float* x,int n){int width=1;while(width<n)width*=2;return node(x,n,0,width);}
float dot(ng::Args a,int r,int h,int id){float leaf[256];
 for(int i=0;i<256;++i)leaf[i]=a.b(2,(id*2+h/12)*256+i)*a.b(0,(r*24+h)*256+i);
 return tree(leaf,256)/16.f;
}
// CPU emulation of independent work-group scheduling. Slots are visited in
// reverse order to catch accidental dependence on submission order. This is
// NOT a substitute for executing and comparing the SYCL device implementation.
void emulate(ng::Shape s,ng::Args a,bool split,std::vector<float>& pre){
 const int S=s.budget+3;
 for(int r=s.tokens-1;r>=0;--r){int n=0;while(n<S&&a.i(4)[r*S+n]!=-1)++n;if(!n)continue;int chunks=(n+31)/32;
  for(int h=23;h>=0;--h){std::vector<float> scores(n),p(n);
   for(int j=n-1;j>=0;--j)scores[j]=dot(a,r,h,a.i(4)[r*S+j]);
   if(!split){float maximum=-INFINITY;for(int j=0;j<n;++j)maximum=std::max(maximum,scores[j]);
    for(int j=0;j<n;++j)p[j]=detmath::exp(scores[j]-maximum);float den=tree(p.data(),n);
    for(float& x:p)x=x/den;
    for(int d=255;d>=0;--d){std::vector<float> products(n);for(int j=0;j<n;++j)products[j]=p[j]*a.b(3,(a.i(4)[r*S+j]*2+h/12)*256+d);
     int at=(r*24+h)*256+d;pre[at]=p47ref::blocked(products);a.put(5,at,ng::Args::bf(pre[at])*ng::sigmoid(a.b(1,at)));
    }
   }else{std::vector<float> partial(chunks*258),factors(chunks),leaves(chunks);
    for(int b=chunks-1;b>=0;--b){int valid=std::min(32,n-b*32);float weight[32]{},maximum=-INFINITY;
     for(int j=0;j<valid;++j)maximum=std::max(maximum,scores[b*32+j]);
     for(int j=0;j<valid;++j)weight[j]=detmath::exp(scores[b*32+j]-maximum);
     partial[b*258]=maximum;partial[b*258+1]=tree(weight,32);
     for(int d=255;d>=0;--d){float terms[32]{};for(int j=0;j<valid;++j)terms[j]=weight[j]*a.b(3,(a.i(4)[r*S+b*32+j]*2+h/12)*256+d);
      partial[b*258+2+d]=tree(terms,32);
     }
    }
    float maximum=-INFINITY;for(int b=0;b<chunks;++b)maximum=std::max(maximum,partial[b*258]);
    for(int b=0;b<chunks;++b){factors[b]=detmath::exp(partial[b*258]-maximum);leaves[b]=partial[b*258+1]*factors[b];}
    float den=tree(leaves.data(),chunks);
    for(int d=255;d>=0;--d){for(int b=0;b<chunks;++b)leaves[b]=partial[b*258+2+d]*factors[b];
     int at=(r*24+h)*256+d;pre[at]=tree(leaves.data(),chunks)/den;a.put(5,at,ng::Args::bf(pre[at])*ng::sigmoid(a.b(1,at)));
    }
   }
  }
 }
}
uint32_t ordered(float x){auto u=std::bit_cast<uint32_t>(x);return (u&0x80000000u)?~u:u|0x80000000u;}
uint64_t ulp(float a,float b){uint32_t x=ordered(a),y=ordered(b);return x>y?uint64_t(x)-y:uint64_t(y)-x;}
void write(std::ofstream& out,const auto& v){out.write(reinterpret_cast<const char*>(v.data()),v.size()*sizeof(v[0]));}
}
int main(int argc,char** argv){try{
 if(argc!=2)throw std::invalid_argument("usage: cpu-test RAW_OUTPUT");
 std::ofstream raw(argv[1],std::ios::binary|std::ios::trunc);if(!raw)throw std::runtime_error("raw output open");
 // Exhaustive 1..2051 tails, cancellation and signed zeros: this proof catches
 // arithmetic changes that random full-size fixtures often miss after BF16.
 for(int n=1;n<=2051;++n){std::vector<float> leaves(n);for(int j=0;j<n;++j)leaves[j]=j%11==0?-0.f:float((j*17)%37-18)*std::ldexp(1.f,j%19-9);
  check(std::bit_cast<uint32_t>(p47ref::adjacent(leaves))==std::bit_cast<uint32_t>(p47ref::blocked(leaves)),"historical blocked tail");
  check(std::bit_cast<uint32_t>(p47ref::adjacent(leaves))==std::bit_cast<uint32_t>(tree(leaves.data(),n)),"independent tree");
 }
 struct Case{int context,rows,pattern;uint32_t seed;};std::vector<Case> cases;
 for(int c:{1024,2048,4096,8192,32768})for(int m:{1,2})for(uint32_t seed:{47u,4701u})cases.push_back({c,m,0,seed});
 for(int c:{1,2,3,31,32,33,63,64,65,2051,4095,32767})cases.push_back({c,1,0,4747});
 for(int pattern:{1,2})for(int m:{1,2})cases.push_back({65,m,pattern,4799});
 uint64_t max_ulp=0,max_pre_ulp=0;double max_abs=0,max_pre_abs=0;size_t changed=0,total=0;int ordinal=0;
 for(auto c:cases){p47ref::Fixture source(c.context,c.rows,c.seed,c.pattern),old=source,current=source,incumbent=source,order=source,simulation=source;
  auto shape=source.shape;size_t count=c.rows*6144;std::vector<float> opre(count),npre(count),samepre(count),spre(count);
  p47ref::cpu_old(shape,old.args(),opre.data());
  for(int op:{ng::attention_score,ng::attention_softmax,ng::attention_value}){auto s=shape;s.op=op;ng::cpu(s,incumbent.args());}
  check(old.data[5]==incumbent.data[5],"independent historical oracle != ng::cpu");
  check(old.data[6]==incumbent.data[6]&&old.data[7]==incumbent.data[7],"historical score/probability mismatch");
  emulate(shape,order.args(),false,samepre);check(old.data[5]==order.data[5],"order-preserving output");check(!std::memcmp(opre.data(),samepre.data(),count*4),"order-preserving pre-gate bytes");
  p47ref::cpu_split(shape,current.args(),npre.data());emulate(shape,simulation.args(),true,spre);
  check(current.data[5]==simulation.data[5],"split oracle != independently scheduled simulation");check(!std::memcmp(npre.data(),spre.data(),count*4),"split pre-gate bytes");
  uint64_t row_ulp=0,row_pre_ulp=0;double row_abs=0,row_pre_abs=0;size_t row_changed=0;
  for(size_t i=0;i<count;++i){float x=old.args().b(5,i),y=current.args().b(5,i);check(std::isfinite(x)&&std::isfinite(y)&&std::isfinite(npre[i]),"finite outputs");
   row_changed+=std::bit_cast<uint32_t>(x)!=std::bit_cast<uint32_t>(y);row_ulp=std::max(row_ulp,ulp(x,y));row_abs=std::max(row_abs,double(std::abs(x-y)));
   row_pre_ulp=std::max(row_pre_ulp,ulp(opre[i],npre[i]));row_pre_abs=std::max(row_pre_abs,double(std::abs(opre[i]-npre[i])));
  }
  max_ulp=std::max(max_ulp,row_ulp);max_pre_ulp=std::max(max_pre_ulp,row_pre_ulp);max_abs=std::max(max_abs,row_abs);max_pre_abs=std::max(max_pre_abs,row_pre_abs);changed+=row_changed;total+=count;
  write(raw,old.data[5]);write(raw,current.data[5]);write(raw,npre);
  std::cout<<std::setprecision(10)<<"{\"case\":"<<ordinal++<<",\"context\":"<<c.context<<",\"rows\":"<<c.rows<<",\"seed\":"<<c.seed<<",\"pattern\":"<<c.pattern<<",\"selected_first\":"<<p47ref::count(shape,source.args(),0)<<",\"selected_last\":"<<p47ref::count(shape,source.args(),c.rows-1)<<",\"passed\":true,\"old_new_changed\":"<<row_changed<<",\"old_new_float32_ulp\":"<<row_ulp<<",\"old_new_max_abs\":"<<row_abs<<",\"pre_gate_max_ulp\":"<<row_pre_ulp<<",\"pre_gate_max_abs\":"<<row_pre_abs<<"}\n";
 }
 raw.close();if(!raw)throw std::runtime_error("raw output write");
 std::cout<<std::setprecision(10)<<"{\"summary\":true,\"passed\":true,\"device_executed\":false,\"pid\":"<<getpid()<<",\"cases\":"<<cases.size()<<",\"checks\":"<<checks<<",\"output_values\":"<<total<<",\"old_new_changed\":"<<changed<<",\"old_new_float32_ulp\":"<<max_ulp<<",\"old_new_max_abs\":"<<max_abs<<",\"pre_gate_max_ulp\":"<<max_pre_ulp<<",\"pre_gate_max_abs\":"<<max_pre_abs<<",\"logits_measured\":false}\n";
 return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
