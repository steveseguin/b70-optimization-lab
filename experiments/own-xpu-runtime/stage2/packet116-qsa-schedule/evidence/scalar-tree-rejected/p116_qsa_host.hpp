#pragma once
#include "p49_qsa_reference.hpp"
#include "round2.hpp"
namespace p116 {
// Breadth-first adjacent tree. The rejected recursive visit changed GNU NaN
// payload selection; keep the original storage/update order explicitly.
template<int Begin,int Count,class Leaf> inline float fixed_tree(const Leaf& leaf){
 float values[Count];for(int j=0;j<Count;++j)values[j]=leaf(Begin+j);
 for(int z=1;z<Count;z*=2)for(int j=0;j<Count;j+=2*z)values[j]=values[j]+values[j+z];
 return values[0];
}
inline float select_dot(ng::Args a,int r,int h,int b){
 return fixed_tree<0,128>([&](int k){return a.b(0,(r*4+h)*128+k)*a.b(1,b*128+k);});
}
template<int Stage> inline void selection_host(ng::Shape s,ng::Args a,float* global){
 if(!a.i(18)[0]||a.i(15)[0])return;int pos=a.i(17)[0];
 if(pos<0||pos>ng::position_limit(s)-s.tokens){a.i(15)[0]=1;return;}
 int cap=(s.capacity+3)/4,S=s.budget+3;
 for(int r=0;r<s.tokens;++r){int n=(pos+r+1)/4,count=std::min(n,s.budget/4);
  if constexpr(Stage==0){for(int b=n-1;b>=0;--b){float score=0.f;for(int h=0;h<4;++h)score=score+std::max(0.f,select_dot(a,r,h,b));global[r*cap+b]=score/detmath::sqrt(128.f);}}
  else {bool finite=true;for(int k=0;k<n;++k)finite=finite&&std::isfinite(global[r*cap+k]);
   if(!finite){std::fill_n(a.i(2)+r*S,S,-1);a.i(15)[0]=1;continue;}
   for(int k=0;k<S-count*4-(pos+r+1-n*4);++k)a.i(2)[r*S+count*4+(pos+r+1-n*4)+k]=-1;
   for(int k=0;k<pos+r+1-n*4;++k)a.i(2)[r*S+count*4+k]=n*4+k;
   for(int b=n-1;b>=0;--b){float v=global[r*cap+b];int partial[32]{};
    for(int lane=0;lane<32;++lane)for(int k=lane;k<n;k+=32){float x=global[r*cap+k];partial[lane]+=x>v||(x==v&&k<b);}
    int rank=0;for(int v:partial)rank+=v;if(rank<count)for(int k=0;k<4;++k)a.i(2)[r*S+rank*4+k]=b*4+k;
   }
  }
 }
}
inline void attention_host(ng::Shape s,ng::Args a){
 p47ref::validate(s,a);if(!a.i(18)[0]||a.i(15)[0])return;int S=s.budget+3;
 for(int r=0;r<s.tokens;++r){int n=p47ref::count(s,a,r);if(!n)continue;int C=(n+31)/32;
  for(int h=23;h>=0;--h){std::vector<float> partial(C*258);
   for(int c=C-1;c>=0;--c){float scores[32]{},prob[32]{};int valid=std::min(32,n-c*32);float m=-INFINITY;
    for(int j=0;j<valid;++j){scores[j]=p47ref::score(s,a,r,h,c*32+j);m=std::max(m,scores[j]);}
    for(int j=0;j<valid;++j)prob[j]=detmath::exp(scores[j]-m);
    partial[c*258+256]=m;partial[c*258+257]=fixed_tree<0,32>([&](int j){return prob[j];});
    for(int d=255;d>=0;--d)partial[c*258+d]=fixed_tree<0,32>([&](int j){return j<valid?prob[j]*a.b(3,(a.i(4)[r*S+c*32+j]*2+h/12)*256+d):0.f;});
   }
   float m=-INFINITY;for(int c=0;c<C;++c)m=std::max(m,partial[c*258+256]);std::vector<float> factors(C),terms(C);
   for(int c=0;c<C;++c){factors[c]=detmath::exp(partial[c*258+256]-m);terms[c]=partial[c*258+257]*factors[c];}
   float den=p47ref::adjacent(terms);
   for(int d=255;d>=0;--d){for(int c=0;c<C;++c)terms[c]=partial[c*258+d]*factors[c];p47ref::store(a,(r*24+h)*256+d,p47ref::adjacent(terms)/den,nullptr);}
  }
 }
}
}
