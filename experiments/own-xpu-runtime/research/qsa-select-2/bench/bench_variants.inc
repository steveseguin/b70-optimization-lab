// included inside main(): launch wrappers for select_fast.hpp variants
{
 auto s0f=[](auto bps){return Fn([](sycl::queue&q,ng::Shape s,ng::Args a,float*scratch){s.op=ng::select;constexpr int B=decltype(bps)::value;
  const size_t sub=size_t(s.tokens)*select_groups<B>(s);const size_t glob=(sub*32+255)/256*256;
  return q.parallel_for(sycl::nd_range<1>(glob,256),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{select_scores_sg<B>(s,a,it,scratch,Guard{});});});};
 Fn s1f=[](sycl::queue&q,ng::Shape s,ng::Args a,float*scratch){s.op=ng::select;
  return q.submit([&](sycl::handler& h){sycl::local_accessor<int,1> idx(sycl::range<1>(size_t(s.budget/4)),h);sycl::local_accessor<float,1> val(sycl::range<1>(size_t(s.budget/4)),h);
   sycl::local_accessor<int,1> hist(sycl::range<1>(select_hist_ints),h);sycl::local_accessor<int,1> found(sycl::range<1>(select_found_ints),h);sycl::local_accessor<int,1> part(sycl::range<1>(1024),h);
   h.parallel_for(sycl::nd_range<1>(sycl::range<1>(size_t(s.tokens)*1024),sycl::range<1>(1024)),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    select_topk_row2(s,a,it,scratch,idx.get_multi_ptr<sycl::access::decorated::no>().get(),val.get_multi_ptr<sycl::access::decorated::no>().get(),hist.get_multi_ptr<sycl::access::decorated::no>().get(),found.get_multi_ptr<sycl::access::decorated::no>().get(),part.get_multi_ptr<sycl::access::decorated::no>().get(),Guard{});});});};
 auto s1d=[](auto ph){return Fn([](sycl::queue&q,ng::Shape s,ng::Args a,float*scratch){s.op=ng::select;constexpr int P=decltype(ph)::value;
  return q.submit([&](sycl::handler& h){sycl::local_accessor<int,1> idx(sycl::range<1>(size_t(s.budget/4)),h);sycl::local_accessor<float,1> val(sycl::range<1>(size_t(s.budget/4)),h);
   sycl::local_accessor<int,1> hist(sycl::range<1>(select_hist_ints),h);sycl::local_accessor<int,1> found(sycl::range<1>(select_found_ints),h);sycl::local_accessor<int,1> part(sycl::range<1>(1024),h);
   h.parallel_for(sycl::nd_range<1>(sycl::range<1>(size_t(s.tokens)*1024),sycl::range<1>(1024)),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    select_topk_row2_diag<P>(s,a,it,scratch,idx.get_multi_ptr<sycl::access::decorated::no>().get(),val.get_multi_ptr<sycl::access::decorated::no>().get(),hist.get_multi_ptr<sycl::access::decorated::no>().get(),found.get_multi_ptr<sycl::access::decorated::no>().get(),part.get_multi_ptr<sycl::access::decorated::no>().get(),Guard{});});});});};
 for(int p=1;p<=5;++p){static const char* nm[]={"","r2_ph1_finite","r2_ph2_radix0","r2_ph3_radix3","r2_ph4_compact","r2_ph5_rank"};
  Fn f=p==1?s1d(std::integral_constant<int,1>{}):p==2?s1d(std::integral_constant<int,2>{}):p==3?s1d(std::integral_constant<int,3>{}):p==4?s1d(std::integral_constant<int,4>{}):s1d(std::integral_constant<int,5>{});
  vars.push_back({nm[p],ref_s0,f,false});}
 vars.push_back({"s0sg4",s0f(std::integral_constant<int,4>{}),ref_s1p<0>});
 vars.push_back({"s0sg8",s0f(std::integral_constant<int,8>{}),ref_s1p<0>});
 vars.push_back({"fast4",s0f(std::integral_constant<int,4>{}),s1f});
 vars.push_back({"s0sg16",s0f(std::integral_constant<int,16>{}),ref_s1p<0>});
 vars.push_back({"s0sg32",s0f(std::integral_constant<int,32>{}),ref_s1p<0>});
 vars.push_back({"s1row2",ref_s0,s1f});
 vars.push_back({"fast8",s0f(std::integral_constant<int,8>{}),s1f});
}
