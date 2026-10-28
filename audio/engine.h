#pragma once
#include "dsp.h"
#include <array>
#include <cstdint>
#include <map>
#include <mutex>
#include <string>
#include <string_view>
#include <vector>
#include <optional>
#include <memory>
#include <stdexcept>
namespace evsound {
using Curve=std::vector<std::pair<double,double>>;
using Profile=std::map<std::string,double>;
struct OrderConfig {
    Profile values;
    std::map<std::string,Curve> curves;
    std::string speed_pitch_curve="exponential";
    OrderConfig();
    void validate() const;
    double get(std::string_view key) const {for(const auto& item:values) if(item.first==key)return item.second;throw std::out_of_range("Unknown order parameter.");}
};
const std::map<std::string,Profile>& profiles();
const std::vector<std::string>& sound_theme_order();
const std::vector<std::string>& debug_theme_order();
const std::map<std::string,Profile>& debug_themes();
const std::map<std::string,Profile>& sound_themes();
double curve_at(double x,const Curve& curve);
struct Random {
    std::uint64_t lo,hi,inc_lo,inc_hi;
    bool has_uint32=false; std::uint32_t cached=0;
    explicit Random(int seed);
    std::uint64_t next64();
    std::uint32_t next32();
    double uniform(double low=0.,double high=1.);
    std::uint32_t integer(std::uint32_t high);
};
class OrderSynth {
public:
    explicit OrderSynth(int sample_rate=44100,OrderConfig config=OrderConfig());
    int sample_rate;
    OrderConfig config;
    std::vector<double> phases;
    double rpm=1000.,throttle=0.,gain=0.,regen_mix=0.,regen_request=0.;
    double drive_load=0.,accel_fast=0.,accel_baseline=0.;
    double requested_rpm=1000.,requested_throttle=0.; bool enabled=false;
    std::optional<std::array<double,2>> driving_controls;
    mutable std::recursive_mutex mutex;
    void reset();
    void configure(const OrderConfig& value);
    void change_sample_rate(int rate);
    void set_parameters(double rpm,double throttle,bool enabled=true,double regen=0.);
    void set_driving_controls(double rpm,double pedal,double drive,double regen,double acceleration,bool enabled);
    double pitch_progression(double speed) const;
    double spectral_weight(double frequency) const;
    void resume();
    void render(std::size_t frames,double* output);
private:
    Random random{73};
    double normalization=1.;
    std::array<std::array<double,6>,2> noise_sos{};
    std::array<std::array<double,2>,2> noise_state{};
    void setup();
};
class Output;
class Engine {
public:
    explicit Engine(int sample_rate=44100,OrderConfig config=OrderConfig());
    ~Engine();
    Engine(const Engine&)=delete; Engine& operator=(const Engine&)=delete;
    int sample_rate;
    OrderSynth order_synth;
    bool order_active=false,order_sleeping=false,debug_enabled=false;
    std::optional<std::array<double,2>> driving_controls;
    std::string operating_state="off";
    int startup_sample=-1;
    double playback_gain=1.,playback_target=1.;
    std::array<double,6> params{42.,0.,0.,.34,.22,0.};
    double hz=42.,richness=.22,drive_level=0.,regen_level=0.,output_gain=0.;
    double electric_mix=0.,order_mix=0.,electric_hz=470.,electric_hz_target=470.;
    double sound_speed=0.,sound_speed_target=0.,intent=0.,accel_fast=0.,accel_baseline=0.;
    std::array<double,4> response{1.,0.,0.,0.},response_target{1.,0.,0.,0.};
    std::array<double,5> response_timings{.10,.09,.16,.24,.30};
    std::array<double,11> electric_colour{.14,900.,.01,1.,.45,0.,0.,0.,0.,0.,0.};
    std::array<double,11> electric_colour_target=electric_colour;
    ElectricState electric_state;
    OrchestraState orchestra_state;
    TractionState traction_state;
    CycleState cycle_state;
    std::array<double,5> cycle_target{2.5,.60,140.,0.,0.};
    std::vector<double> source;
    std::array<double,4096> debug_output{};
    std::array<std::uint64_t,3> render_counts{};
    mutable std::recursive_mutex mutex;
    static double fundamental_for_rpm(double rpm,double max_rpm,double base=42.);
    void reset();
    void set_parameters(double rpm,double max_rpm,double drive_power,double regen_power,
                        const Profile& profile,double throttle=0.,std::optional<double> motor_load={},
                        std::optional<double> regen_load={},double acceleration=0.);
    void set_driving_parameters(double speed,double pedal,double load,double acceleration,
                               const std::string& state,const Profile& profile,double volume=1.,bool enabled=true);
    void set_order_parameters(double rpm,double throttle,bool enabled=true);
    void prepare(std::size_t frames);
    void render(float* output,std::size_t frames,int channels=1);
    void render_cycle(const double* rate,const double* hz,const double* cutoff,const double* richness,
                      std::size_t frames,double* output);
    void render_offline(float* output,std::size_t frames,int channels);
    void start(); void stop(); bool opened() const; bool active() const;
    static void refresh_devices();
private:
    mutable std::mutex control_mutex;
    std::unique_ptr<Output> output;
    Random random{19};
    struct Grain {double position=0.; int age=0,duration=0;};
    std::array<Grain,64> grains{}; std::size_t grain_count=0;
    int grain_clock=0;
    double phase=0.,bass_phase=0.,regen_phase=0.;
    std::array<std::vector<double>,38> work;
    std::size_t capacity=0;
    void make_source();
    void legacy(const double* hz,const double* drive,const double* richness,std::size_t frames,
                double* motor,double* regen);
public:
    std::size_t active_grains() const {return grain_count;}
};
}
