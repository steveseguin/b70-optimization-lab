"""Parameter-storage-only deltas; imported packet bytes remain untouched."""
def apply(path,text):
 if path.name=='sycl_device.cpp':
  old="check_error(); auto wait=dependencies(deps); auto id=next_handle();\n    auto [it,inserted]=events_.try_emplace(id); (void)inserted;\n    it->second=native.submit(*queue_,bindings,wait); return id;"
  new="if(ownrt::preparing_parameters){native.submit(*queue_,bindings,{});return 0;}check_error(); auto wait=dependencies(deps);events_.try_emplace(0);try {auto submitted=native.submit(*queue_,bindings,wait);\n    auto id=next_handle();auto node=events_.extract(0);node.key()=id;node.mapped()=std::move(submitted);events_.insert(std::move(node));return id;}catch(...){events_.erase(0);throw;}"
  assert text.count(old)==1
  text=text.replace(old,new)
  oldcopy='h.depends_on(wait); h.memcpy(dst,src,n);'
  newcopy='h.depends_on(wait); if(ownrt::copy_is_device_to_device)h.parallel_for(sycl::range<1>(n),[=](sycl::id<1> i){static_cast<unsigned char*>(dst)[i]=static_cast<const unsigned char*>(src)[i];});else h.memcpy(dst,src,n);'
  assert text.count(oldcopy)==1
  return text.replace(oldcopy,newcopy)
 if path.parent.name=='packet7-kopt2' and path.name=='kernels.cpp':
  oldcopy='if(copy){h.memcpy(dst,src,n);return;}'
  assert text.count(oldcopy)==1
  text=text.replace(oldcopy,'if(copy){h.parallel_for(sycl::range<1>(n),[=](sycl::id<1> i){reinterpret_cast<unsigned char*>(dst)[i]=reinterpret_cast<const unsigned char*>(src)[i];});return;}')
 if path.parent.name not in ('packet6-kopt','packet7-kopt2','packet8-kopt3') or path.name!='kernels.cpp':return text
 if path.parent.name=='packet6-kopt':
  changes={"auto descriptions=desc;":"auto descriptions=packet23::parameters(desc);", "std::array<void*,28> pointers{};std::copy(p.begin(),p.end(),pointers.begin());":"std::array<void*,28> pointer_values{};std::copy(p.begin(),p.end(),pointer_values.begin());auto pointers=packet23::parameters(pointer_values)->data();", "descriptions[j]":"(*descriptions)[j]", "descriptions[which]":"(*descriptions)[which]"}
 else:
  changes={"auto descriptors=desc;":"auto descriptors=packet23::parameters(desc);", "std::array<void*,64> ptr{};std::copy(p.begin(),p.end(),ptr.begin());":"std::array<void*,64> pointer_values{};std::copy(p.begin(),p.end(),pointer_values.begin());auto ptr=packet23::parameters(pointer_values)->data();", "descriptors[j]":"(*descriptors)[j]", "descriptors[which]":"(*descriptors)[which]"}
 for old,new in changes.items():
  assert text.count(old)==1,(path,old,text.count(old))
  text=text.replace(old,new)
 return text
