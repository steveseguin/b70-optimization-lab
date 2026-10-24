// New-model ranks keep the actual inherited protocol and admission parser.
// A no-argument invocation never constructs a Device or reads model files.
#include "build/private/source/diet-native/native-src/entry-main.cpp"
int main(int argc,char**argv){bool mode=false;for(int i=1;i<argc;++i)if(std::string_view(argv[i])=="--gsq-packed")mode=true;if(!mode)return 64;return packet26_model_entry(argc,argv);}
