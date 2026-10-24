#define main packet26_model_entry
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/recurrent-f32/build/source-v2/experiments/own-xpu-runtime/gsq-rco-iq3s/dense-packed-block/engine/build/source/main.cpp"
#undef main
int main(int argc,char**argv){std::vector<char*> args{argv[0]};bool f32=false,mini=false,gsq=false;for(int i=1;i<argc;++i){std::string_view x(argv[i]);if(x=="--recurrent-f32")f32=true;else args.push_back(argv[i]);mini|=x=="--mini";gsq|=x=="--gsq-packed";}if(!f32||!mini||!gsq)return 64;args.push_back(nullptr);return packet26_model_entry(int(args.size()-1),args.data());}
