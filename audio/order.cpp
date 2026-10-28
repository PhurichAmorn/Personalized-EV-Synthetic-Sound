#include "engine.h"
#include <algorithm>
#include <cmath>
#include <complex>
#include <stdexcept>

namespace evsound {
namespace {
double value(const Profile& values,const char* key) {
    for(const auto& entry:values) if(entry.first==key) return entry.second;
    throw std::out_of_range("Unknown order parameter.");
}
const Curve& curve(const std::map<std::string,Curve>& curves,const char* key) {
    for(const auto& entry:curves) if(entry.first==key) return entry.second;
    throw std::out_of_range("Unknown order curve.");
}
double clamp01(double x) { return std::min(1.,std::max(0.,x)); }
double smoothstep(double x) { x=clamp01(x); return x*x*(3-2*x); }
double spectral(double f,double low,double high) {
    const double shelf=high+(low-high)/(1+std::pow(std::max(0.,f-400.)/250.,2));
    return shelf*smoothstep((f-20.)/20.)*smoothstep((1200.-f)/200.);
}
double maximum(const Curve& curve) {
    double result=0.; for (const auto& p:curve) result=std::max(result,p.second);
    return result;
}
}
OrderSynth::OrderSynth(int rate,OrderConfig settings):sample_rate(rate),config(std::move(settings)) {
    if (sample_rate<8000) throw std::invalid_argument("Sample rate must be at least 8000 Hz.");
    config.validate(); setup(); reset();
}
void OrderSynth::setup() {
    const auto& orders=curve(config.curves,"order_amplitudes");
    phases.resize(orders.size());
    const double low_weight=value(config.values,"low_frequency_weight");
    const double accel_dynamic=value(config.values,"acceleration_dynamic_gain");
    const double accel_harmonic=value(config.values,"acceleration_harmonic_boost");
    const double accel_brightness=value(config.values,"acceleration_brightness_boost");
    const double regen_gain=value(config.values,"regen_gain");
    const double noise_gain=value(config.values,"noise_gain");
    const auto& rpm_curve=curve(config.curves,"rpm_dynamic_gain_curve");
    const auto& throttle_gain_curve=curve(config.curves,"throttle_gain_curve");
    const auto& throttle_harmonic_curve=curve(config.curves,"throttle_harmonic_curve");
    const auto& throttle_brightness_curve=curve(config.curves,"throttle_brightness_curve");
    const auto& load_gain_curve=curve(config.curves,"load_gain_curve");
    const auto& load_bass_curve=curve(config.curves,"load_bass_curve");
    const auto& load_harmonic_curve=curve(config.curves,"load_harmonic_curve");
        double total = 0.; for (const auto& order : orders) total += order.second;
        const double direct = (total * std::max(1., maximum(throttle_harmonic_curve))
                               * std::max(1., low_weight) + noise_gain)
            * maximum(rpm_curve)
            * maximum(throttle_gain_curve);
        const double driving = (total * std::max(1., low_weight)
            * std::max(1., maximum(load_bass_curve))
            * std::max(1., maximum(load_harmonic_curve))
            * std::max(1., maximum(throttle_harmonic_curve))
            * (1 + accel_harmonic)
            * std::max(1., maximum(throttle_brightness_curve) * (1 + accel_brightness))
            + noise_gain)
            * maximum(load_gain_curve)
            * std::max(1., regen_gain)
            * (.85 + .15 * maximum(throttle_gain_curve))
            * (1 + accel_dynamic) * maximum(rpm_curve);
        normalization = .48 / std::max({direct, driving, 1e-9});

    // Bilinear transform of the two-pole analog Butterworth bandpass.
    const double low=2*sample_rate*std::tan(pi*40/sample_rate);
    const double high=2*sample_rate*std::tan(pi*300/sample_rate);
    const double bandwidth=high-low, center=std::sqrt(low*high), fs2=2.*sample_rate;
    const std::complex<double> prototype(-std::sqrt(.5),std::sqrt(.5));
    const auto half=prototype*(bandwidth/2);
    const auto root=std::sqrt(half*half-center*center);
    const auto p1=half+root, p2=half-root;
    const auto z1=(fs2+p1)/(fs2-p1), z2=(fs2+p2)/(fs2-p2);
    const auto fast=std::abs(z1)<std::abs(z2)?z1:z2;
    const auto slow=std::abs(z1)<std::abs(z2)?z2:z1;
    const double k=bandwidth*bandwidth*fs2*fs2/std::norm((fs2-p1)*(fs2-p2));
    noise_sos={{{k,2*k,k,1.,-2*fast.real(),std::norm(fast)},
                {1.,-2.,1.,1.,-2*slow.real(),std::norm(slow)}}};
}
void OrderSynth::change_sample_rate(int rate) {
    std::lock_guard<std::recursive_mutex> lock(mutex);
    if(rate<8000)throw std::invalid_argument("Sample rate must be at least 8000 Hz.");
    sample_rate=rate;setup();random=Random(73);reset();
}
void OrderSynth::reset() {
    std::lock_guard<std::recursive_mutex> lock(mutex);
    std::fill(phases.begin(),phases.end(),0.);
    rpm=requested_rpm=1000.; throttle=gain=regen_mix=regen_request=0.;
    requested_throttle=drive_load=accel_fast=accel_baseline=0.;
    enabled=false; driving_controls.reset(); noise_state={};
}
void OrderSynth::configure(const OrderConfig& value) {
    std::lock_guard<std::recursive_mutex> lock(mutex);
    value.validate();
    const auto old_orders=curve(config.curves,"order_amplitudes");
    const auto old_phases=phases;
    config=value; setup();
    const auto& orders=curve(config.curves,"order_amplitudes");
    for(std::size_t i=0;i<orders.size();++i) {
        phases[i]=0.;
        for(std::size_t j=0;j<old_orders.size();++j)
            if(orders[i].first==old_orders[j].first) {phases[i]=old_phases[j];break;}
    }
}
void OrderSynth::set_parameters(double r,double t,bool on,double regen) {
    std::lock_guard<std::recursive_mutex> lock(mutex);
    if(!std::isfinite(r)||!std::isfinite(t)||!std::isfinite(regen))
        throw std::invalid_argument("Sound RPM and throttle must be finite.");
    driving_controls.reset(); requested_rpm=std::max(0.,r);
    requested_throttle=std::clamp(t,0.,100.);enabled=on;regen_request=clamp01(regen);
}
void OrderSynth::set_driving_controls(double r,double pedal,double drive,double regen,double acceleration,bool on) {
    std::lock_guard<std::recursive_mutex> lock(mutex);
    if(!std::isfinite(drive)||!std::isfinite(acceleration))
        throw std::invalid_argument("Driving sound controls must be finite.");
    set_parameters(r,pedal*100.,on,regen);
    driving_controls=std::array<double,2>{clamp01(drive),clamp01(acceleration)};
}
void OrderSynth::resume() {
    std::lock_guard<std::recursive_mutex> lock(mutex);
    rpm=requested_rpm;throttle=requested_throttle;gain=enabled?1.:0.;regen_mix=regen_request;
}
double OrderSynth::pitch_progression(double speed) const {
    std::lock_guard<std::recursive_mutex> lock(mutex);
    const double x=clamp01(speed/value(config.values,"speed_pitch_reference_kmh"));
    const double k=value(config.values,"speed_pitch_saturation");
    return config.speed_pitch_curve=="linear"?x:-std::expm1(-k*x)/-std::expm1(-k);
}
double OrderSynth::spectral_weight(double f) const {
    std::lock_guard<std::recursive_mutex> lock(mutex);
    const double low=value(config.values,"low_frequency_weight"), high=value(config.values,"high_frequency_attenuation");
    return spectral(f,low,high);
}
void OrderSynth::render(std::size_t frames,double* out) {
    std::lock_guard<std::recursive_mutex> lock(mutex);
    if(frames==0) return;
    const double master_gain=value(config.values,"master_gain");
    const double rpm_smooth=value(config.values,"rpm_smoothing_s");
    const double throttle_smooth=value(config.values,"throttle_smoothing_s");
    const double gain_smooth=value(config.values,"gain_smoothing_s");
    const double throttle_gamma=value(config.values,"throttle_gamma");
    const double accel_dynamic=value(config.values,"acceleration_dynamic_gain");
    const double accel_harmonic=value(config.values,"acceleration_harmonic_boost");
    const double accel_brightness=value(config.values,"acceleration_brightness_boost");
    const double accel_smooth=value(config.values,"acceleration_smoothing_s");
    const double load_smooth=value(config.values,"load_smoothing_s");
    const double regen_gain=value(config.values,"regen_gain");
    const double regen_harmonic=value(config.values,"regen_harmonic_mix");
    const double regen_brightness=value(config.values,"regen_brightness");
    const double regen_smooth=value(config.values,"regen_smoothing");
    const double noise_gain=value(config.values,"noise_gain");
    const auto& rpm_curve=curve(config.curves,"rpm_dynamic_gain_curve");
    const auto& throttle_gain_curve=curve(config.curves,"throttle_gain_curve");
    const auto& throttle_harmonic_curve=curve(config.curves,"throttle_harmonic_curve");
    const auto& throttle_brightness_curve=curve(config.curves,"throttle_brightness_curve");
    const auto& load_gain_curve=curve(config.curves,"load_gain_curve");
    const auto& load_bass_curve=curve(config.curves,"load_bass_curve");
    const auto& load_harmonic_curve=curve(config.curves,"load_harmonic_curve");
    const auto& orders=curve(config.curves,"order_amplitudes");
    const double dominant=value(config.values,"dominant_order");
    const double sr=sample_rate;
    const double low_weight=value(config.values,"low_frequency_weight");
    const double high_attenuation=value(config.values,"high_frequency_attenuation");
        const double start_rpm = rpm, start_throttle = throttle, start_regen = regen_mix, start_gain = gain;
        const double start_drive = drive_load, start_fast = accel_fast, start_base = accel_baseline;
        for (std::size_t j = 0; j < frames; ++j) {
            const double elapsed = j + 1.;
            rpm = requested_rpm + (start_rpm - requested_rpm) * std::exp(-elapsed / (sr * rpm_smooth));
            throttle = requested_throttle + (start_throttle - requested_throttle)
                * std::exp(-elapsed / (sr * throttle_smooth));
            regen_mix = regen_request + (start_regen - regen_request)
                * std::exp(-elapsed / (sr * regen_smooth));
            gain = (enabled ? 1. : 0.) + (start_gain - (enabled ? 1. : 0.))
                * std::exp(-elapsed / (sr * gain_smooth));
            double level = curve_at(throttle, throttle_gain_curve);
            double mix = curve_at(throttle, throttle_harmonic_curve);
            double body = 1., brightness = 1., urgency = 0.;
            if (driving_controls) {
                drive_load = (*driving_controls)[0] + (start_drive - (*driving_controls)[0])
                    * std::exp(-elapsed / (sr * load_smooth));
                accel_fast = (*driving_controls)[1] + (start_fast - (*driving_controls)[1])
                    * std::exp(-elapsed / (sr * accel_smooth));
                accel_baseline = (*driving_controls)[1] + (start_base - (*driving_controls)[1]) * std::exp(-elapsed / (sr * .8));
                urgency = std::max(0., accel_fast - accel_baseline) * drive_load;
                const double intent = std::pow(throttle / 100., throttle_gamma);
                mix = curve_at(intent * 100., throttle_harmonic_curve)
                    * curve_at(drive_load, load_harmonic_curve) * (1 + accel_harmonic * urgency);
                mix = (1 - regen_mix) * mix + regen_mix * regen_harmonic;
                body = (1 - regen_mix) * curve_at(drive_load, load_bass_curve) + regen_mix * .70;
                brightness = ((1 - regen_mix) * curve_at(intent, throttle_brightness_curve)
                              + regen_mix * regen_brightness) * (1 + accel_brightness * urgency);
                level = curve_at(drive_load, load_gain_curve)
                    * (.85 + .15 * curve_at(intent * 100., throttle_gain_curve));
                level = ((1 - regen_mix) * level + regen_mix * regen_gain) * (1 + accel_dynamic * urgency);
            }
            double signal = 0.;
            for (size_t k = 0; k < orders.size(); ++k) {
                const double f = orders[k].first * rpm / 60.;
                phases[k] = std::fmod(phases[k] + 2 * pi * f / sr, 2 * pi);
                const double harmonic = orders[k].first == dominant ? 1. : mix;
                const double balance = 1 - .65 * regen_mix * clamp01((orders[k].first - 2.) / 4.);
                const double nyquist = clamp01((.49 * sr - f) / (.04 * sr));
                double weight = orders[k].second * balance * harmonic * spectral(f,low_weight,high_attenuation) * nyquist;
                if (driving_controls) {
                    const double low = 1 / (1 + std::pow(f / 400., 4));
                    weight *= low * body + (1 - low) * brightness;
                }
                signal += weight * std::sin(phases[k]);
            }
            if (noise_gain > 0.) {
                double value=random.uniform(-1.,1.);
                for(size_t section=0;section<noise_sos.size();++section) {
                    const auto& b=noise_sos[section]; auto& z=noise_state[section];
                    const double filtered=b[0]*value+z[0];
                    z[0]=b[1]*value-b[4]*filtered+z[1];
                    z[1]=b[2]*value-b[5]*filtered;
                    value=filtered;
                }
                signal += noise_gain * std::clamp(value,-1.,1.);
            }
            out[j] = signal * gain * curve_at(rpm, rpm_curve) * level * normalization * master_gain;
        }
}
}
