#include "../audio/engine.h"
#include "../audio/output.h"
#include <atomic>
#include <cassert>
#include <cmath>
#include <cstdlib>
#include <new>
#include <thread>
#include <vector>
static std::atomic<bool> watch{false};
static std::atomic<unsigned> allocations{0};
void* operator new(std::size_t size){if(watch)++allocations;if(auto p=std::malloc(size?size:1))return p;throw std::bad_alloc();}
void operator delete(void* p)noexcept{std::free(p);}
void* operator new[](std::size_t n){return ::operator new(n);}
void operator delete[](void* p)noexcept{::operator delete(p);}
int main(int argc,char** argv){
    using namespace evsound;
    Random random(73);
    assert(std::abs(random.uniform(-1,1)-(-.014727621423614279))<1e-16);
    Random grains(19);assert(grains.integer(103633)==61043);
    assert(std::abs(grains.uniform(.24,.36)-.3511043213780044)<1e-16);
    Engine engine(16000);
    std::array<float,1024> audio{};
    engine.render(audio.data(),512,2);for(float x:audio)assert(x==0);
    for(const auto& theme:debug_themes()){
        engine.set_driving_parameters(80,70,.7,3,"ready",theme.second);
        allocations=0;watch=true;
        for(int i=0;i<20;++i)engine.render(audio.data(),512,2);
        watch=false;assert(allocations==0);
        bool audible=false;
        for(std::size_t i=0;i<audio.size();i+=2){assert(std::isfinite(audio[i]));assert(std::abs(audio[i])<.5);assert(audio[i]==audio[i+1]);audible|=audio[i]!=0;}
        assert(audible);
    }
    auto invalid=sound_themes().at("Comfort");invalid["electric_pulse"]=2.;
    const auto previous=engine.params;bool failed=false;
    try{engine.set_parameters(1,10,1,0,invalid);}catch(const std::invalid_argument&){failed=true;}
    assert(failed&&engine.params==previous);
    failed=false;try{engine.set_driving_parameters(-1,0,0,0,"ready",sound_themes().at("Comfort"));}catch(const std::invalid_argument&){failed=true;}assert(failed);
    // Concurrent frontend updates cannot race the native callback's state.
    std::thread updates([&]{for(int i=0;i<100;++i){engine.set_driving_parameters(i,70,.7,3,"ready",sound_themes().at("Sport"));auto c=OrderConfig();c.values["master_gain"]=.7;engine.order_synth.configure(c);}});
    for(int i=0;i<100;++i)engine.render(audio.data(),512,2);
    updates.join();
    engine.reset();assert(engine.active_grains()==0);assert(engine.order_synth.rpm==1000.);
    if(argc==2){
        Output::set_library(argv[1]);
        auto lifecycle=[&]{for(int i=0;i<10;++i){engine.start();(void)engine.opened();engine.stop();}};
        std::thread first(lifecycle),second(lifecycle);first.join();second.join();
        assert(!engine.opened());assert(engine.sample_rate==48000);
    }
}
