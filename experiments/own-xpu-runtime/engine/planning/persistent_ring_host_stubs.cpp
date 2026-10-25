// Test-only fail-closed link closure for the empty-plan actual Engine RESET fixture.
// Every excluded model loader/arithmetic entry throws if reached. Real owner,
// retirement, CopyEngine, SnapshotFlat, reset and dispatcher code are linked.
// Generated from the retained v2 link log; names and demangled meanings are
// explicit so this cannot become a substitute arithmetic implementation.
#ifndef OWN_RT_HOST_ONLY
#error "RESET fixture stubs must never enter a device build"
#endif
#include <stdexcept>
// integrated::dense(ownrt::Device&, iq3::kopt2::Matrix const&, unsigned int)
extern "C" [[noreturn]] void reset_unreachable_0() asm("_ZN10integrated5denseERN5ownrt6DeviceERKN3iq35kopt26MatrixEj");
extern "C" [[noreturn]] void reset_unreachable_0() {throw std::logic_error("reset fixture reached excluded entry: integrated::dense(ownrt::Device&, iq3::kopt2::Matrix const&, unsigned int)");}
// integrated::experts(ownrt::Device&, std::vector<iq3::kopt2::Matrix, std::allocator<iq3::kopt2::Matrix> > const&, bool)
extern "C" [[noreturn]] void reset_unreachable_1() asm("_ZN10integrated7expertsERN5ownrt6DeviceERKSt6vectorIN3iq35kopt26MatrixESaIS6_EEb");
extern "C" [[noreturn]] void reset_unreachable_1() {throw std::logic_error("reset fixture reached excluded entry: integrated::experts(ownrt::Device&, std::vector<iq3::kopt2::Matrix, std::allocator<iq3::kopt2::Matrix> > const&, bool)");}
// integrated::mixture(ownrt::Device&, unsigned long, unsigned long, unsigned long, unsigned int)
extern "C" [[noreturn]] void reset_unreachable_2() asm("_ZN10integrated7mixtureERN5ownrt6DeviceEmmmj");
extern "C" [[noreturn]] void reset_unreachable_2() {throw std::logic_error("reset fixture reached excluded entry: integrated::mixture(ownrt::Device&, unsigned long, unsigned long, unsigned long, unsigned int)");}
// p30integrated::small(ownrt::Device&, std::basic_string_view<char, std::char_traits<char> >, std::span<iq3::kopt2::Matrix const, 18446744073709551615ul>, std::span<unsigned int const, 18446744073709551615ul>)
extern "C" [[noreturn]] void reset_unreachable_3() asm("_ZN13p30integrated5smallERN5ownrt6DeviceESt17basic_string_viewIcSt11char_traitsIcEESt4spanIKN3iq35kopt26MatrixELm18446744073709551615EES7_IKjLm18446744073709551615EE");
extern "C" [[noreturn]] void reset_unreachable_3() {throw std::logic_error("reset fixture reached excluded entry: p30integrated::small(ownrt::Device&, std::basic_string_view<char, std::char_traits<char> >, std::span<iq3::kopt2::Matrix const, 18446744073709551615ul>, std::span<unsigned int const, 18446744073709551615ul>)");}
// iq3::step_operator(ownrt::Device&, integrated::Spec const&, std::span<unsigned long const, 18446744073709551615ul>)
extern "C" [[noreturn]] void reset_unreachable_4() asm("_ZN3iq313step_operatorERN5ownrt6DeviceERKN10integrated4SpecESt4spanIKmLm18446744073709551615EE");
extern "C" [[noreturn]] void reset_unreachable_4() {throw std::logic_error("reset fixture reached excluded entry: iq3::step_operator(ownrt::Device&, integrated::Spec const&, std::span<unsigned long const, 18446744073709551615ul>)");}
// iq3::kopt::route_mask(ownrt::Device&, unsigned long, unsigned long, unsigned int, unsigned int, bool)
extern "C" [[noreturn]] void reset_unreachable_5() asm("_ZN3iq34kopt10route_maskERN5ownrt6DeviceEmmjjb");
extern "C" [[noreturn]] void reset_unreachable_5() {throw std::logic_error("reset fixture reached excluded entry: iq3::kopt::route_mask(ownrt::Device&, unsigned long, unsigned long, unsigned int, unsigned int, bool)");}
// iq3::kopt::slot_select(ownrt::Device&, unsigned long, unsigned long, unsigned long, unsigned int, unsigned int, unsigned int, bool)
extern "C" [[noreturn]] void reset_unreachable_6() asm("_ZN3iq34kopt11slot_selectERN5ownrt6DeviceEmmmjjjb");
extern "C" [[noreturn]] void reset_unreachable_6() {throw std::logic_error("reset fixture reached excluded entry: iq3::kopt::slot_select(ownrt::Device&, unsigned long, unsigned long, unsigned long, unsigned int, unsigned int, unsigned int, bool)");}
// iq3::Model::Model(std::vector<std::filesystem::__cxx11::path, std::allocator<std::filesystem::__cxx11::path> > const&, std::vector<iq3::Planned, std::allocator<iq3::Planned> >)
extern "C" [[noreturn]] void reset_unreachable_7() asm("_ZN3iq35ModelC1ERKSt6vectorINSt10filesystem7__cxx114pathESaIS4_EES1_INS_7PlannedESaIS9_EE");
extern "C" [[noreturn]] void reset_unreachable_7() {throw std::logic_error("reset fixture reached excluded entry: iq3::Model::Model(std::vector<std::filesystem::__cxx11::path, std::allocator<std::filesystem::__cxx11::path> > const&, std::vector<iq3::Planned, std::allocator<iq3::Planned> >)");}
// iq3::Model::Model(std::vector<std::filesystem::__cxx11::path, std::allocator<std::filesystem::__cxx11::path> > const&, std::vector<iq3::Planned, std::allocator<iq3::Planned> >, iq3::Admission const&)
extern "C" [[noreturn]] void reset_unreachable_8() asm("_ZN3iq35ModelC1ERKSt6vectorINSt10filesystem7__cxx114pathESaIS4_EES1_INS_7PlannedESaIS9_EERKNS_9AdmissionE");
extern "C" [[noreturn]] void reset_unreachable_8() {throw std::logic_error("reset fixture reached excluded entry: iq3::Model::Model(std::vector<std::filesystem::__cxx11::path, std::allocator<std::filesystem::__cxx11::path> > const&, std::vector<iq3::Planned, std::allocator<iq3::Planned> >, iq3::Admission const&)");}
// iq3::Slice::~Slice()
extern "C" [[noreturn]] void reset_unreachable_9() asm("_ZN3iq35SliceD1Ev");
extern "C" [[noreturn]] void reset_unreachable_9() {throw std::logic_error("reset fixture reached excluded entry: iq3::Slice::~Slice()");}
// iq3::kopt4::epilogue_f32(ownrt::Device&, unsigned long, unsigned long, unsigned long, unsigned int)
extern "C" [[noreturn]] void reset_unreachable_10() asm("_ZN3iq35kopt412epilogue_f32ERN5ownrt6DeviceEmmmj");
extern "C" [[noreturn]] void reset_unreachable_10() {throw std::logic_error("reset fixture reached excluded entry: iq3::kopt4::epilogue_f32(ownrt::Device&, unsigned long, unsigned long, unsigned long, unsigned int)");}
// iq3::read_plan(std::filesystem::__cxx11::path const&)
extern "C" [[noreturn]] void reset_unreachable_11() asm("_ZN3iq39read_planERKNSt10filesystem7__cxx114pathE");
extern "C" [[noreturn]] void reset_unreachable_11() {throw std::logic_error("reset fixture reached excluded entry: iq3::read_plan(std::filesystem::__cxx11::path const&)");}
// p28::submit(ownrt::Device&, std::vector<iq3::kopt2::Matrix, std::allocator<iq3::kopt2::Matrix> > const&, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&, bool, unsigned int)
extern "C" [[noreturn]] void reset_unreachable_12() asm("_ZN3p286submitERN5ownrt6DeviceERKSt6vectorIN3iq35kopt26MatrixESaIS6_EERKNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEEEbj");
extern "C" [[noreturn]] void reset_unreachable_12() {throw std::logic_error("reset fixture reached excluded entry: p28::submit(ownrt::Device&, std::vector<iq3::kopt2::Matrix, std::allocator<iq3::kopt2::Matrix> > const&, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&, bool, unsigned int)");}
// p29::submit(ownrt::Device&, std::vector<iq3::kopt2::Matrix, std::allocator<iq3::kopt2::Matrix> > const&, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&, bool, unsigned int)
extern "C" [[noreturn]] void reset_unreachable_13() asm("_ZN3p296submitERN5ownrt6DeviceERKSt6vectorIN3iq35kopt26MatrixESaIS6_EERKNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEEEbj");
extern "C" [[noreturn]] void reset_unreachable_13() {throw std::logic_error("reset fixture reached excluded entry: p29::submit(ownrt::Device&, std::vector<iq3::kopt2::Matrix, std::allocator<iq3::kopt2::Matrix> > const&, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&, bool, unsigned int)");}
// p33::submit(ownrt::Device&, std::vector<iq3::kopt2::Matrix, std::allocator<iq3::kopt2::Matrix> > const&, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&, bool, unsigned int)
extern "C" [[noreturn]] void reset_unreachable_14() asm("_ZN3p336submitERN5ownrt6DeviceERKSt6vectorIN3iq35kopt26MatrixESaIS6_EERKNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEEEbj");
extern "C" [[noreturn]] void reset_unreachable_14() {throw std::logic_error("reset fixture reached excluded entry: p33::submit(ownrt::Device&, std::vector<iq3::kopt2::Matrix, std::allocator<iq3::kopt2::Matrix> > const&, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&, bool, unsigned int)");}
// p39::submit(ownrt::Device&, std::vector<iq3::kopt2::Matrix, std::allocator<iq3::kopt2::Matrix> > const&, p39::Kind, p39::Bindings const&)
extern "C" [[noreturn]] void reset_unreachable_15() asm("_ZN3p396submitERN5ownrt6DeviceERKSt6vectorIN3iq35kopt26MatrixESaIS6_EENS_4KindERKNS_8BindingsE");
extern "C" [[noreturn]] void reset_unreachable_15() {throw std::logic_error("reset fixture reached excluded entry: p39::submit(ownrt::Device&, std::vector<iq3::kopt2::Matrix, std::allocator<iq3::kopt2::Matrix> > const&, p39::Kind, p39::Bindings const&)");}
// p60::submit(ownrt::Device&, std::array<unsigned long, 16ul> const&, int, unsigned int, bool, bool, bool, bool)
extern "C" [[noreturn]] void reset_unreachable_16() asm("_ZN3p606submitERN5ownrt6DeviceERKSt5arrayImLm16EEijbbbb");
extern "C" [[noreturn]] void reset_unreachable_16() {throw std::logic_error("reset fixture reached excluded entry: p60::submit(ownrt::Device&, std::array<unsigned long, 16ul> const&, int, unsigned int, bool, bool, bool, bool)");}
// p74::submit(ownrt::Device&, iq3::kopt2::Matrix const&, unsigned int, p39::Kind, p39::Bindings const&)
extern "C" [[noreturn]] void reset_unreachable_17() asm("_ZN3p746submitERN5ownrt6DeviceERKN3iq35kopt26MatrixEjN3p394KindERKNS8_8BindingsE");
extern "C" [[noreturn]] void reset_unreachable_17() {throw std::logic_error("reset fixture reached excluded entry: p74::submit(ownrt::Device&, iq3::kopt2::Matrix const&, unsigned int, p39::Kind, p39::Bindings const&)");}
// p93::submit(ownrt::Device&, iq3::kopt2::Matrix const&, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&)
extern "C" [[noreturn]] void reset_unreachable_18() asm("_ZN3p936submitERN5ownrt6DeviceERKN3iq35kopt26MatrixERKNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEEE");
extern "C" [[noreturn]] void reset_unreachable_18() {throw std::logic_error("reset fixture reached excluded entry: p93::submit(ownrt::Device&, iq3::kopt2::Matrix const&, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&)");}
// p183::small(ownrt::Device&, std::basic_string_view<char, std::char_traits<char> >, std::span<iq3::kopt2::Matrix const, 18446744073709551615ul>, std::span<unsigned int const, 18446744073709551615ul>)
extern "C" [[noreturn]] void reset_unreachable_19() asm("_ZN4p1835smallERN5ownrt6DeviceESt17basic_string_viewIcSt11char_traitsIcEESt4spanIKN3iq35kopt26MatrixELm18446744073709551615EES7_IKjLm18446744073709551615EE");
extern "C" [[noreturn]] void reset_unreachable_19() {throw std::logic_error("reset fixture reached excluded entry: p183::small(ownrt::Device&, std::basic_string_view<char, std::char_traits<char> >, std::span<iq3::kopt2::Matrix const, 18446744073709551615ul>, std::span<unsigned int const, 18446744073709551615ul>)");}
// p183::segment(ownrt::Device&, std::vector<iq3::kopt2::Matrix, std::allocator<iq3::kopt2::Matrix> > const&, bool, unsigned int)
extern "C" [[noreturn]] void reset_unreachable_20() asm("_ZN4p1837segmentERN5ownrt6DeviceERKSt6vectorIN3iq35kopt26MatrixESaIS6_EEbj");
extern "C" [[noreturn]] void reset_unreachable_20() {throw std::logic_error("reset fixture reached excluded entry: p183::segment(ownrt::Device&, std::vector<iq3::kopt2::Matrix, std::allocator<iq3::kopt2::Matrix> > const&, bool, unsigned int)");}
// p183::attention(ownrt::Device&, iq3::kopt2::Matrix const&, p39::Bindings const&)
extern "C" [[noreturn]] void reset_unreachable_21() asm("_ZN4p1839attentionERN5ownrt6DeviceERKN3iq35kopt26MatrixERKN3p398BindingsE");
extern "C" [[noreturn]] void reset_unreachable_21() {throw std::logic_error("reset fixture reached excluded entry: p183::attention(ownrt::Device&, iq3::kopt2::Matrix const&, p39::Bindings const&)");}
// p49c::dense_submit(ownrt::Device&, iq3::kopt2::Matrix const&, p39::Kind, p39::Bindings const&)
extern "C" [[noreturn]] void reset_unreachable_22() asm("_ZN4p49c12dense_submitERN5ownrt6DeviceERKN3iq35kopt26MatrixEN3p394KindERKNS8_8BindingsE");
extern "C" [[noreturn]] void reset_unreachable_22() {throw std::logic_error("reset fixture reached excluded entry: p49c::dense_submit(ownrt::Device&, iq3::kopt2::Matrix const&, p39::Kind, p39::Bindings const&)");}
// p49d::small(ownrt::Device&, std::basic_string_view<char, std::char_traits<char> >, std::span<iq3::kopt2::Matrix const, 18446744073709551615ul>, std::span<unsigned int const, 18446744073709551615ul>)
extern "C" [[noreturn]] void reset_unreachable_23() asm("_ZN4p49d5smallERN5ownrt6DeviceESt17basic_string_viewIcSt11char_traitsIcEESt4spanIKN3iq35kopt26MatrixELm18446744073709551615EES7_IKjLm18446744073709551615EE");
extern "C" [[noreturn]] void reset_unreachable_23() {throw std::logic_error("reset fixture reached excluded entry: p49d::small(ownrt::Device&, std::basic_string_view<char, std::char_traits<char> >, std::span<iq3::kopt2::Matrix const, 18446744073709551615ul>, std::span<unsigned int const, 18446744073709551615ul>)");}
// p49d::expert(ownrt::Device&, std::vector<iq3::kopt2::Matrix, std::allocator<iq3::kopt2::Matrix> > const&, p39::Kind, p39::Bindings const&, std::basic_string_view<char, std::char_traits<char> >, std::basic_string_view<char, std::char_traits<char> >)
extern "C" [[noreturn]] void reset_unreachable_24() asm("_ZN4p49d6expertERN5ownrt6DeviceERKSt6vectorIN3iq35kopt26MatrixESaIS6_EEN3p394KindERKNSB_8BindingsESt17basic_string_viewIcSt11char_traitsIcEESJ_");
extern "C" [[noreturn]] void reset_unreachable_24() {throw std::logic_error("reset fixture reached excluded entry: p49d::expert(ownrt::Device&, std::vector<iq3::kopt2::Matrix, std::allocator<iq3::kopt2::Matrix> > const&, p39::Kind, p39::Bindings const&, std::basic_string_view<char, std::char_traits<char> >, std::basic_string_view<char, std::char_traits<char> >)");}
// p49d::Selection::load(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&)
extern "C" [[noreturn]] void reset_unreachable_25() asm("_ZN4p49d9Selection4loadERKNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEEES8_");
extern "C" [[noreturn]] void reset_unreachable_25() {throw std::logic_error("reset fixture reached excluded entry: p49d::Selection::load(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&)");}
// mtp36::elementwise(ownrt::Device&, integrated::Spec const&, std::span<unsigned long const, 18446744073709551615ul>)
extern "C" [[noreturn]] void reset_unreachable_26() asm("_ZN5mtp3611elementwiseERN5ownrt6DeviceERKN10integrated4SpecESt4spanIKmLm18446744073709551615EE");
extern "C" [[noreturn]] void reset_unreachable_26() {throw std::logic_error("reset fixture reached excluded entry: mtp36::elementwise(ownrt::Device&, integrated::Spec const&, std::span<unsigned long const, 18446744073709551615ul>)");}
// mtp36::norm_hidden(ownrt::Device&, unsigned long, unsigned long, unsigned long, unsigned long, unsigned int)
extern "C" [[noreturn]] void reset_unreachable_27() asm("_ZN5mtp3611norm_hiddenERN5ownrt6DeviceEmmmmj");
extern "C" [[noreturn]] void reset_unreachable_27() {throw std::logic_error("reset fixture reached excluded entry: mtp36::norm_hidden(ownrt::Device&, unsigned long, unsigned long, unsigned long, unsigned long, unsigned int)");}
// mtp36::merge(ownrt::Device&, unsigned long, unsigned long, unsigned long, unsigned int)
extern "C" [[noreturn]] void reset_unreachable_28() asm("_ZN5mtp365mergeERN5ownrt6DeviceEmmmj");
extern "C" [[noreturn]] void reset_unreachable_28() {throw std::logic_error("reset fixture reached excluded entry: mtp36::merge(ownrt::Device&, unsigned long, unsigned long, unsigned long, unsigned int)");}
// mtp36::linear(ownrt::Device&, mtp36::Linear const&)
extern "C" [[noreturn]] void reset_unreachable_29() asm("_ZN5mtp366linearERN5ownrt6DeviceERKNS_6LinearE");
extern "C" [[noreturn]] void reset_unreachable_29() {throw std::logic_error("reset fixture reached excluded entry: mtp36::linear(ownrt::Device&, mtp36::Linear const&)");}
// packet18::submit_parallel(ownrt::Device&, integrated::Spec const&, std::span<unsigned long const, 18446744073709551615ul>, unsigned long, unsigned long, unsigned long, std::span<unsigned long const, 18446744073709551615ul>)
extern "C" [[noreturn]] void reset_unreachable_30() asm("_ZN8packet1815submit_parallelERN5ownrt6DeviceERKN10integrated4SpecESt4spanIKmLm18446744073709551615EEmmmS9_");
extern "C" [[noreturn]] void reset_unreachable_30() {throw std::logic_error("reset fixture reached excluded entry: packet18::submit_parallel(ownrt::Device&, integrated::Spec const&, std::span<unsigned long const, 18446744073709551615ul>, unsigned long, unsigned long, unsigned long, std::span<unsigned long const, 18446744073709551615ul>)");}
// packet26::p25bridge::prepare_input(ownrt::Device&, unsigned long, unsigned long, unsigned long)
extern "C" [[noreturn]] void reset_unreachable_31() asm("_ZN8packet269p25bridge13prepare_inputERN5ownrt6DeviceEmmm");
extern "C" [[noreturn]] void reset_unreachable_31() {throw std::logic_error("reset fixture reached excluded entry: packet26::p25bridge::prepare_input(ownrt::Device&, unsigned long, unsigned long, unsigned long)");}
// packet26::p25bridge::submit(ownrt::Device&, std::vector<iq3::kopt2::Matrix, std::allocator<iq3::kopt2::Matrix> > const&, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&, bool, unsigned int, unsigned long)
extern "C" [[noreturn]] void reset_unreachable_32() asm("_ZN8packet269p25bridge6submitERN5ownrt6DeviceERKSt6vectorIN3iq35kopt26MatrixESaIS7_EERKNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEEEbjm");
extern "C" [[noreturn]] void reset_unreachable_32() {throw std::logic_error("reset fixture reached excluded entry: packet26::p25bridge::submit(ownrt::Device&, std::vector<iq3::kopt2::Matrix, std::allocator<iq3::kopt2::Matrix> > const&, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&, bool, unsigned int, unsigned long)");}
// packet27::small::shapes(std::basic_string_view<char, std::char_traits<char> >)
extern "C" [[noreturn]] void reset_unreachable_33() asm("_ZN8packet275small6shapesESt17basic_string_viewIcSt11char_traitsIcEE");
extern "C" [[noreturn]] void reset_unreachable_33() {throw std::logic_error("reset fixture reached excluded entry: packet27::small::shapes(std::basic_string_view<char, std::char_traits<char> >)");}
// packet27::small::submit(ownrt::Device&, std::basic_string_view<char, std::char_traits<char> >, std::span<iq3::kopt2::Matrix const, 18446744073709551615ul>, std::span<unsigned int const, 18446744073709551615ul>)
extern "C" [[noreturn]] void reset_unreachable_34() asm("_ZN8packet275small6submitERN5ownrt6DeviceESt17basic_string_viewIcSt11char_traitsIcEESt4spanIKN3iq35kopt26MatrixELm18446744073709551615EES8_IKjLm18446744073709551615EE");
extern "C" [[noreturn]] void reset_unreachable_34() {throw std::logic_error("reset fixture reached excluded entry: packet27::small::submit(ownrt::Device&, std::basic_string_view<char, std::char_traits<char> >, std::span<iq3::kopt2::Matrix const, 18446744073709551615ul>, std::span<unsigned int const, 18446744073709551615ul>)");}
// iq3::Meta::integer() const
extern "C" [[noreturn]] void reset_unreachable_35() asm("_ZNK3iq34Meta7integerEv");
extern "C" [[noreturn]] void reset_unreachable_35() {throw std::logic_error("reset fixture reached excluded entry: iq3::Meta::integer() const");}
// iq3::Model::slice(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&, unsigned long, unsigned long) const
extern "C" [[noreturn]] void reset_unreachable_36() asm("_ZNK3iq35Model5sliceERKNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEEEmm");
extern "C" [[noreturn]] void reset_unreachable_36() {throw std::logic_error("reset fixture reached excluded entry: iq3::Model::slice(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&, unsigned long, unsigned long) const");}
// p49d::Selection::site(integrated::Spec const&) const
extern "C" [[noreturn]] void reset_unreachable_37() asm("_ZNK4p49d9Selection4siteERKN10integrated4SpecE");
extern "C" [[noreturn]] void reset_unreachable_37() {throw std::logic_error("reset fixture reached excluded entry: p49d::Selection::site(integrated::Spec const&) const");}
