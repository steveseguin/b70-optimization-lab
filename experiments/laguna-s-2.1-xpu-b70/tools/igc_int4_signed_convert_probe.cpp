// Static BMG code-generation probe for direct signed INT4 -> BF16 conversion.
#include <cstdio>
#include <sycl/sycl.hpp>

#include "csrc/xpu/grouped_gemm/xe_2/gemm_xe2.hpp"

using namespace cute;
using namespace MoE;

template <bool DIRECT>
class LagunaSignedInt4ConvertProbe;

CUTE_DEVICE void direct_signed_int4_to_bf16(
    intel::uchar4 const& src0,
    intel::ushort8& dst0,
    float& y0,
    float& y1) {
#if defined(CUTE_ARCH_REORDER_XE_ENABLED)
  const uint32_t widths = 0x00040004;
  const uint32_t offsets = 0x00040000;
  asm("{\n"
      ".decl IN_UB v_type=G type=UB num_elts=64 alias=<%1,0>\n"
      ".decl TMP_W v_type=G type=W num_elts=128 alias=<%0,0>\n"
      ".decl OUT_BF v_type=G type=BF num_elts=128 alias=<%0,0>\n"
      ".decl TMP_F v_type=G type=F num_elts=32\n"
      ".decl WIDTHS v_type=G type=UW num_elts=2 alias=<%4,0>\n"
      ".decl OFFSETS v_type=G type=UW num_elts=2 alias=<%5,0>\n"
      ".decl Y0_F v_type=G type=F num_elts=16 alias=<%2,0>\n"
      ".decl Y1_F v_type=G type=F num_elts=16 alias=<%3,0>\n"
      "bfe (M1_NM, 32) TMP_W(0,0)<1> WIDTHS(0,0)<0;2,1> "
      "OFFSETS(0,0)<0;2,1> IN_UB(0,0)<1;2,0>\n"
      "mov (M1_NM, 32) TMP_F(0,0)<1> TMP_W(0,0)<1;1,0>\n"
      "mul (M1, 16) OUT_BF(0,0)<1> TMP_F(0,0)<1;1,0> Y0_F(0,0)<1;1,0>\n"
      "mul (M1, 16) OUT_BF(0,16)<1> TMP_F(0,16)<1;1,0> Y1_F(0,0)<1;1,0>\n"
      "bfe (M1_NM, 32) TMP_W(1,0)<1> WIDTHS(0,0)<0;2,1> "
      "OFFSETS(0,0)<0;2,1> IN_UB(0,16)<1;2,0>\n"
      "mov (M1_NM, 32) TMP_F(0,0)<1> TMP_W(1,0)<1;1,0>\n"
      "mul (M1, 16) OUT_BF(1,0)<1> TMP_F(0,0)<1;1,0> Y0_F(0,0)<1;1,0>\n"
      "mul (M1, 16) OUT_BF(1,16)<1> TMP_F(0,16)<1;1,0> Y1_F(0,0)<1;1,0>\n"
      "bfe (M1_NM, 32) TMP_W(2,0)<1> WIDTHS(0,0)<0;2,1> "
      "OFFSETS(0,0)<0;2,1> IN_UB(0,32)<1;2,0>\n"
      "mov (M1_NM, 32) TMP_F(0,0)<1> TMP_W(2,0)<1;1,0>\n"
      "mul (M1, 16) OUT_BF(2,0)<1> TMP_F(0,0)<1;1,0> Y0_F(0,0)<1;1,0>\n"
      "mul (M1, 16) OUT_BF(2,16)<1> TMP_F(0,16)<1;1,0> Y1_F(0,0)<1;1,0>\n"
      "bfe (M1_NM, 32) TMP_W(3,0)<1> WIDTHS(0,0)<0;2,1> "
      "OFFSETS(0,0)<0;2,1> IN_UB(0,48)<1;2,0>\n"
      "mov (M1_NM, 32) TMP_F(0,0)<1> TMP_W(3,0)<1;1,0>\n"
      "mul (M1, 16) OUT_BF(3,0)<1> TMP_F(0,0)<1;1,0> Y0_F(0,0)<1;1,0>\n"
      "mul (M1, 16) OUT_BF(3,16)<1> TMP_F(0,16)<1;1,0> Y1_F(0,0)<1;1,0>\n"
      "}\n"
      : "=rw"(dst0)
      : "rw"(src0), "rw"(y0), "rw"(y1), "rw.u"(widths),
        "rw.u"(offsets));
#else
  CUTE_INVALID_CONTROL_PATH("Not Xe");
#endif
}

