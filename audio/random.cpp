#include "engine.h"
#include <stdexcept>
namespace evsound {
// PCG64 XSL-RR and NumPy's bounded uint32 draws preserve the reference seeds.
static std::uint64_t multiply_high(std::uint64_t a,std::uint64_t b) {
    const std::uint64_t al=static_cast<std::uint32_t>(a),ah=a>>32;
    const std::uint64_t bl=static_cast<std::uint32_t>(b),bh=b>>32;
    const std::uint64_t low=al*bl;
    const std::uint64_t middle=ah*bl+(low>>32);
    const std::uint64_t carry=al*bh+static_cast<std::uint32_t>(middle);
    return ah*bh+(middle>>32)+(carry>>32);
}
Random::Random(int seed) {
    if(seed==19){hi=0x38b480e5c3fee5ebULL;lo=0x5cc07ecf48923a08ULL;inc_hi=0x08ec6de1cfef1833ULL;inc_lo=0x16b47d7b07061ce7ULL;}
    else if(seed==73){hi=0xd9d9ef771f11fa6bULL;lo=0xca3b7660d28f7285ULL;inc_hi=0x8299a4e311c1523aULL;inc_lo=0x5b804cf48f2e1865ULL;}
    else throw std::invalid_argument("Only the reference audio RNG seeds are supported.");
}
std::uint64_t Random::next64() {
    hi=multiply_high(lo,0x4385df649fccf645ULL)+lo*0x2360ed051fc65da4ULL+hi*0x4385df649fccf645ULL;
    lo*=0x4385df649fccf645ULL;
    const auto before=lo; lo+=inc_lo;hi+=inc_hi+(lo<before);
    const std::uint64_t word=hi^lo; const unsigned rotate=hi>>58;
    return (word>>rotate)|(word<<((-rotate)&63));
}
std::uint32_t Random::next32() {
    if(has_uint32){has_uint32=false;return cached;}
    const auto word=next64();cached=static_cast<std::uint32_t>(word>>32);has_uint32=true;
    return static_cast<std::uint32_t>(word);
}
double Random::uniform(double low,double high) {return low+(high-low)*(static_cast<double>(next64()>>11)*0x1.0p-53);}
std::uint32_t Random::integer(std::uint32_t high) {
    if(!high) throw std::invalid_argument("Random upper bound must be positive.");
    const auto threshold=static_cast<std::uint32_t>(-high)%high;
    for(;;){const std::uint64_t product=static_cast<std::uint64_t>(next32())*high;
        if(static_cast<std::uint32_t>(product)>=threshold) return static_cast<std::uint32_t>(product>>32);}
}
}
