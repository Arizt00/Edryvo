#include "lantern.hpp"
#include <iostream>
struct Data { int count; double total; };
int main() {
    lantern::State<Data> state(1);
    ++state.value.count; state.value.total+=2.5;
    state.checkpoint();
    std::cout<<"LANTERN_NATIVE "<<state.value.count<<" "<<state.value.total<<std::endl;
}
