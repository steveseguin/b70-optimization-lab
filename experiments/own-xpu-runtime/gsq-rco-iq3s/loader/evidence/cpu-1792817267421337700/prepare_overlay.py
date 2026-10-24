"""Private actual iq3 loader overlay; never edits parent or parses model payload."""
from pathlib import Path
import difflib,hashlib,json,re
P=Path(__file__).resolve().parent; ROOT=P.parents[3]
BASE=ROOT/'experiments/own-xpu-runtime'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
FILES={'gguf.hpp':'stage2/packet2/loader/gguf.hpp','gguf.cpp':'stage2/packet2/loader/gguf.cpp','math.hpp':'stage2/packet2/kernels/math.hpp','grids.hpp':'stage2/packet2/kernels/grids.hpp','owner.hpp':'stage1/packet3-prep/src/owner.hpp'}
NATIVE=BASE/'stage2/packet195-record-bundle-diet/diet-native/native-base/experiments/own-xpu-runtime'


def replace(text,old,new):
    if text.count(old)!=1:raise ValueError('overlay anchor not unique: '+old[:70])
    return text.replace(old,new)


def transform(name,text):
    if name=='gguf.hpp':
        text=replace(text,'struct File;','''// The caller must independently authenticate this complete admission; never derive
// expected entries from the candidate plan or from just-read model headers.
struct ShardIdentity {
  std::string basename; uint64_t bytes,dev,ino,mtime_ns,ctime_ns;
};
struct File;''')
        text=replace(text,'explicit Shard(const std::filesystem::path&);','explicit Shard(const std::filesystem::path&,const ShardIdentity* expected=nullptr);')
        text=replace(text,'class Model {','''struct Admission {
  std::vector<ShardIdentity> shards;
  std::vector<Planned> expected;
};
class Model {
  Model(const std::vector<std::filesystem::path>&,std::vector<Planned>,const Admission*);''')
        text=replace(text,'  Model(const std::vector<std::filesystem::path>&,std::vector<Planned>);','''  Model(const std::vector<std::filesystem::path>&,std::vector<Planned>);
  Model(const std::vector<std::filesystem::path>&,std::vector<Planned>,const Admission&);''')
    if name=='gguf.cpp':
        text=replace(text,'O_RDONLY|O_CLOEXEC','O_RDONLY|O_CLOEXEC|O_NOFOLLOW')
        text=replace(text,'  ~File() {if(fd>=0)close(fd);}','''  void verify(const ShardIdentity& e) const {
    struct stat s{};
    require(!fstat(fd,&s) && S_ISREG(s.st_mode) && s.st_size>=0,"held shard stat unavailable");
    require(uint64_t(s.st_size)==e.bytes && uint64_t(s.st_dev)==e.dev && uint64_t(s.st_ino)==e.ino &&
      uint64_t(s.st_mtim.tv_sec)*1000000000ULL+uint64_t(s.st_mtim.tv_nsec)==e.mtime_ns &&
      uint64_t(s.st_ctim.tv_sec)*1000000000ULL+uint64_t(s.st_ctim.tv_nsec)==e.ctime_ns,"held shard identity differs");
  }
  ~File() {if(fd>=0)close(fd);}''')
        text=replace(text,'Shard::Shard(const std::filesystem::path& path):file(std::make_shared<File>(path)),basename(path.filename()) {','''Shard::Shard(const std::filesystem::path& path,const ShardIdentity* expected):file(std::make_shared<File>(path)),basename(path.filename()) {
  if(expected){require(expected->basename==basename,"admitted shard basename differs");file->verify(*expected);}''')
        text=replace(text,'void validate_splits(const std::vector<Shard>& shards) {','void validate_splits(const std::vector<Shard>& shards) {')
        end='  for(auto t:ordered) {require(t->offset>=end,"overlapping tensors");end=add(t->offset,t->bytes);require(add(data_start,end)<=file_bytes,"tensor out of file");}\n}'
        text=replace(text,end,end[:-1]+'  if(expected)file->verify(*expected);\n}')
        old='Model::Model(const std::vector<std::filesystem::path>& paths,std::vector<Planned> p):plan(std::move(p)) {\n  for(auto& path:paths)shards.emplace_back(path);validate_splits(shards);'
        new='''Model::Model(const std::vector<std::filesystem::path>& paths,std::vector<Planned> p):Model(paths,std::move(p),nullptr) {}
Model::Model(const std::vector<std::filesystem::path>& paths,std::vector<Planned> p,const Admission& a):Model(paths,std::move(p),&a) {}
Model::Model(const std::vector<std::filesystem::path>& paths,std::vector<Planned> p,const Admission* admission):plan(std::move(p)) {
  std::map<std::string,const ShardIdentity*> admitted;
  if(admission) {
    require(paths.size()==2 && admission->shards.size()==2,"exact two admitted shards required");
    for(auto& s:admission->shards) {
      require(!s.basename.empty() && s.basename==std::filesystem::path(s.basename).filename() && s.basename!="." && s.basename!="..","unsafe admitted basename");
      require(admitted.emplace(s.basename,&s).second,"duplicate admitted shard");
    }
    std::set<std::string> seen;
    for(auto& path:paths)require(admitted.contains(path.filename()) && seen.insert(path.filename()).second,"candidate shard identity set differs");
    require(plan.size()==admission->expected.size() && !plan.empty(),"admitted tensor coverage differs");
    std::map<std::string,const Planned*> expected;
    const std::set<unsigned> supported={0,1,8,12,13,14,18,20,21,22,23,30,42};
    for(auto& e:admission->expected)require(expected.emplace(e.name,&e).second,"duplicate admitted tensor");
    seen.clear();
    for(auto& row:plan) {
      require(seen.insert(row.name).second && expected.contains(row.name),"admitted tensor names differ");
      const auto& e=*expected.at(row.name);
      require(supported.contains(unsigned(row.type)) && row.shard==e.shard && row.type==e.type && row.dimensions==e.dimensions && row.offset==e.offset && row.bytes==e.bytes && row.layer==e.layer && row.mask==e.mask && row.component==e.component,"admitted descriptor differs");
    }
  }
  for(auto& path:paths)shards.emplace_back(path,admission?admitted.at(path.filename()):nullptr);validate_splits(shards);'''
        text=replace(text,old,new)
        text=replace(text,'row.component=="hyperconnections" && row.type==Type::Q8_0','row.component=="hyperconnections" && (row.type==Type::Q8_0 || (admission && row.type==Type::BF16))')
        text=replace(text,'std::array<uint64_t,3> Model::census() const {','std::array<uint64_t,3> Model::census() const {')
        text=replace(text,'  }\n}\nstd::array<uint64_t,3> Model::census()', '  }\n  if(admission)for(auto& s:shards)s.file->verify(*admitted.at(s.basename));\n}\nstd::array<uint64_t,3> Model::census()')
    return text


