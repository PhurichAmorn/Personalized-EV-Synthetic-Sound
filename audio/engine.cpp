#include "engine.h"
#include "output.h"
#include <algorithm>
#include <cmath>
#include <stdexcept>
namespace evsound {
static double clamp(double value){return std::clamp(value,0.,1.);}
static double value(const Profile& p,const char* key,double fallback){auto found=p.find(key);return found==p.end()?fallback:found->second;}
static void finite(std::initializer_list<double> values){for(double v:values)if(!std::isfinite(v))throw std::invalid_argument("Sound inputs must be finite.");}
static double ramp(double start,double target,std::size_t index,double seconds,int sr){return target+(start-target)*std::exp(-(index+1.)/(seconds*sr));}
Engine::Engine(int rate,OrderConfig config):sample_rate(rate),order_synth(rate,std::move(config)),output(std::make_unique<Output>()) {make_source();prepare(512);reset();}
Engine::~Engine(){try{output->stop();}catch(...){}}
void Engine::make_source(){
    source.resize(static_cast<std::size_t>(sample_rate)*6);
    const std::size_t n=source.size()/2;
    for(std::size_t i=0;i<n;++i){const double t=static_cast<double>(i)/sample_rate;
        source[i]=.38*std::sin(2*pi*96*t)+.16*std::sin(2*pi*144*t+.4)+.08*std::sin(2*pi*192.2*t);
        source[n+i]=.08*std::sin(2*pi*288*t+.7)+.04*std::sin(2*pi*384.3*t);
    }
}
void Engine::prepare(std::size_t frames){std::lock_guard<std::recursive_mutex> guard(mutex);if(frames>capacity){for(auto& buffer:work)buffer.resize(frames);capacity=frames;}}
void Engine::reset(){
    std::lock_guard<std::recursive_mutex> guard(mutex);
    order_synth.reset();order_mix=0;order_active=false;order_sleeping=false;driving_controls.reset();
    intent=accel_fast=accel_baseline=0;operating_state="off";startup_sample=-1;
    playback_gain=playback_target=1.;params={42.,0.,0.,.34,.22,0.};phase=bass_phase=regen_phase=0.;
    hz=42.;richness=.22;drive_level=regen_level=output_gain=electric_mix=0.;electric_hz=electric_hz_target=470.;
    electric_state={};orchestra_state={};traction_state={};cycle_state={};cycle_target={2.5,.60,140.,0.,0.};
    sound_speed=sound_speed_target=0.;response=response_target={1.,0.,0.,0.};response_timings={.10,.09,.16,.24,.30};
    electric_colour=electric_colour_target={.14,900.,.01,1.,.45,0.,0.,0.,0.,0.,0.};
    debug_enabled=false;debug_output.fill(0.);grain_count=0;grain_clock=0;render_counts.fill(0);
}
double Engine::fundamental_for_rpm(double rpm,double ceiling,double base){return base+180.*clamp(rpm/ceiling);}
void Engine::set_parameters(double rpm,double ceiling,double power,double regen_power,const Profile& p,double throttle,
                            std::optional<double> motor_load,std::optional<double> regen_load,double acceleration){
    std::lock_guard<std::recursive_mutex> guard(mutex);
    const double base=p.at("base_hz"),gain=p.at("gain"),rich=p.at("richness");
    const double electric=value(p,"electric_mix",0.),scale=value(p,"electric_pitch_scale",5.),offset=value(p,"electric_pitch_offset",120.);
    const double exponent=value(p,"electric_load_exponent",1.);
    finite({rpm,ceiling,power,regen_power,throttle,acceleration,base,gain,rich,electric,scale,offset,value(p,"electric_start_hz",0.),exponent});
    if(ceiling<=0||scale<=0||offset<0||value(p,"electric_start_hz",0.)<0||exponent<.7||exponent>1.3)throw std::invalid_argument("Invalid sound pitch or load response.");
    if(motor_load)finite({*motor_load});if(regen_load)finite({*regen_load});
    const double seconds=value(p,"traction_cycle_s",0.),cycle_mix=value(p,"traction_cycle_mix",seconds>0?1.:0.);
    const double crossfade=value(p,"traction_crossfade_s",.60),sweep=value(p,"traction_sweep_hz",140.);
    const double morph=value(p,"traction_morph_mix",0.),stage=value(p,"traction_stage_colour",0.);
    finite({seconds,cycle_mix,crossfade,sweep,morph,stage});
    if((seconds!=0&&(seconds<1||seconds>10))||cycle_mix<0||cycle_mix>1||crossfade<.10||crossfade>(seconds?std::min(2.,seconds/2):2.)||sweep<20||sweep>200||morph<0||morph>1||stage<0||stage>1)throw std::invalid_argument("Traction cycle timing is outside its bounds.");
    std::array<double,4> next_response={value(p,"drive_cruise_gain",1.),value(p,"acceleration_richness",0.),value(p,"traction_mix",0.),cycle_mix};
    const std::array<double,4> limits={1.,.30,1.,1.};
    for(std::size_t i=0;i<4;++i)if(!std::isfinite(next_response[i])||next_response[i]<0||next_response[i]>limits[i])throw std::invalid_argument("Sound response is outside its bounds.");
    std::array<double,5> timings={value(p,"electric_pitch_smoothing_s",.10),value(p,"drive_attack_s",.09),value(p,"drive_release_s",.16),value(p,"regen_attack_s",.24),value(p,"regen_release_s",.30)};
    for(double t:timings)if(!std::isfinite(t)||t<.02||t>2.)throw std::invalid_argument("Sound timings are outside their bounds.");
    std::array<double,11> colours={value(p,"electric_depth",.14),value(p,"electric_cutoff",900.),value(p,"electric_detune",.01),value(p,"electric_effort",1.),value(p,"electric_regen_gain",.45),value(p,"electric_growl",0.),value(p,"electric_regen_richness",0.),value(p,"orchestral_mix",0.),value(p,"electric_whirl",0.),value(p,"electric_pulse",0.),value(p,"electric_shimmer",0.)};
    const std::array<double,11> colour_limits={.3,2000.,.03,2.,1.,1.,1.,1.,1.,1.,1.};
    for(std::size_t i=0;i<11;++i)if(!std::isfinite(colours[i])||colours[i]<0||colours[i]>colour_limits[i]||(i==1&&colours[i]<200))throw std::invalid_argument("Electric sound controls are outside their bounds.");
    response_target=next_response;response_timings=timings;electric_colour_target=colours;
    if(seconds)cycle_target={seconds,crossfade,sweep,morph,stage};
    driving_controls.reset();order_active=value(p,"order_synthesis",0.)!=0.;
    if(order_active)order_synth.set_parameters(1000+5000*clamp(rpm/ceiling),throttle*100,rpm>0||(motor_load?*motor_load:throttle)>0);
    double drive=motor_load?.72*clamp(*motor_load)+.28*clamp(power):std::max(power,.18*throttle);
    drive=std::pow(clamp(drive),exponent);
    const double regen=regen_load?.80*clamp(*regen_load)+.20*clamp(regen_power):regen_power;
    electric_hz_target=value(p,"electric_start_hz",offset+scale*base)+scale*180.*clamp(rpm/ceiling);
    params={fundamental_for_rpm(rpm,ceiling,base),clamp(drive),clamp(regen),clamp(gain),clamp(rich),clamp(electric)};
}
void Engine::set_driving_parameters(double speed,double pedal_percent,double load,double acceleration,const std::string& state,const Profile& profile,double volume,bool sound_enabled){
    std::lock_guard<std::recursive_mutex> guard(mutex);
    finite({speed,pedal_percent,load,acceleration,volume});
    if(speed<0||(state!="off"&&state!="starting"&&state!="ready"))throw std::invalid_argument("Invalid driving sound state or speed.");
    const double pedal=clamp(pedal_percent/100.),drive=clamp(load),regen=clamp(-load);
    std::lock_guard<std::recursive_mutex> synth_guard(order_synth.mutex);
    const double motion=order_synth.pitch_progression(speed);
    const double urgency=clamp(acceleration/order_synth.config.get("acceleration_reference_m_s2"));
    const bool active=sound_enabled&&state=="ready";
    set_parameters(motion*6000,6000,active?drive:0.,active?regen:0.,profile,active?pedal:0.,active?drive:0.,active?regen:0.,0.);
    driving_controls=std::array<double,2>{active?pedal:0.,active?urgency:0.};sound_speed_target=speed;
    if(order_active)order_synth.set_driving_controls(1000+5000*motion,pedal,active?drive:0.,active?regen:0.,active?urgency:0.,active&&(speed>.1||drive>0));
    if(state=="starting"&&operating_state!="starting")startup_sample=0;
    if(state=="off")startup_sample=-1;
    operating_state=state;playback_target=sound_enabled&&state!="off"?clamp(volume):0.;
}
void Engine::set_order_parameters(double rpm,double pedal,bool enabled){std::lock_guard<std::recursive_mutex> guard(mutex);order_synth.set_parameters(rpm,pedal,enabled);order_active=true;}
void Engine::legacy(const double* frequencies,const double* drive,const double* richness,std::size_t n,double* motor,double* regen){
    const std::size_t source_size=source.size()/2;
    while(grain_clock<static_cast<int>(n)){
        if(grain_count==grains.size())throw std::runtime_error("Native grain pool exhausted.");
        const double position=random.integer(static_cast<std::uint32_t>(source_size-static_cast<int>(.65*sample_rate)-1));
        const int duration=static_cast<int>(random.uniform(.24,.36)*sample_rate);
        const int gap=std::max(1,static_cast<int>(random.uniform(.064,.080)*sample_rate));
        grains[grain_count++]={position,-grain_clock,duration};grain_clock+=gap;
    }
    grain_clock-=static_cast<int>(n);
    auto& body=work[34];auto& shimmer=work[35];auto& weight=work[36];
    std::fill_n(body.data(),n,0.);std::fill_n(shimmer.data(),n,0.);std::fill_n(weight.data(),n,0.);
    std::size_t active=0;
    for(std::size_t k=0;k<grain_count;++k){
        auto grain=grains[k];
        for(std::size_t j=0;j<n;++j){int age=grain.age+static_cast<int>(j);
            if(age>=0&&age<grain.duration){const auto lower=static_cast<std::size_t>(std::floor(grain.position));const double fraction=grain.position-lower;
                const double envelope=std::pow(std::sin(pi*age/grain.duration),2);const auto a=lower%source_size,b=(a+1)%source_size;
                body[j]+=(source[a]*(1-fraction)+source[b]*fraction)*envelope;
                shimmer[j]+=(source[source_size+a]*(1-fraction)+source[source_size+b]*fraction)*envelope;
                weight[j]+=envelope;grain.position+=.80+.40*clamp((frequencies[j]-42)/180.);
            }
        }
        grain.age+=static_cast<int>(n);if(grain.age<grain.duration)grains[active++]=grain;
    }
    grain_count=active;
    for(std::size_t j=0;j<n;++j){const double f=frequencies[j],d=drive[j],q=richness[j];
        phase+=2*pi*f/sample_rate;bass_phase+=2*pi*f*.5/sample_rate;regen_phase+=2*pi*f*.85/sample_rate;
        const double divisor=std::max(weight[j],1.);
        motor[j]=.22*std::sin(bass_phase)+.42*std::sin(phase)+(.09+.12*q*d)*std::sin(2*phase)+(.025+.06*q*d)*std::sin(3*phase)+.40*body[j]/divisor+(.15+.25*d)*shimmer[j]/divisor;
        regen[j]=.30*std::sin(regen_phase)+.045*std::sin(2*regen_phase)+.30*body[j]/divisor+.10*shimmer[j]/divisor;
    }
    phase=std::fmod(phase,2*pi);bass_phase=std::fmod(bass_phase,2*pi);regen_phase=std::fmod(regen_phase,2*pi);
}
void Engine::render_cycle(const double* rate,const double* h,const double* cutoff,const double* rich,std::size_t frames,double* out){std::lock_guard<std::recursive_mutex> guard(mutex);traction_cycle(rate,h,cutoff,rich,cycle_target,cycle_state,sample_rate,frames,out);}
void Engine::render(float* out,std::size_t frames,int channels){
    if(!frames)return;
    if(!out||channels<1||channels>2)throw std::invalid_argument("Invalid output buffer/channels.");
    std::lock_guard<std::recursive_mutex> guard(mutex);
    std::lock_guard<std::recursive_mutex> synth_guard(order_synth.mutex);
    prepare(frames);
    // Grains are block-scheduled in the reference; keep the bounded pool safe for long offline buffers.
    if(frames>static_cast<std::size_t>(sample_rate)*2){
        const std::size_t chunk=512;
        for(std::size_t offset=0;offset<frames;offset+=chunk)render(out+offset*channels,std::min(chunk,frames-offset),channels);
        return;
    }
    auto smooth=[&](int k,double& state,double target,double seconds,bool snap=false){double start=state;auto& b=work[k];
        for(std::size_t j=0;j<frames;++j){b[j]=ramp(start,target,j,seconds,sample_rate);if(snap&&std::abs(b[j]-target)<1e-5)b[j]=target;}state=b[frames-1];};
    smooth(0,hz,params[0],.12);smooth(1,drive_level,params[1],params[1]>drive_level?response_timings[1]:response_timings[2]);
    smooth(2,regen_level,params[2],params[2]>regen_level?response_timings[3]:response_timings[4]);
    smooth(3,richness,params[4],params[4]>richness?.10:.22);smooth(4,electric_mix,params[5],.30,true);
    smooth(5,output_gain,params[3],.05);smooth(6,order_mix,order_active?1.:0.,.30,true);
    smooth(7,electric_hz,electric_hz_target,response_timings[0]);smooth(8,sound_speed,sound_speed_target,.25);smooth(9,playback_gain,playback_target,.05);
    for(int i=0;i<4;++i)smooth(15+i,response[i],response_target[i],.25);
    std::fill_n(work[10].data(),frames,1.);std::fill_n(work[11].data(),frames,0.);
    if(driving_controls){const auto& c=order_synth.config;
        smooth(12,intent,std::pow((*driving_controls)[0],c.get("throttle_gamma")),c.get("throttle_smoothing_s"));
        smooth(13,accel_fast,(*driving_controls)[1],c.get("acceleration_smoothing_s"));smooth(14,accel_baseline,(*driving_controls)[1],.8);
        for(std::size_t j=0;j<frames;++j){const double transient=std::max(0.,work[13][j]-work[14][j])*work[1][j];
            work[10][j]=std::sqrt(clamp(work[13][j]));
            work[3][j]=clamp(work[3][j]*(.6+.4*work[12][j])+c.get("acceleration_harmonic_boost")*transient+work[16][j]*work[13][j]);
            work[1][j]*=(.85+.15*work[12][j])*(1+c.get("acceleration_dynamic_gain")*transient);
            work[1][j]*=work[15][j]+(1-work[15][j])*work[10][j];
            work[11][j]=work[12][j]*clamp(work[13][j]/.025)*clamp(work[1][j]/.05);
            work[2][j]*=c.get("regen_gain");
        }
    }
    if(sound_speed<.1&&drive_level<1e-5&&regen_level<1e-5){cycle_state.position=0.;std::fill_n(work[11].data(),frames,0.);}
    for(int k:{30,31,32,33,37})std::fill_n(work[k].data(),frames,0.);
    if(work[6][0]<1.){
        if(work[4][0]<1.||params[5]<1.){legacy(work[0].data(),work[1].data(),work[3].data(),frames,work[30].data(),work[31].data());++render_counts[0];}
        if(work[4][0]>0.||params[5]>0.){
            Colours colours;for(int i=0;i<11;++i){smooth(19+i,electric_colour[i],electric_colour_target[i],.20);colours[i]=work[19+i].data();}
            electric(work[7].data(),work[1].data(),work[3].data(),colours,electric_state,sample_rate,frames,work[32].data(),work[33].data());++render_counts[1];
            const bool has_traction=work[17][0]>1e-5||response_target[2]>0.;
            const bool has_cycle=has_traction&&(work[18][0]>1e-5||response_target[3]>0.);
            const bool has_ensemble=work[26][0]>1e-5||electric_colour_target[7]>0.;
            if(has_traction)traction(work[8].data(),work[7].data(),work[20].data(),work[3].data(),traction_state,sample_rate,frames,work[34].data());
            if(has_cycle)render_cycle(work[11].data(),work[7].data(),work[20].data(),work[3].data(),frames,work[35].data());
            if(has_ensemble)orchestra(work[7].data(),work[20].data(),work[3].data(),orchestra_state,sample_rate,frames,work[36].data());
            for(std::size_t j=0;j<frames;++j){if(has_traction){
                const double tone=has_cycle?(1-work[18][j])*work[34][j]+work[18][j]*work[35][j]:work[34][j];
                const double blend=work[17][j]*(.20+.80*work[10][j]),rb=.35*work[17][j];
                work[32][j]=(1-blend)*work[32][j]+blend*tone;work[33][j]=(1-rb)*work[33][j]+rb*.30*work[34][j];
            }if(has_ensemble){const double blend=work[26][j];work[32][j]=(1-blend)*work[32][j]+blend*work[36][j];work[33][j]=(1-.5*blend)*work[33][j]+.15*blend*work[36][j];}}
        }
    }
    if(work[6][0]>0.||order_active){if(order_sleeping)order_synth.resume();order_sleeping=false;order_synth.render(frames,work[37].data());++render_counts[2];}else order_sleeping=true;
    for(std::size_t j=0;j<frames;++j){
        const double motor=work[30][j]*(1-work[4][j])+work[32][j]*work[4][j];
        const double regen=work[31][j]*(1-work[4][j])+work[33][j]*work[4][j];
        const double sound=(work[1][j]*motor+.60*work[2][j]*regen)/std::max(1.,work[1][j]+work[2][j]);
        double sample=(1-work[6][j])*std::tanh(sound*work[5][j]*1.6)+work[6][j]*std::tanh(work[37][j]);
        if(startup_sample>=0){const double t=(startup_sample+static_cast<double>(j))/sample_rate;
            const double envelope=std::pow(std::sin(pi*clamp(t/1.4)),2);sample+=.045*envelope*(std::sin(2*pi*196*t)+.5*std::sin(2*pi*294*t));}
        const float rendered=static_cast<float>(std::clamp(sample*work[9][j],-1.,1.));
        for(int c=0;c<channels;++c)out[j*channels+c]=rendered;
    }
    if(startup_sample>=0){startup_sample+=static_cast<int>(frames);if(startup_sample>=1.4*sample_rate)startup_sample=-1;}
    if(debug_enabled){const auto count=std::min(frames,debug_output.size());
        std::move(debug_output.begin()+count,debug_output.end(),debug_output.begin());
        for(std::size_t j=0;j<count;++j)debug_output[debug_output.size()-count+j]=out[(frames-count+j)*channels];}
}
void Engine::render_offline(float* out,std::size_t frames,int channels){
    std::lock_guard<std::mutex> control(control_mutex);
    if(output->opened())throw std::runtime_error("Offline rendering requires a stopped output stream.");
    prepare(frames);render(out,frames,channels);
}
void Engine::start(){
    std::lock_guard<std::mutex> control(control_mutex);
    if(output->opened())return;
    const auto device=Output::default_device();
    if(device.sample_rate<8000)throw std::runtime_error("Output sample rate must be at least 8000 Hz.");
    {std::lock_guard<std::recursive_mutex> guard(mutex);
        if(sample_rate!=device.sample_rate){sample_rate=device.sample_rate;order_synth.change_sample_rate(sample_rate);random=Random(19);make_source();}
        prepare(512);reset();
    }
    output->start(device,[this](float* out,unsigned long frames,int channels){render(out,frames,channels);});
}
void Engine::stop(){std::lock_guard<std::mutex> control(control_mutex);try{output->stop();}catch(...){reset();throw;}reset();}
bool Engine::opened()const{std::lock_guard<std::mutex> control(control_mutex);return output->opened();}
bool Engine::active()const{std::lock_guard<std::mutex> control(control_mutex);return output->active();}
void Engine::refresh_devices(){Output::refresh_devices();}
}
