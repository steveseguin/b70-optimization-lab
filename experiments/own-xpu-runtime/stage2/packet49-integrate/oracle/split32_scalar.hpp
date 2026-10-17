#pragma once
// Independent full-model CPU specification of packet47's split32 arithmetic.
// The callbacks read already-rounded BF16 values; no device scheduling is used.
#include <algorithm>
#include <vector>
#include <cmath>
namespace p49oracle {
inline float tree(std::vector<float> x) {
  for(size_t step=1;step<x.size();step*=2)
    for(size_t j=0;j<x.size();j+=2*step)x[j]=x[j]+(j+step<x.size()?x[j+step]:0.f);
  return x[0];
}
template<class Score,class Value>
std::vector<float> split32(int count,int width,Score score,Value value) {
  const int blocks=(count+31)/32;
  std::vector<float> maxima(blocks),sums(blocks),partials(blocks*width);
  for(int b=0;b<blocks;++b){
    const int end=std::min(count,(b+1)*32);
    std::vector<float> weights(32,0.f);float maximum=-INFINITY;
    for(int j=b*32;j<end;++j){float s=score(j);weights[j-b*32]=s;maximum=std::max(maximum,s);}
    maxima[b]=maximum;
    for(int j=b*32;j<end;++j)weights[j-b*32]=detmath::exp(weights[j-b*32]-maximum);
    sums[b]=tree(weights);
    for(int d=0;d<width;++d){std::vector<float> terms(32,0.f);
      for(int j=b*32;j<end;++j)terms[j-b*32]=weights[j-b*32]*value(j,d);
      partials[b*width+d]=tree(terms);
    }
  }
  float maximum=*std::max_element(maxima.begin(),maxima.end());
  std::vector<float> scales(blocks),den_terms(blocks),out(width);
  for(int b=0;b<blocks;++b){scales[b]=detmath::exp(maxima[b]-maximum);den_terms[b]=sums[b]*scales[b];}
  float denominator=tree(den_terms);
  for(int d=0;d<width;++d){std::vector<float> terms(blocks);
    for(int b=0;b<blocks;++b)terms[b]=partials[b*width+d]*scales[b];
    out[d]=tree(terms)/denominator;
  }
  return out;
}
}
