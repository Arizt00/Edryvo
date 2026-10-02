#pragma once
#include "lantern.h"
#include <type_traits>
#include <stdexcept>
namespace lantern {
template<class T> class State {
    static_assert(std::is_trivially_copyable<T>::value,"Use fixed data fields; not strings, vectors, pointers or handles");
    uint64_t schema_;
public:
    T value{};
    explicit State(uint64_t schema,lantern_migration migrate=nullptr):schema_(schema){
        int result=lantern_restore(&value,sizeof(T),schema,migrate);
        if(result<0)throw std::runtime_error(result==-2?"Lantern: schema changed; provide a migration":"Lantern: invalid checkpoint or I/O error");
    }
    void checkpoint(){if(lantern_checkpoint(&value,sizeof(T),schema_)<0)throw std::runtime_error("Lantern: checkpoint failed");}
    bool reload(){int r=lantern_poll(&value,sizeof(T),schema_);if(r<0)throw std::runtime_error("Lantern: checkpoint failed");return r==1;}
};
}
