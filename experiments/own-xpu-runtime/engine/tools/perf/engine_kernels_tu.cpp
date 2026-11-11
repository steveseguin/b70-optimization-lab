// Machine-code dumps of the engine's decode kernels without building the engine: every kernel type of the card-2
// answer-step profile (round18 g82) instantiated with the engine's launch form (backend_sycl_v41.hpp launch_rows /
// launch_sg / launch_wgl / launch: work-group size, 32-lane sub-groups, local memory). The functors are
// value-initialized and the arguments are null: this program is only COMPILED for its machine code (isa_census.py,
// predict.py); running it would launch nothing (main returns before any submit unless argc > 1000).
//   tools/perf/dump_isa.sh /home/steve/dsv41-work/perf/isa-engine82 tools/perf/engine_kernels_tu.cpp
//   (SRC_ROOT=/home/steve/dsv41-work/src82/src: the profiled build's kernel sources)
#include <sycl/sycl.hpp>
#include <cstdio>
#include <tuple>
#include <utility>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;
using A = ActF32;

// argument types of K::operator()(nd_item<1>, Args...)
template <typename M> struct Sig;
template <typename K, typename... Args> struct Sig<void (K::*)(sycl::nd_item<1>, Args...) const> {
    using T = std::tuple<std::decay_t<Args>...>;
};
template <typename Tup, size_t... I>
auto head_t(std::index_sequence<I...>) -> std::tuple<std::tuple_element_t<I, Tup>...>;
template <typename Tup> using Head = decltype(head_t<Tup>(std::make_index_sequence<std::tuple_size_v<Tup> - 1>{}));

// launch_rows<0, WG> / launch_sg / launch_wg: 32-lane sub-groups, no local memory
template <size_t WG, typename K> void rows(sycl::queue &q, size_t nwg) {
    K k{};
    typename Sig<decltype(&K::operator())>::T args{};
    q.submit([&](sycl::handler &h) {
        h.parallel_for(sycl::nd_range<1>(nwg * WG, WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            std::apply([&](auto... a) { k(it, a...); }, args);
        });
    });
}
// launch_rows<SLM, WG> / launch_wgl<SLM>: local memory passed as the last argument (LT = float or uint32_t)
template <size_t WG, size_t SLM, typename LT, typename K> void rows_slm(sycl::queue &q, size_t nwg) {
    K k{};
    Head<typename Sig<decltype(&K::operator())>::T> args{};
    q.submit([&](sycl::handler &h) {
        sycl::local_accessor<LT, 1> lt(SLM, h);
        h.parallel_for(sycl::nd_range<1>(nwg * WG, WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            std::apply([&](auto... a) { k(it, a..., &lt[0]); }, args);
        });
    });
}
// launch(): no required sub-group size (the compiler picks the SIMD width)
template <size_t WG, typename K> void plain(sycl::queue &q, size_t nwg) {
    K k{};
    typename Sig<decltype(&K::operator())>::T args{};
    q.submit([&](sycl::handler &h) {
        h.parallel_for(sycl::nd_range<1>(nwg * WG, WG), [=](sycl::nd_item<1> it) { std::apply([&](auto... a) { k(it, a...); }, args); });
    });
}

template <typename D> using DR = DenseRows<D>;
template <typename D> using DPair = RowsPair<DR<D>, DR<D>>;

