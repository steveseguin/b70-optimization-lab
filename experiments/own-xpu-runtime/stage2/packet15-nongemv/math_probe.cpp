// Standalone CPU diagnostic of elementary libraries, not a replacement oracle.
#include <cmath>
extern "C" void primitive(int op,const float* in,float* out,int n){
 for(int i=0;i<n;++i){float x=in[i];switch(op){
 case 0:out[i]=std::exp(x);break;
 case 1:out[i]=std::log(x);break;
 case 2:out[i]=std::sqrt(x);break;
 case 3:out[i]=1.f/(1.f+std::exp(-x));break;
 case 4:out[i]=1.f/std::sqrt(x);break;
 }}
}