def normalized(text):
    text='\n'.join(x for x in text.splitlines() if not x.startswith('#line ') and 'kernel_guard.hpp' not in x)+'\n'
    return re.sub(r'#include "[^"\n]*/([^/"\n]+)"',r'#include "\1"',text)


def prepare():
    pins=json.loads((P/'parent-pins.json').read_text())
    for name,want in pins.items():
        if sha(ROOT/name)!=want:raise ValueError('parent changed: '+name)
    dest=P/'build/private';dest.mkdir(parents=True,exist_ok=True)
    patches=[];nativepatch=[];outputs={};compat={}
    for name,relative in FILES.items():
        original=(BASE/relative).read_text()
        if name=='math.hpp':
            updated=(P.parent/'graph/build/private/packet2/kernels/math.hpp').read_text()
        else:updated=transform(name,original)
        (dest/name).write_text(updated);outputs[name]=sha(dest/name)
        patches.extend(difflib.unified_diff(original.splitlines(True),updated.splitlines(True),fromfile='a/'+relative,tofile='b/'+relative))
        if name in ('gguf.hpp','gguf.cpp'):
            native=(NATIVE/relative).read_text()
            if normalized(native)!=original:raise ValueError('P195 loader body differs')
            changed=transform(name,native)
            if normalized(changed)!=updated:raise ValueError('P195 overlay semantic mismatch')
            nativepatch.extend(difflib.unified_diff(native.splitlines(True),changed.splitlines(True),fromfile='a/'+relative,tofile='b/'+relative))
            compat[name]={'body_identical':True,'patched_body_identical':True,'p195_sha256':sha(NATIVE/relative)}
    (P/'overlay.patch').write_text(''.join(patches));(P/'p195-loader.patch').write_text(''.join(nativepatch))
    result={'schema':'ownrt.gsq.loader-overlay.v1','private_sha256':outputs,'p195_compatibility':compat,'native_admitted':False}
    (P/'overlay.json').write_text(json.dumps(result,indent=2)+'\n');return result
