#include "detmath.hpp"
#include <cstdio>
#include <cstdlib>
int main(int argc,char**argv){ uint32_t start=std::strtoul(argv[1],0,16), n=262144; FILE*f=std::fopen(argv[2],"wb");
 for(uint32_t i=0;i<n;++i){ volatile float x=detmath::value(start+i); uint32_t y=detmath::bits(detmath::log(x)); std::fwrite(&y,4,1,f);} std::fclose(f); return 0; }
