// rux7 candidate tags (included before the candidate list)
// VarS<R, E, G, W, XP, XW, PK>: the x-stationary RoutedUS (sycl_v41_routed_rux7.hpp)
template <unsigned R_, unsigned E_, unsigned G_, unsigned W_, unsigned XP_ = 0, unsigned XW_ = 1, unsigned PK_ = 0> struct VarS {
    // (member names differ from VarX's so rux6's cname6 overloads do not match)
    static constexpr unsigned SR = R_, SE = E_, SG = G_, SW = W_, SXP = XP_, SXW = XW_, SPK = PK_, XS = 1;
};
// VarQ2<R, E, G, W, XP, RED, DL, WL>: layer 0's Q2_K down on RoutedQ2KG (the Q2_K section only)
template <unsigned R_, unsigned E_, unsigned G_, unsigned W_, unsigned XP_, unsigned RED_, unsigned DL_, unsigned WL_> struct VarQ2 {
    static constexpr unsigned R = R_, E = E_, G = G_, W = W_, XP = XP_, RED = RED_, DL = DL_, WL = WL_;
};