CUTE_DEVICE void baseline_scale_bf16(
    intel::ushort8& dst0,
    float& y0,
    float& y1) {
#if defined(CUTE_ARCH_REORDER_XE_ENABLED)
  asm("{\n"
      ".decl OUT_BF v_type=G type=BF num_elts=128 alias=<%0,0>\n"
      ".decl Y0_F v_type=G type=F num_elts=16 alias=<%1,0>\n"
      ".decl Y1_F v_type=G type=F num_elts=16 alias=<%2,0>\n"
      "mul (M1, 16) OUT_BF(0,0)<1> OUT_BF(0,0)<1;1,0> Y0_F(0,0)<1;1,0>\n"
      "mul (M1, 16) OUT_BF(0,16)<1> OUT_BF(0,16)<1;1,0> Y1_F(0,0)<1;1,0>\n"
      "mul (M1, 16) OUT_BF(1,0)<1> OUT_BF(1,0)<1;1,0> Y0_F(0,0)<1;1,0>\n"
      "mul (M1, 16) OUT_BF(1,16)<1> OUT_BF(1,16)<1;1,0> Y1_F(0,0)<1;1,0>\n"
      "mul (M1, 16) OUT_BF(2,0)<1> OUT_BF(2,0)<1;1,0> Y0_F(0,0)<1;1,0>\n"
      "mul (M1, 16) OUT_BF(2,16)<1> OUT_BF(2,16)<1;1,0> Y1_F(0,0)<1;1,0>\n"
      "mul (M1, 16) OUT_BF(3,0)<1> OUT_BF(3,0)<1;1,0> Y0_F(0,0)<1;1,0>\n"
      "mul (M1, 16) OUT_BF(3,16)<1> OUT_BF(3,16)<1;1,0> Y1_F(0,0)<1;1,0>\n"
      "}\n"
      : "+rw"(dst0)
      : "rw"(y0), "rw"(y1));
#endif
}

template <bool DIRECT>
void launch(
    sycl::queue& q,
    const intel::uchar4* src,
    intel::ushort8* dst) {
  namespace syclex = sycl::ext::oneapi::experimental;
  namespace intelex = sycl::ext::intel::experimental;
  q.submit([&](sycl::handler& cgh) {
     syclex::properties props{
         syclex::sub_group_size<16>, intelex::grf_size<128>};
     cgh.parallel_for<LagunaSignedInt4ConvertProbe<DIRECT>>(
         sycl::nd_range<1>(sycl::range<1>(16), sycl::range<1>(16)),
         props,
         [=](sycl::nd_item<1> item) {
           auto in = src[item.get_global_linear_id()];
           intel::ushort8 out;
           float y0 = 0.125f;
           float y1 = 0.25f;
           if constexpr (DIRECT) {
             direct_signed_int4_to_bf16(in, out, y0, y1);
           } else {
             cute::Xe_Reorder<
                 cute::ReorderKind::UU,
                 int4_t,
                 bfloat16_t>::reorder(in, out);
             baseline_scale_bf16(out, y0, y1);
           }
           dst[item.get_global_linear_id()] = out;
         });
   }).wait();
}

int main() {
  sycl::queue q{sycl::gpu_selector_v};
  auto* src = sycl::malloc_device<intel::uchar4>(16, q);
  auto* dst = sycl::malloc_device<intel::ushort8>(16, q);
  launch<false>(q, src, dst);
  launch<true>(q, src, dst);
  ::printf("ok\n");
  return 0;
}
