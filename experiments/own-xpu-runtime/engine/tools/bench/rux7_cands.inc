// rux7 candidate forms for bench_rux7.cpp: KOf specialisations + names
#include "rux7_us.hpp"
template <Ty TY, unsigned NB, unsigned R, unsigned E, unsigned G, unsigned W, unsigned XP, unsigned XW, unsigned PK>
struct KOf<TY, NB, VarS<R, E, G, W, XP, XW, PK>> {
    using T = RoutedUS<typename FT<TY, NB>::F, 6, R, E, G, W, XP, XW, PK>;
};
template <typename V> static void cname6(char *b, size_t n)
    requires requires { V::XS; }
{
    std::snprintf(b, n, "S R%uE%u %s w%u xp%u xw%u%s", V::SR, V::SE, V::SG == 128 ? "g" : "G", V::SW, V::SXP, V::SXW,
                  V::SPK == 2 ? " blk" : V::SPK ? " L1" : "");
}
