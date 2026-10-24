#define main packet26_model_entry
#include "gsq-rco-iq3s/dense-packed-block/engine/build/source/main.cpp"
#undef main
int main(int argc,char**argv){std::vector<char*> args;args.push_back(argv[0]);bool precision=false;for(int i=1;i<argc;++i){if(std::string_view(argv[i])=="--recurrent-f32")precision=true;else args.push_back(argv[i]);}if(!precision)return 64;args.push_back(nullptr);argc=int(args.size()-1);argv=args.data();bool gsq=false,attention=false,qkv=false;for(int i=1;i<argc;++i){std::string_view x(argv[i]);gsq|=x=="--gsq-packed";attention|=x=="--attention-q8-p33";qkv|=x=="--qkv-q6-p33";}if(!gsq||!attention||!qkv)return 64;return packet26_model_entry(argc,argv);}
