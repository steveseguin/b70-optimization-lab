#define main p214_model_body
#include "main.cpp"
#undef main
extern "C" int p214_future_entry(int argc,char**argv){return p214_model_body(argc,argv);}
int main(int,char**){std::cerr<<"P214 compile-only: all executable invocations disabled; native qualification pending\n";return 64;}
