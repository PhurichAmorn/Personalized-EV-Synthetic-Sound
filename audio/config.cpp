#include "engine.h"
#include <cmath>
#include <algorithm>
#include <stdexcept>
namespace evsound {
OrderConfig::OrderConfig() {
    values["dominant_order"]=4.0;
    curves["order_amplitudes"]={{0.5,0.05},{1.0,0.08},{1.5,0.05},{2.0,0.12},{2.5,0.07},{3.0,0.15},{3.5,0.08},{4.0,0.3},{4.5,0.08},{5.0,0.12},{6.0,0.08}};
    values["low_frequency_weight"]=1.2;
    values["high_frequency_attenuation"]=0.4;
    curves["rpm_dynamic_gain_curve"]={{1000.0,0.7},{2500.0,0.85},{3250.0,1.0},{4000.0,1.1},{6000.0,1.15}};
    curves["throttle_gain_curve"]={{0.0,0.16},{10.0,0.25},{20.0,0.38},{50.0,0.65},{100.0,1.0}};
    curves["throttle_harmonic_curve"]={{0.0,0.3},{10.0,0.35},{20.0,0.42},{50.0,0.65},{100.0,1.0}};
    values["master_gain"]=0.85;
    values["rpm_smoothing_s"]=0.12;
    values["throttle_smoothing_s"]=0.1;
    values["gain_smoothing_s"]=0.15;
    values["speed_pitch_reference_kmh"]=180.0;
    values["acceleration_reference_m_s2"]=8.0;
    values["speed_pitch_saturation"]=3.0;
    values["throttle_gamma"]=1.25;
    curves["throttle_brightness_curve"]={{0.0,0.55},{1.0,1.0}};
    curves["load_gain_curve"]={{0.0,0.16},{1.0,1.0}};
    curves["load_bass_curve"]={{0.0,0.8},{1.0,1.15}};
    curves["load_harmonic_curve"]={{0.0,0.4},{1.0,1.0}};
    values["acceleration_dynamic_gain"]=0.1;
    values["acceleration_harmonic_boost"]=0.15;
    values["acceleration_brightness_boost"]=0.1;
    values["acceleration_smoothing_s"]=0.18;
    values["load_smoothing_s"]=0.12;
    values["regen_gain"]=0.45;
    values["regen_harmonic_mix"]=0.45;
    values["regen_brightness"]=0.6;
    values["regen_smoothing"]=0.22;
    values["regen_intensity"]=0.55;
    values["noise_gain"]=0.0;
}
const std::map<std::string,Profile>& profiles() {
    static const std::map<std::string,Profile> data={
        {"Sound Profile A",{{"base_hz",42.0},{"gain",0.34},{"richness",0.22}}},
        {"Sound Profile B",{{"base_hz",34.0},{"gain",0.3},{"richness",0.38}}},
    };
    return data;
}
const std::map<std::string,Profile>& sound_themes() {
    static const std::map<std::string,Profile> data={
        {"Comfort",{{"base_hz",70.0},{"gain",0.32},{"richness",0.045},{"electric_mix",1.0},{"electric_pitch_scale",0.14},{"electric_pitch_offset",115.2},{"electric_depth",0.04},{"electric_cutoff",520.0},{"electric_detune",0.002},{"electric_effort",0.3},{"electric_regen_gain",0.2},{"electric_growl",0.12},{"drive_cruise_gain",0.18},{"acceleration_richness",0.025},{"drive_attack_s",0.16},{"drive_release_s",0.3},{"regen_attack_s",0.22},{"regen_release_s",0.32},{"electric_pitch_smoothing_s",0.22}}},
        {"Sport",{{"base_hz",70.0},{"gain",0.32},{"richness",0.48},{"electric_mix",1.0},{"electric_pitch_scale",1.15},{"electric_pitch_offset",9.5},{"electric_depth",0.12},{"electric_cutoff",900.0},{"electric_detune",0.0005},{"electric_effort",1.5},{"electric_regen_gain",0.34},{"electric_growl",1.0},{"electric_regen_richness",0.45},{"drive_cruise_gain",0.72},{"acceleration_richness",0.18},{"drive_attack_s",0.07},{"drive_release_s",0.13},{"regen_attack_s",0.14},{"regen_release_s",0.24},{"electric_pitch_smoothing_s",0.1}}},
        {"Deep",{{"base_hz",70.0},{"gain",0.32},{"richness",0.22},{"electric_mix",1.0},{"electric_pitch_scale",0.55},{"electric_pitch_offset",31.5},{"electric_depth",0.22},{"electric_cutoff",550.0},{"electric_detune",0.0015},{"electric_effort",0.85},{"electric_regen_gain",0.3},{"electric_growl",0.15},{"drive_cruise_gain",0.35},{"acceleration_richness",0.1},{"drive_attack_s",0.22},{"drive_release_s",0.4},{"regen_attack_s",0.3},{"regen_release_s",0.45},{"electric_pitch_smoothing_s",0.18},{"traction_mix",0.4},{"traction_cycle_s",0.0},{"traction_crossfade_s",1.2},{"traction_sweep_hz",55.0},{"traction_morph_mix",0.0},{"traction_stage_colour",0.7},{"orchestral_mix",0.5}}},
    };
    return data;
}
const std::map<std::string,Profile>& debug_themes() {
    static const std::map<std::string,Profile> data={
        {"Comfort / Dynamic Orders",{{"base_hz",42.0},{"gain",0.34},{"richness",0.22},{"order_synthesis",1.0}}},
        {"Premium EV",{{"base_hz",42.0},{"gain",0.34},{"richness",0.22}}},
        {"Electric Motorsport",{{"base_hz",70.0},{"gain",0.34},{"richness",0.3},{"electric_mix",1.0}}},
        {"Taycan Inspired",{{"base_hz",70.0},{"gain",0.34},{"richness",0.3},{"electric_mix",1.0},{"electric_pitch_scale",1.0},{"electric_pitch_offset",20.0}}},
        {"Comfort",{{"base_hz",70.0},{"gain",0.32},{"richness",0.045},{"electric_mix",1.0},{"electric_pitch_scale",0.14},{"electric_pitch_offset",115.2},{"electric_depth",0.04},{"electric_cutoff",520.0},{"electric_detune",0.002},{"electric_effort",0.3},{"electric_regen_gain",0.2},{"electric_growl",0.12},{"drive_cruise_gain",0.18},{"acceleration_richness",0.025},{"drive_attack_s",0.16},{"drive_release_s",0.3},{"regen_attack_s",0.22},{"regen_release_s",0.32},{"electric_pitch_smoothing_s",0.22}}},
        {"Sport",{{"base_hz",70.0},{"gain",0.32},{"richness",0.48},{"electric_mix",1.0},{"electric_pitch_scale",1.15},{"electric_pitch_offset",9.5},{"electric_depth",0.12},{"electric_cutoff",900.0},{"electric_detune",0.0005},{"electric_effort",1.5},{"electric_regen_gain",0.34},{"electric_growl",1.0},{"electric_regen_richness",0.45},{"drive_cruise_gain",0.72},{"acceleration_richness",0.18},{"drive_attack_s",0.07},{"drive_release_s",0.13},{"regen_attack_s",0.14},{"regen_release_s",0.24},{"electric_pitch_smoothing_s",0.1}}},
        {"Deep",{{"base_hz",70.0},{"gain",0.32},{"richness",0.22},{"electric_mix",1.0},{"electric_pitch_scale",0.55},{"electric_pitch_offset",31.5},{"electric_depth",0.22},{"electric_cutoff",550.0},{"electric_detune",0.0015},{"electric_effort",0.85},{"electric_regen_gain",0.3},{"electric_growl",0.15},{"drive_cruise_gain",0.35},{"acceleration_richness",0.1},{"drive_attack_s",0.22},{"drive_release_s",0.4},{"regen_attack_s",0.3},{"regen_release_s",0.45},{"electric_pitch_smoothing_s",0.18},{"traction_mix",0.4},{"traction_cycle_s",0.0},{"traction_crossfade_s",1.2},{"traction_sweep_hz",55.0},{"traction_morph_mix",0.0},{"traction_stage_colour",0.7},{"orchestral_mix",0.5}}},
    };
    return data;
}
const std::vector<std::string>& sound_theme_order(){static const std::vector<std::string> names={"Comfort","Sport","Deep"};return names;}
const std::vector<std::string>& debug_theme_order(){static const std::vector<std::string> names={"Comfort / Dynamic Orders","Premium EV","Electric Motorsport","Taycan Inspired","Comfort","Sport","Deep"};return names;}
void OrderConfig::validate() const {
    auto positive=[&](const char* key){double v=get(key); if(!std::isfinite(v)||v<=0) throw std::invalid_argument(std::string(key)+" must be positive.");};
    auto bounded=[&](const char* key,double limit){double v=get(key); if(!std::isfinite(v)||v<0||v>limit) throw std::invalid_argument(std::string(key)+" is outside its bounds.");};
    for(auto key:{"speed_pitch_reference_kmh","acceleration_reference_m_s2","speed_pitch_saturation","throttle_gamma","acceleration_smoothing_s","load_smoothing_s","regen_smoothing","low_frequency_weight","rpm_smoothing_s","throttle_smoothing_s","gain_smoothing_s"}) positive(key);
    for(auto key:{"regen_intensity","regen_gain","regen_harmonic_mix","regen_brightness","high_frequency_attenuation","master_gain"}) bounded(key,1.);
    bounded("noise_gain",.05); bounded("acceleration_dynamic_gain",.10);
    bounded("acceleration_harmonic_boost",.15); bounded("acceleration_brightness_boost",.10);
    if(speed_pitch_curve!="linear"&&speed_pitch_curve!="exponential") throw std::invalid_argument("Unknown speed pitch curve.");
    const auto& orders=curves.at("order_amplitudes");
    bool dominant=false; double total=0.;
    for(std::size_t i=0;i<orders.size();++i){
        const auto [order,amplitude]=orders[i];
        if(!std::isfinite(order)||order<=0||!std::isfinite(amplitude)||amplitude<0) throw std::invalid_argument("Invalid order amplitudes.");
        for(std::size_t j=0;j<i;++j) if(orders[j].first==order) throw std::invalid_argument("Orders must be unique.");
        dominant|=order==get("dominant_order"); total+=amplitude;
    }
    if(!dominant||total<=0) throw std::invalid_argument("Orders must include dominant order and nonzero total amplitude.");
    for(const auto& [name,curve]:curves){
        if(name=="order_amplitudes") continue;
        if(curve.size()<2) throw std::invalid_argument("Gain curves need at least two knots.");
        for(std::size_t i=0;i<curve.size();++i){
            if(!std::isfinite(curve[i].first)||!std::isfinite(curve[i].second)||curve[i].second<0 || (i&&curve[i].first<=curve[i-1].first)) throw std::invalid_argument("Invalid gain curve.");
        }
    }
}
double curve_at(double x,const Curve& curve) {
    if(x<=curve.front().first) return curve.front().second;
    for(std::size_t i=0;i+1<curve.size();++i) if(x<curve[i+1].first){
        double t=std::clamp((x-curve[i].first)/(curve[i+1].first-curve[i].first),0.,1.);
        return curve[i].second+(curve[i+1].second-curve[i].second)*t*t*(3-2*t);
    }
    return curve.back().second;
}
}
