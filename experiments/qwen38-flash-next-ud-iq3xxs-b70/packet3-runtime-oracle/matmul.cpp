// CPU C ABI for the runtime's arithmetic identity; no device implementation.
#include "../../own-xpu-runtime/stage2/packet13-integrate/arithmetic.hpp"
extern "C" int variant(unsigned type,unsigned rows,unsigned cols,unsigned experts) {
  try {return integrated::arithmetic::variant(iq3::Type(type),rows,cols,experts,false);}
  catch (...) {return -1;}
}
extern "C" void matmul(unsigned type,const uint8_t* w,const uint16_t* x,
                        float* y,unsigned rows,unsigned cols,unsigned batch,unsigned v) {
  auto t=iq3::Type(type);auto l=iq3::layout(t);size_t rb=cols/l.elements*l.bytes;
  for(unsigned b=0;b<batch;++b)for(unsigned r=0;r<rows;++r)
    y[size_t(b)*rows+r]=integrated::arithmetic::row(t,w+r*rb,x+size_t(b)*cols,cols,v);
}