int main(int argc, char **) {
    if (argc <= 1000) {
        std::puts("compile-only translation unit (machine-code dumps); nothing to run");
        return 0;
    }
    sycl::queue q;
    // dense rows (launch_rows<0>: 16 rows per work-group of 512)
    rows<512, GemvQ8P<40, A>>(q, 1);
    rows<512, GemvQ8P<72, A>>(q, 1);
    rows<512, GemvQ8P<128, A>>(q, 1);
    rows<512, GemvQ8P<160, A>>(q, 1);
    rows<512, GemvQ8P<256, A>>(q, 1);
    rows<512, GemvQ6KP<5, A>>(q, 1);
    rows<512, GemvQ6KP<16, A>>(q, 1);
    rows<512, GemvQ6KP<20, A>>(q, 1);
    rows<512, GemvQ6KP<24, A>>(q, 1);
    rows<512, GemvQ6KP<32, A>>(q, 1);
    rows<512, GemvQ5KP<9, A>>(q, 1);
    rows<512, GemvQ5KP<20, A>>(q, 1);
    rows<512, GemvH16P<160, A>>(q, 1);
    rows<512, GemvH16P<16, A>>(q, 1);
    // fused row launches (RowsP)
    rows<512, RowsP<RowsPair<RowsPair<HcFinishRows, RopeRows<A>>, DR<GemvQ8P<40, A>>>>>(q, 1);
    rows<512, RowsP<RowsPair<RowsPair<HcFinishRows, RopeRows<A>>, DR<GemvQ6KP<5, A>>>>>(q, 1);
    rows<512, RowsP<RowsPair<NoRows, DPair<GemvQ8P<160, A>>>>>(q, 1);
    rows<512, RowsP<RowsPair<NoRows, DPair<GemvQ6KP<20, A>>>>>(q, 1);
    rows<512, RowsP<RowsPair<HcDotsRows<5120, 8>, DPair<GemvQ8P<160, A>>>>>(q, 1);
    rows<64, RowsP<RowsPair<NormRows<5120, 4>, HcDotsRows<5120, 8>>>>(q, 1);
    rows<64, RowsP<RowsPair<NormRows<1280, 4>, NormRows<512, 2>>>>(q, 1);
    rows<512, RowsP<RopeRows<A>>>(q, 1);
    // router + mix finish + shared gate / up (route_with_shared: local 2 * 1024 + 6 floats)
    rows_slm<512, 2 * 1024 + 6, float, RoutePRows<RowsPair<HcFinishRows, DPair<GemvQ8P<160, A>>>>>(q, 1);
    rows_slm<512, 2 * 1024 + 6, float, RoutePRows<RowsPair<HcFinishRows, DPair<GemvQ5KP<20, A>>>>>(q, 1);
    // routed experts (launch_rows<K::TAB>, at most 128 work-groups)
    rows_slm<512, RoutedIQ2SP<20, A>::TAB, float, RoutedIQ2SP<20, A>>(q, 128);
    rows_slm<512, RoutedIQ2XXSP<20, A>::TAB, float, RoutedIQ2XXSP<20, A>>(q, 128);
    rows_slm<512, RoutedIQ1SP<20, A, true>::TAB, float, RoutedIQ1SP<20, A, true>>(q, 128);
    rows_slm<512, RoutedIQ2SP<9, A>::TAB, float, RoutedIQ2SP<9, A>>(q, 128);
    rows_slm<512, RoutedIQ3XXSP<9, A>::TAB, float, RoutedIQ3XXSP<9, A>>(q, 128);
    rows_slm<512, RoutedIQ2XSP<9, A>::TAB, float, RoutedIQ2XSP<9, A>>(q, 128);
    rows_slm<512, RoutedIQ2XXSP<9, A>::TAB, float, RoutedIQ2XXSP<9, A>>(q, 128);
    // attention (launch_sg: one sub-group per work-group; launch_wgl: SparseOutJC)
    rows<32, SparseScoreHG<512, 4>>(q, 20);
    rows<32, SparseSoftmaxPN<640>>(q, 16);
    using SC = SparseOutJC<512, 16, 128>;
    rows_slm<SC::WG, SC::SLM, uint32_t, SC>(q, 16);
    // engram gate (launch_sg 4: the profiled build's chain form)
    rows<32, EngramGateP>(q, 4);
    // element-wise launches (launch(): no required sub-group size)
    plain<64, HcPostPreP<A>>(q, 80);
    plain<64, WindowAppendP<A>>(q, 8);
    plain<64, SwigluBothS<A>>(q, 42);
    plain<32, MoeCombineA<A>>(q, 27);
    q.wait();
    return 0;
}
