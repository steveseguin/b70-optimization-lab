#pragma once
// Exact strict reader extracted from pinned P198 checkpoint.hpp; no native operations.
#include <string>
#include <vector>
#include <stdexcept>
#include <utility>
namespace p209 {
struct CJson {
  enum Kind {Null,Bool,Number,String,Array,Object};
  Kind kind=Null; bool boolean=false; std::string text;   // number literal or decoded string
  std::vector<CJson> items;                               // array elements, or object values
  std::vector<std::string> keys;                          // object keys, parallel to items
  const CJson* find(const std::string& k) const;
};
inline const CJson* CJson::find(const std::string& k) const {
  for(size_t j=0;j<keys.size();++j)if(keys[j]==k)return &items[j];
  return nullptr;
}
struct CJsonParser {
  const std::string& s; size_t i=0; int depth=0;
  explicit CJsonParser(const std::string& t):s(t){}
  [[noreturn]] void fail(const std::string& why) const {throw std::runtime_error("json: "+why+" at byte "+std::to_string(i));}
  static bool digit(char c){return c>='0'&&c<='9';}
  void ws(){while(i<s.size()&&(s[i]==' '||s[i]=='\n'||s[i]=='\r'||s[i]=='\t'))++i;}
  bool eat(char c){ws();if(i<s.size()&&s[i]==c){++i;return true;}return false;}
  void expect(char c){if(!eat(c))fail(std::string("expected '")+c+"'");}
  static void utf8(std::string& o,unsigned cp) {
    if(cp<0x80)o+=char(cp);
    else if(cp<0x800){o+=char(0xC0|(cp>>6));o+=char(0x80|(cp&0x3F));}
    else {o+=char(0xE0|(cp>>12));o+=char(0x80|((cp>>6)&0x3F));o+=char(0x80|(cp&0x3F));}
  }
  std::string string() {
    ws();if(i>=s.size()||s[i]!='"')fail("expected string");++i;std::string o;
    while(true) {
      if(i>=s.size())fail("unterminated string");
      const unsigned char c=static_cast<unsigned char>(s[i++]);
      if(c=='"')return o;
      if(c<0x20)fail("raw control character in string");
      if(c!='\\'){o+=char(c);continue;}
      if(i>=s.size())fail("truncated escape");
      const char e=s[i++];
      switch(e) {
        case '"':o+='"';break; case '\\':o+='\\';break; case '/':o+='/';break;
        case 'b':o+='\b';break; case 'f':o+='\f';break; case 'n':o+='\n';break;
        case 'r':o+='\r';break; case 't':o+='\t';break;
        case 'u': {
          if(i+4>s.size())fail("short \\u escape");
          unsigned cp=0;
          for(int k=0;k<4;++k){const char h=s[i++];cp<<=4;
            if(h>='0'&&h<='9')cp|=unsigned(h-'0');else if(h>='a'&&h<='f')cp|=unsigned(h-'a'+10);
            else if(h>='A'&&h<='F')cp|=unsigned(h-'A'+10);else fail("bad \\u hex digit");}
          if(cp>=0xD800&&cp<=0xDFFF)fail("surrogate escape (never written by the checkpoint writer)");
          utf8(o,cp);break;
        }
        default:fail("unknown escape");
      }
    }
  }
  CJson value() {
    ws();if(i>=s.size())fail("unexpected end");
    if(++depth>64)fail("nesting deeper than 64");
    CJson v;const char c=s[i];
    if(c=='{') {
      ++i;v.kind=CJson::Object;ws();
      if(i<s.size()&&s[i]=='}')++i;
      else while(true) {
        std::string k=string();
        for(const auto& f:v.keys)if(f==k)fail("duplicate key "+k);
        expect(':');CJson item=value();v.keys.push_back(std::move(k));v.items.push_back(std::move(item));
        if(eat(','))continue;
        expect('}');break;
      }
    } else if(c=='[') {
      ++i;v.kind=CJson::Array;ws();
      if(i<s.size()&&s[i]==']')++i;
      else while(true){v.items.push_back(value());if(eat(','))continue;expect(']');break;}
    } else if(c=='"'){v.kind=CJson::String;v.text=string();}
    else if(s.compare(i,4,"true")==0){i+=4;v.kind=CJson::Bool;v.boolean=true;}
    else if(s.compare(i,5,"false")==0){i+=5;v.kind=CJson::Bool;}
    else if(s.compare(i,4,"null")==0){i+=4;}
    else {
      const size_t b=i;if(s[i]=='-')++i;
      if(i<s.size()&&s[i]=='0')++i;
      else {if(i>=s.size()||s[i]<'1'||s[i]>'9')fail("bad number");while(i<s.size()&&digit(s[i]))++i;}
      if(i<s.size()&&s[i]=='.'){++i;if(i>=s.size()||!digit(s[i]))fail("bad fraction");while(i<s.size()&&digit(s[i]))++i;}
      if(i<s.size()&&(s[i]=='e'||s[i]=='E')){++i;if(i<s.size()&&(s[i]=='+'||s[i]=='-'))++i;
        if(i>=s.size()||!digit(s[i]))fail("bad exponent");while(i<s.size()&&digit(s[i]))++i;}
      v.kind=CJson::Number;v.text=s.substr(b,i-b);
    }
    --depth;return v;
  }
};
static CJson checkpoint_parse_json(const std::string& text) {
  CJsonParser p(text);CJson v=p.value();p.ws();
  if(p.i!=text.size())p.fail("trailing bytes after the manifest object");
  return v;
}
}
