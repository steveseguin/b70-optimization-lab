#pragma once
#include "kernels.hpp"

// Packet24: independent work items, no work-group barrier or shared-local tree.
// The launch adapter orders stages. Guard provides atomic error(a)/fail(a).
namespace ng2 {
constexpr int tile = 32;
inline int ceildiv(int n,int d){return (n+d-1)/d;}
inline bool supported(ng::Shape s){
 return s.op==ng::norm||s.op==ng::combine_norm||s.op==ng::gated_norm||
        s.op==ng::gdn||s.op==ng::prepare||s.op==ng::pool||s.op==ng::select||s.op==ng::attention_score||
        s.op==ng::attention_softmax||s.op==ng::attention_value;
}
inline int width(ng::Shape s){return s.op==ng::gated_norm?128:s.width;}
inline int rows(ng::Shape s){return s.tokens*(s.op==ng::gated_norm?48:s.heads);}
inline int slots(ng::Shape s){return s.budget+3;}
inline int chunks(ng::Shape s){return ceildiv(std::min(s.capacity,slots(s)),tile);}
inline int stages(ng::Shape s){return s.op==ng::attention_score?1:s.op==ng::attention_softmax?3:2;}
inline size_t scratch_floats(ng::Shape s){
 if(s.op==ng::gdn)return size_t(s.tokens)*(4096+96);
 if(s.op==ng::prepare)return size_t(s.tokens)*30*8;
 if(s.op==ng::pool)return size_t(ceildiv(s.capacity,4))*4;
 if(s.op==ng::select)return size_t(s.tokens)*ceildiv(s.capacity,4);
 if(s.op==ng::attention_score)return 1;
 if(s.op==ng::attention_softmax)return size_t(s.tokens)*24*chunks(s)*2;
 if(s.op==ng::attention_value)return size_t(s.tokens)*6144*chunks(s);
 return size_t(rows(s))*ceildiv(width(s),tile);
}
inline size_t work_items(ng::Shape s,int stage){
 if(s.op==ng::gdn)return stage==0?size_t(s.tokens)*112:size_t(6144);
 if(s.op==ng::prepare)return size_t(s.tokens)*30*(stage==0?8:64);
 if(s.op==ng::pool)return stage==0?size_t(ceildiv(s.capacity,4))*4+size_t(s.tokens)*640:size_t(ceildiv(s.capacity,4))*32;
 if(s.op==ng::select)return size_t(s.tokens)*(stage==0?std::max(ceildiv(s.capacity,4),slots(s)):ceildiv(s.capacity,4));
 if(s.op==ng::attention_score)return size_t(s.tokens)*24*std::min(s.capacity,slots(s));
 if(s.op==ng::attention_softmax)return size_t(s.tokens)*24*(stage<2?chunks(s):ceildiv(std::min(s.capacity,slots(s)),4));
 if(s.op==ng::attention_value)return size_t(s.tokens)*6144*(stage==0?chunks(s):1);
 return size_t(rows(s))*(stage==0?ceildiv(width(s),tile):ceildiv(width(s),4));
}

// Evaluate a complete aligned 32-leaf subtree. The partial final subtree still
// performs every original +0 tail node up to its cut depth. For a whole tree
// smaller than 32, stop at its root: no fictitious additions above that root.
template<class Get> inline float subtree(int n,int chunk,Get get){
 float v[tile];int begin=chunk*tile;
 for(int k=0;k<tile;++k)v[k]=begin+k<n?get(begin+k):0.f;
 for(int stride=1;stride<std::min(n,tile);stride*=2)
  for(int k=0;k<tile;k+=2*stride)
   if(begin+k<n)v[k]=v[k]+(begin+k+stride<n?v[k+stride]:0.f);
 return v[0];
}
// Upper nodes preserve order and odd-tail +0 at every level. Maximum 128
// partials covers all registered widths, and 65 covers attention's 2051 slots.
inline float upper(const float* p,int n){
 float v[128];for(int k=0;k<n;++k)v[k]=p[k];
 for(int stride=1;stride<n;stride*=2)
  for(int k=0;k<n;k+=2*stride)v[k]=v[k]+(k+stride<n?v[k+stride]:0.f);
 return v[0];
}
template<int N,class Get> inline float private_tree(Get get){
 float v[N];for(int k=0;k<N;++k)v[k]=get(k);
 for(int stride=1;stride<N;stride*=2)
  for(int k=0;k<N;k+=2*stride)v[k]=v[k]+v[k+stride];
 return v[0];
}
template<class Get> inline float dot128(Get get){
 return private_tree<32>([&](int lane){float x=0.f;for(int k=0;k<4;++k)x=x+get(4*lane+k);return x;});
}
template<class Guard> inline int attention_count(ng::Shape s,ng::Args a,int r,Guard guard){
 int n=0,S=slots(s),limit=std::min(s.capacity,S),pos=a.i(17)[0];
 while(n<S&&a.i(4)[r*S+n]!=-1){int id=a.i(4)[r*S+n];
  if(n>=limit||id<0||id>=s.capacity||id>pos+r){guard.fail(a);return -1;}++n;
 }
 return n;
}
inline float norm_value(ng::Shape s,ng::Args a,int row,int k){
 int w=width(s);if(s.op!=ng::combine_norm)return a.b(0,row*w+k);
 return ng::Args::bf(a.b(0,row*w+k)+a.b(1,(row/s.heads)*w+k)*(2.f*ng::sigmoid(a.b(2,row)/4.f)));
}
template<class Get> inline float rounded_normalized(Get get,ng::Args a,int gain,int k,int flags,float inv){return ng::Args::bf((get(k)*inv)*(a.weight(gain,k,flags)+float(flags&1)));}
template<class Get> inline float rotary(Get get,ng::Args a,int gain,int k,int flags,float inv,int position){
 float v=rounded_normalized(get,a,gain,k,flags,inv);if(k>=64)return v;
 int j=k%32;float c=rope_constants::cos(static_cast<const uint16_t*>(a.p[16]),position,j),z=rope_constants::sin(static_cast<const uint16_t*>(a.p[16]),position,j);
 float lo=rounded_normalized(get,a,gain,j,flags,inv),hi=rounded_normalized(get,a,gain,j+32,flags,inv);
 return k<32?lo*c-hi*z:hi*c+lo*z;
}

template<class Guard> inline void body(ng::Shape s,ng::Args a,int stage,size_t index,float* scratch,Guard guard){
 if(index>=work_items(s,stage)||!a.i(18)[0]||guard.error(a))return;
 int pos=a.i(17)[0];if(pos<0||pos>s.capacity-s.tokens){if(index==0)guard.fail(a);return;}
 if(s.op==ng::norm||s.op==ng::combine_norm||s.op==ng::gated_norm){
  int w=width(s),C=ceildiv(w,tile);
  if(stage==0){int row=int(index)/C,c=int(index)%C;
   scratch[row*C+c]=subtree(w,c,[&](int k){float x=norm_value(s,a,row,k);return x*x;});
  }else{int per=ceildiv(w,4),row=int(index)/per,first=(int(index)%per)*4;
   float inv=detmath::rsqrt(upper(scratch+row*C,C)/float(w)+1e-6f);
   for(int k=first;k<std::min(w,first+4);++k){float x=norm_value(s,a,row,k);
    int slot=s.op==ng::combine_norm?3:s.op==ng::gated_norm?2:1;
    float y=(x*inv)*(a.weight(slot,(s.op==ng::gated_norm?0:(row%s.heads)*w)+k,s.flags)+float(s.flags&1));
    if(s.op==ng::gated_norm)y=y*ng::sigmoid(a.b(1,row*w+k));
    a.put(s.op==ng::combine_norm?5:s.op==ng::gated_norm?3:2,row*w+k,y);
    if(s.op==ng::combine_norm)a.put(4,row*w+k,x);
   }
  }
 }else if(s.op==ng::gdn){
  constexpr int step=4192;
  if(stage==0){int row=int(index)/112,part=int(index)%112;float* out=scratch+row*step;
   if(part<64){int key=part/4,first=(part%4)*32;size_t qb=size_t(row)*10240+key*128,kb=qb+2048;
    float qn=detmath::sqrt(dot128([&](int k){float v=a.b(0,qb+k);return v*v;})+1e-6f);
    float kn=detmath::sqrt(dot128([&](int k){float v=a.b(0,kb+k);return v*v;})+1e-6f);
    for(int k=first;k<first+32;++k){out[key*128+k]=(a.b(0,qb+k)/qn)/detmath::sqrt(float(128));out[2048+key*128+k]=a.b(0,kb+k)/kn;}
   }else{int h=part-64;float gate=a.b(1,row*48+h)+a.weight(4,h,s.flags);
    float sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate;
    float av=(s.flags&2)?a.f(3)[h]:-detmath::exp(a.weight(3,h,s.flags));
    out[4096+h]=detmath::exp(av*sp);out[4144+h]=ng::sigmoid(a.b(2,row*48+h));
   }
  }else{int h=int(index)/128,j=int(index)%128,key=(s.flags&4)?h%16:h/3,state=(h*128+j)*128;
   for(int row=0;row<s.tokens;++row){const float* in=scratch+row*step;float v[128];
    for(int k=0;k<128;++k)v[k]=a.b(row?7:5,state+k)*in[4096+h];
    float pred=dot128([&](int k){return v[k]*in[2048+key*128+k];});
    float delta=(a.b(0,row*10240+4096+h*128+j)-pred)*in[4144+h];
    for(int k=0;k<128;++k)v[k]=v[k]+delta*in[2048+key*128+k];
    float y=dot128([&](int k){return v[k]*in[key*128+k];});
    a.put(6,(row*48+h)*128+j,y);for(int k=0;k<128;++k)a.put(7,state+k,v[k]);
   }
  }
 }else if(s.op==ng::prepare){
  int per=stage==0?8:64,row=int(index)/per,c=int(index)%per,r=row/30,h=row%30;
  int w=h<26?256:128,gain=h<24?3:h<26?4:5,out=h<24?6:h<26?8:9;
  int input=h<24?0:h<26?1:2,base=h<24?(r*24+h)*512:h<26?(r*2+h-24)*256:(r*4+h-26)*128;
  int target=h<24?(r*24+h)*256:h<26?(r*2+h-24)*256:(r*4+h-26)*128;
  auto get=[&](int k){return a.b(input,base+k);};
  if(stage==0){if(c<ceildiv(w,tile))scratch[row*8+c]=subtree(w,c,[&](int k){float v=get(k);return v*v;});}
  else if(c*4<w){float inv=detmath::rsqrt(upper(scratch+row*8,ceildiv(w,tile))/float(w)+1e-6f);
   for(int k=c*4;k<c*4+4;++k){a.put(out,target+k,rotary(get,a,gain,k,s.flags,inv,pos+r));if(h<24)a.put(7,target+k,a.b(0,base+256+k));}
  }
 }else if(s.op==ng::pool){
  int blocks=ceildiv(s.capacity,4);
  if(stage==0&&index>=size_t(blocks)*4){int j=int(index)-blocks*4;
   if(j<s.tokens*512){a.put(4,pos*512+j,a.b(0,j));a.put(5,pos*512+j,a.b(1,j));}
   else if(j<s.tokens*640){int k=j-s.tokens*512;a.put(6,pos*128+k,a.b(2,k));}
   return;
  }
  int per=stage==0?4:32,block=int(index)/per,c=int(index)%per;
  if(block<pos/4||block>=(pos+s.tokens)/4)return;
  auto get=[&](int k){float v=0.f;for(int j=0;j<4;++j){int r=block*4+j;v=v+(r<pos?a.b(6,r*128+k):a.b(2,(r-pos)*128+k));}return ng::Args::bf(v/4.f);};
  if(stage==0)scratch[block*4+c]=subtree(128,c,[&](int k){float v=get(k);return v*v;});
  else{float inv=detmath::rsqrt(upper(scratch+block*4,4)/float(128)+1e-6f);for(int k=c*4;k<c*4+4;++k)a.put(7,block*128+k,rotary(get,a,3,k,s.flags,inv,block*4));}
 }else if(s.op==ng::select){
  int cap=ceildiv(s.capacity,4),S=slots(s),per=stage==0?std::max(cap,S):cap;
  int r=int(index)/per,b=int(index)%per,n=(pos+r+1)/4,count=std::min(n,s.budget/4);
  if(stage==0){if(b<S)a.i(2)[r*S+b]=-1;
   if(b<n){float score=0.f;for(int h=0;h<4;++h){float d=private_tree<128>([&](int k){return a.b(0,(r*4+h)*128+k)*a.b(1,b*128+k);});score=score+std::max(0.f,d);}
    scratch[r*cap+b]=score/detmath::sqrt(float(128));}
  }else{bool finite=true;for(int k=0;k<n;++k)finite=finite&&std::isfinite(scratch[r*cap+k]);
   if(!finite){if(b==0)guard.fail(a);return;}
   if(b<n){float v=scratch[r*cap+b];int rank=0;for(int k=0;k<n;++k){float other=scratch[r*cap+k];rank+=other>v||(other==v&&k<b);}
    if(rank<count)for(int j=0;j<4;++j)a.i(2)[r*S+rank*4+j]=b*4+j;}
   if(b==0)for(int j=0;j<pos+r+1-n*4;++j)a.i(2)[r*S+count*4+j]=n*4+j;
  }
 }else if(s.op==ng::attention_score){
  int S=slots(s),L=std::min(s.capacity,S),slot=int(index)%L,head=int(index)/L,r=head/24,h=head%24,id=a.i(4)[r*S+slot];
  if(id < -1||id>=s.capacity||id>pos+r){guard.fail(a);return;}
  if(id<0){a.f(6)[head*S+slot]=-INFINITY;return;}
  float score=private_tree<256>([&](int k){return a.b(2,(id*2+h/12)*256+k)*a.b(0,head*256+k);});
  a.f(6)[head*S+slot]=score/detmath::sqrt(float(256));
 }else if(s.op==ng::attention_softmax){
  int S=slots(s),C=chunks(s),per=stage<2?C:ceildiv(std::min(s.capacity,S),4),head=int(index)/per,c=int(index)%per,r=head/24;
  int n=attention_count(s,a,r,guard);if(n<=0)return;int used=ceildiv(n,tile);
  float* maxima=scratch+head*C;float* sums=scratch+size_t(s.tokens)*24*C+head*C;
  if(stage==0){float m=-INFINITY;for(int k=c*tile;k<std::min(n,(c+1)*tile);++k)m=std::max(m,a.f(6)[head*S+k]);maxima[c]=m;
  }else if(stage==1){if(c>=used)return;float m=-INFINITY;for(int k=0;k<used;++k)m=std::max(m,maxima[k]);
   sums[c]=subtree(n,c,[&](int k){float v=detmath::exp(a.f(6)[head*S+k]-m);a.f(7)[head*S+k]=v;return v;});
  }else{float den=upper(sums,used);for(int k=c*4;k<std::min(n,c*4+4);++k)a.f(7)[head*S+k]=a.f(7)[head*S+k]/den;}
 }else if(s.op==ng::attention_value){
  int C=chunks(s),out=stage==0?int(index)/C:int(index),c=stage==0?int(index)%C:0;
  int k=out%256,h=(out/256)%24,r=out/6144,S=slots(s),n=attention_count(s,a,r,guard);if(n<=0)return;
  if(stage==0){if(c>=ceildiv(n,tile))return;
   scratch[size_t(out)*C+c]=subtree(n,c,[&](int j){int id=a.i(4)[r*S+j];return a.f(7)[(r*24+h)*S+j]*a.b(3,(id*2+h/12)*256+k);});
  }else{float value=upper(scratch+size_t(out)*C,ceildiv(n,tile));a.put(5,out,ng::Args::bf(value)*ng::sigmoid(a.b(1,out)));}
 }
}
struct HostGuard {int error(ng::Args a)const{return a.i(15)[0];}void fail(ng::Args a)const{a.i(15)[0]=1;}};
inline void cpu(ng::Shape s,ng::Args a){
 ng::validate(s);if(!supported(s)){ng::cpu(s,a);return;}
 std::vector<float> scratch(scratch_floats(s));
 for(int stage=0;stage<stages(s);++stage)for(size_t i=0;i<work_items(s,stage);++i)body(s,a,stage,i,scratch.data(),HostGuard{});
}
} // namespace ng2
