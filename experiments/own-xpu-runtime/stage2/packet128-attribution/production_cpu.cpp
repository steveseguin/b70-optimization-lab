// Compile the actual production operation in a separate TU, as in the engine.
// Shapes are runtime inputs; the fixture must not specialize a different oracle.
#include "adapter.cpp"
extern "C" void p109_production_ng(ng::Shape shape,ng::Args args){
 packet18::NgHost operation(shape);operation.run(args.p);
}
