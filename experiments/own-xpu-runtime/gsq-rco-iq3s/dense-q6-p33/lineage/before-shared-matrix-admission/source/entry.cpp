#define main packet26_model_entry
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/dense-q6-p33/build/source/main.cpp"
#undef main
int main(int argc,char**argv){bool gsq=false,attention=false,qkv=false;for(int i=1;i<argc;++i){std::string_view x(argv[i]);gsq|=x=="--gsq-packed";attention|=x=="--attention-q8-p33";qkv|=x=="--qkv-q6-p33";}if(!gsq||!attention||!qkv)return 64;return packet26_model_entry(argc,argv);}
