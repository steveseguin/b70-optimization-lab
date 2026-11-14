// rux6 candidate tags (included before the candidate list)
template <unsigned R_, unsigned E_, unsigned XA_, unsigned LV_, unsigned G_, unsigned W_, unsigned XP_, unsigned XW_, unsigned WP_,
          unsigned PK_ = 0>
struct VarX {
    static constexpr unsigned R = R_, E = E_, XA = XA_, LV = LV_, G = G_, W = W_, XP = XP_, XW = XW_, WP = WP_, PK = PK_;
};
template <unsigned XP_, unsigned XW_, unsigned WP_, unsigned PK_ = 0> struct VarXP {
    static constexpr unsigned XP = XP_, XW = XW_, WP = WP_, PK = PK_;
};
struct VarR6 {};
