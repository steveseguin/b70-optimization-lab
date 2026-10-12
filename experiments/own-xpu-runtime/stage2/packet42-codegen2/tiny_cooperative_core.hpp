#pragma once
#include "../packet29-merged/kernels.hpp"
// Exact ng::group statement body; only op dispatch becomes a template constant.
namespace p42tiny {using namespace ng;
template<ng::Op Code,class Team> inline void cooperative_group(Shape s,Args a,int group,Team t){
 // slots 15/17/18 = sticky_error/position/active; slot16 = RoPE; no readback.
 t.each(1,[&](int){t.x[0]=float(!a.i(18)[0]||t.error(a));});t.barrier();
 if(t.x[0])return;
 t.barrier();
 int pos=a.i(17)[0];
 if(pos<0||pos>s.capacity-s.tokens){if(group==0)t.each(1,[&](int){t.fail(a);});return;}
 bool unit=s.flags&1;
 if constexpr(Code==gdn){
  int h=group/128,j=group%128,key=(s.flags&4)?h%16:h/3;
  for(int row=0;row<s.tokens;++row){
   size_t qbase=size_t(row)*10240+key*128,kbase=qbase+2048;
   float qn=detmath::sqrt(dot128(t,[&](int k){float v=a.b(0,qbase+k);return v*v;})+1e-6f);t.barrier();
   float kn=detmath::sqrt(dot128(t,[&](int k){float v=a.b(0,kbase+k);return v*v;})+1e-6f);t.barrier();
   float gate=a.b(1,row*48+h)+a.weight(4,h,s.flags),sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate;
   float av=(s.flags&2)?a.f(3)[h]:-detmath::exp(a.weight(3,h,s.flags));float decay=detmath::exp(av*sp);
   int state=(h*128+j)*128;
   t.each(128,[&](int k){t.x[k]=(a.b(0,qbase+k)/qn)/detmath::sqrt(float(128));t.x[128+k]=a.b(0,kbase+k)/kn;t.x[256+k]=a.b(row?7:5,state+k)*decay;});t.barrier();
   float pred=dot128(t,[&](int k){return t.x[256+k]*t.x[128+k];});t.barrier();
   float delta=(a.b(0,row*10240+4096+h*128+j)-pred)*sigmoid(a.b(2,row*48+h));
   t.each(128,[&](int k){t.x[256+k]=t.x[256+k]+delta*t.x[128+k];});t.barrier();
   float y=dot128(t,[&](int k){return t.x[256+k]*t.x[k];});t.barrier();
   t.each(1,[&](int){a.put(6,(row*48+h)*128+j,y);});
   t.each(128,[&](int k){a.put(7,state+k,t.x[256+k]);});t.barrier();
  }
 }else if constexpr(Code==conv){
  t.each(128,[&](int lane){int ch=group*128+lane;if(ch>=s.width)return;int dilation=s.extra?s.extra:1,hist=3*dilation;
   float history[9];for(int j=0;j<hist;++j)history[j]=a.b(1,ch*hist+j);
   for(int r=0;r<s.tokens;++r){float x=a.b(0,r*s.width+ch),acc=0;for(int tap=0;tap<4;++tap)acc=acc+(tap==3?x:history[tap*dilation])*a.weight(2,ch*4+tap,s.flags);
    a.put(3,r*s.width+ch,silu(dilation==3?Args::bf(acc):acc));for(int k=0;k<hist-1;++k)history[k]=history[k+1];history[hist-1]=x;}
   for(int j=0;j<hist;++j)a.put(4,ch*hist+j,history[j]);});
 }else if constexpr(Code==norm||Code==combine_norm||Code==gated_norm){
  int width=Code==gated_norm?128:s.width,stream=group%s.heads,base=group*width;
  auto value=[&](int k){if(Code!=combine_norm)return a.b(0,base+k);return Args::bf(a.b(0,base+k)+a.b(1,(group/s.heads)*width+k)*(2.f*sigmoid(a.b(2,group)/4.f)));};
  float inv=detmath::rsqrt(tree(t,width,[&](int k){float x=value(k);return x*x;})/float(width)+1e-6f);t.barrier();
  t.each(width,[&](int k){float x=value(k);int wslot=Code==combine_norm?3:Code==gated_norm?2:1;
   float y=(x*inv)*(a.weight(wslot,(Code==gated_norm?0:stream*width)+k,s.flags)+float(unit));
   if constexpr(Code==gated_norm)y=y*sigmoid(a.b(1,base+k));
   a.put(Code==combine_norm?5:Code==gated_norm?3:2,base+k,y);if constexpr(Code==combine_norm)a.put(4,base+k,x);});
 }else if constexpr(Code==activation||Code==mix||Code==moe_combine){
  t.each(128,[&](int lane){int idx=group*128+lane;if(idx>=s.tokens*s.width)return;int r=idx/s.width,k=idx%s.width;
   if constexpr(Code==activation){float v=a.b(0,idx);a.put(2,idx,s.extra?silu(v)*a.b(1,idx):silu(v/4.f));}
   else if constexpr(Code==mix){float sum=0;for(int h=0;h<4;++h)sum=sum+sigmoid(a.b(1,(r*4+h)*s.width+k))*a.b(0,(r*4+h)*s.width+k);a.put(2,idx,sum/4.f);}
   else{float sum=0;for(int e=0;e<s.extra;++e)sum=sum+a.b(0,(r*s.extra+e)*s.width+k)*a.f(1)[r*s.extra+e];a.put(4,idx,Args::bf(sum)+Args::bf(a.b(2,idx)*sigmoid(a.b(3,r))));}
  });
 }else if constexpr(Code==route_gather){
  int r=group,n=s.width,top=s.extra;float maximum=-INFINITY;
  bool finite=true;for(int j=0;j<n;++j){float v=a.b(0,r*n+j);finite=finite&&std::isfinite(v);maximum=std::max(maximum,v);}
  if(!finite){t.each(1,[&](int){t.fail(a);});return;}
  t.each(n,[&](int j){t.x[j]=detmath::exp(a.b(0,r*n+j)-maximum);t.x[512+j]=t.x[j];});t.barrier();float den=t.sum(n);t.barrier();
  t.each(n,[&](int j){t.x[512+j]=t.x[512+j]/den;});t.barrier();
  t.each(n,[&](int j){int rank=0;float v=t.x[512+j];for(int k=0;k<n;++k)rank+=t.x[512+k]>v||(t.x[512+k]==v&&k<j);
   if(rank<top){a.i(2)[r*top+rank]=j;t.x[1024+rank]=v;a.i(5)[(r*top+rank)*3]=j;a.i(5)[(r*top+rank)*3+1]=0;a.i(5)[(r*top+rank)*3+2]=640;
    a.i(6)[(r*top+rank)*3]=j;a.i(6)[(r*top+rank)*3+1]=0;a.i(6)[(r*top+rank)*3+2]=2560;}});t.barrier();
  t.each(top,[&](int j){t.x[1536+j]=t.x[1024+j];});t.barrier();float selected=t.sum(top,1536);t.barrier();
  t.each(top,[&](int j){a.f(3)[r*top+j]=t.x[1024+j]/selected;});
  t.each(top*2560,[&](int j){a.put(4,r*top*2560+j,a.b(1,r*2560+j%2560));});
 }else if constexpr(Code==prepare){
  int r=group/30,h=group%30,position=pos+r;
  if(h<24){norm_rope(t,[&](int k){return a.b(0,(r*24+h)*512+k);},[&](int k,float v){a.put(6,(r*24+h)*256+k,v);a.put(7,(r*24+h)*256+k,a.b(0,(r*24+h)*512+256+k));},a,3,256,position,s.flags);}
  else if(h<26){h-=24;norm_rope(t,[&](int k){return a.b(1,(r*2+h)*256+k);},[&](int k,float v){a.put(8,(r*2+h)*256+k,v);},a,4,256,position,s.flags);}
  else{h-=26;norm_rope(t,[&](int k){return a.b(2,(r*4+h)*128+k);},[&](int k,float v){a.put(9,(r*4+h)*128+k,v);},a,5,128,position,s.flags);}
 }else if constexpr(Code==pool){
  int blocks=(s.capacity+3)/4;
  if(group==blocks){t.each(s.tokens*512,[&](int j){a.put(4,pos*512+j,a.b(0,j));a.put(5,pos*512+j,a.b(1,j));});t.each(s.tokens*128,[&](int j){a.put(6,pos*128+j,a.b(2,j));});}
  else if(group>=pos/4&&group<(pos+s.tokens)/4){
   auto pooled=[&](int k){float x=0;for(int j=0;j<4;++j){int r=group*4+j;x=x+(r<pos?a.b(6,r*128+k):a.b(2,(r-pos)*128+k));}return Args::bf(x/4.f);};
   norm_rope(t,pooled,[&](int k,float v){a.put(7,group*128+k,v);},a,3,128,group*4,s.flags);
  }
 }else if constexpr(Code==ng::select){
  int r=group,position=pos+r,n=(position+1)/4,cap=(s.capacity+3)/4,base=3*cap;
  for(int h=0;h<4;++h){
   // Parallel blocks; each block dot uses a fixed local private tree. Only 128 values.
   t.each(n,[&](int b){float v[128];for(int k=0;k<128;++k)v[k]=a.b(0,(r*4+h)*128+k)*a.b(1,b*128+k);for(int stride=1;stride<128;stride*=2)for(int k=0;k<128;k+=2*stride)v[k]=v[k]+v[k+stride];t.x[b]=(h?t.x[b]:0.f)+std::max(0.f,v[0]);});t.barrier();
  }
  (void)base;t.each(n,[&](int b){t.x[b]=t.x[b]/detmath::sqrt(float(128));});t.barrier();
  bool finite=true;for(int j=0;j<n;++j)finite=finite&&std::isfinite(t.x[j]);
  if(!finite){t.each(s.budget+3,[&](int j){a.i(2)[r*(s.budget+3)+j]=-1;});t.each(1,[&](int){t.fail(a);});return;}
  int count=std::min(n,s.budget/4),slots=s.budget+3;
  t.each(slots,[&](int j){a.i(2)[r*slots+j]=-1;});t.barrier();
  t.each(n,[&](int b){int rank=0;for(int k=0;k<n;++k)rank+=t.x[k]>t.x[b]||(t.x[k]==t.x[b]&&k<b);if(rank<count)for(int j=0;j<4;++j)a.i(2)[r*slots+rank*4+j]=b*4+j;});
  t.each(position+1-n*4,[&](int j){a.i(2)[r*slots+count*4+j]=n*4+j;});
 }else if constexpr(Code==attention_score){
  int slots=s.budget+3,launch_slots=std::min(s.capacity,slots),slot=group%launch_slots,h=(group/launch_slots)%24,r=group/(launch_slots*24),id=a.i(4)[r*slots+slot];
  int offset=(r*24+h)*slots+slot;
  if(id < -1||id>=s.capacity||id>pos+r){t.each(1,[&](int){t.fail(a);});return;}
  if(id<0){t.each(1,[&](int){a.f(6)[offset]=-INFINITY;});return;}
  float score=tree(t,256,[&](int k){return a.b(2,(id*2+h/12)*256+k)*a.b(0,(r*24+h)*256+k);})/detmath::sqrt(float(256));t.barrier();t.each(1,[&](int){a.f(6)[offset]=score;});
 }else if constexpr(Code==attention_softmax){
  int slots=s.budget+3,r=group/24,n=0;
  while(n<slots&&a.i(4)[r*slots+n]!=-1){int id=a.i(4)[r*slots+n];
   if(id<0||id>=s.capacity||id>pos+r||n>=std::min(s.capacity,slots)){t.each(1,[&](int){t.fail(a);});return;}++n;}
  if(!n)return;float m=-INFINITY;for(int k=0;k<n;++k)m=std::max(m,a.f(6)[group*slots+k]);
  t.each(n,[&](int k){float v=detmath::exp(a.f(6)[group*slots+k]-m);t.x[k]=v;a.f(7)[group*slots+k]=v;});t.barrier();float den=t.sum(n);t.barrier();
  t.each(n,[&](int k){a.f(7)[group*slots+k]=a.f(7)[group*slots+k]/den;});
 }else if constexpr(Code==attention_value){
  int k=group%256,h=(group/256)%24,r=group/(256*24),slots=s.budget+3,n=0;
  while(n<slots&&a.i(4)[r*slots+n]!=-1)++n;
  // This consumer validates independently of the score kernel. Clamp before
  // address arithmetic even when called directly with poisoned selection IDs.
  auto safe_id=[&](int j){int id=a.i(4)[r*slots+j];if(id<0||id>=s.capacity||id>pos+r){t.fail(a);return 0;}return id;};
  if(n>std::min(s.capacity,slots)){t.each(1,[&](int){t.fail(a);});return;}
  if(!n)return;float value=tree(t,n,[&](int j){int id=safe_id(j);return a.f(7)[(r*24+h)*slots+j]*a.b(3,(id*2+h/12)*256+k);});t.barrier();
  t.each(1,[&](int){a.put(5,group,Args::bf(value)*sigmoid(a.b(1,group)));});
 }
}
}
