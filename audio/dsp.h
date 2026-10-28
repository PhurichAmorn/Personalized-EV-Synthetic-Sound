#pragma once
#include <array>
#include <cstddef>
namespace evsound {
constexpr double pi=3.1415926535897932384626433832795;
using Colours=std::array<const double*,11>;
struct ElectricState { std::array<double,7> phases{}; double motion=0; };
struct OrchestraState { std::array<double,9> phases{}; };
struct TractionState { std::array<double,4> phases{}; };
struct CycleState {
    std::array<double,5> controls{2.5,.60,140.,0.,0.};
    std::array<double,2> phases{};
    double position=0, morph_phase=0;
};
void electric(const double* hz,const double* drive,const double* richness,const Colours& controls,
              ElectricState& state,double sr,std::size_t n,double* motor,double* regen);
void orchestra(const double* hz,const double* cutoff,const double* richness,OrchestraState& state,
               double sr,std::size_t n,double* output);
void traction(const double* speed,const double* hz,const double* cutoff,const double* richness,
              TractionState& state,double sr,std::size_t n,double* output);
void traction_cycle(const double* rate,const double* hz,const double* cutoff,const double* richness,
                    const std::array<double,5>& target,CycleState& state,double sr,std::size_t n,double* output);
}
