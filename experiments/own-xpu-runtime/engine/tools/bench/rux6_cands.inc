// rux6 candidate forms for bench_rux6.cpp: KOf specialisations + names
// VarX<R, E, XA, LV, G, W, XP, XW, WP>: RoutedUX with those parameters
// VarXP<XP, XW, WP>: RoutedUX on the pick's own (R, E, XA, LV, G, W) (Rux4Pick) plus the prefetch parameters
template <Ty TY, unsigned NB, unsigned R, unsigned E, unsigned XA, unsigned LV, unsigned G, unsigned W, unsigned XP, unsigned XW,
          unsigned WP, unsigned PK>
struct KOf<TY, NB, VarX<R, E, XA, LV, G, W, XP, XW, WP, PK>> {
    using T = RoutedUX<typename FT<TY, NB>::F, 6, R, E, XA, 0, LV, G, W, XP, XW, WP, PK>;
};
template <Ty TY, unsigned NB, unsigned XP, unsigned XW, unsigned WP, unsigned PK>
struct KOf<TY, NB, VarXP<XP, XW, WP, PK>> {
    using P4 = Rux4Pick<TY, NB>;
    using T = RoutedUX<typename FT<TY, NB>::F, 6, P4::R, P4::E, P4::XA, P4::PF, P4::LV, P4::G, P4::W, XP, XW, WP, PK>;
};
template <typename V> static void cname6(char *b, size_t n)
    requires requires { V::XP; V::R; }
{
    std::snprintf(b, n, "X R%uE%u x%u %s w%u xp%u xw%u wp%u%s", V::R, V::E, V::XA, V::G == 128 ? "g" : "G", V::W, V::XP, V::XW, V::WP,
                  V::PK == 2 ? " blk" : V::PK ? " L1" : "");
}
template <typename V> static void cname6(char *b, size_t n)
    requires(requires { V::XP; } && !requires { V::R; })
{
    std::snprintf(b, n, "pick+xp%u xw%u wp%u%s", V::XP, V::XW, V::WP, V::PK == 2 ? " blk" : V::PK ? " L1" : "");
}
// VarR6: the engine's OWN_RUX6=1 type for the format (Rux6Q where rux6_has, else rux4's RoutedIQ*SUP)
template <Ty TY, unsigned NB> struct KOf<TY, NB, VarR6> {
    using T = std::conditional_t<rux6_has<TY, NB>, Rux6Q<TY, NB>, typename FT<TY, NB>::U6>;
};
template <typename V> static void cname6(char *b, size_t n)
    requires std::is_same_v<V, VarR6>
{
    std::snprintf(b, n, "rux6 (OWN_RUX6=1)");
}
