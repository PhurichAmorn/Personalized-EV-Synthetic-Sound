#include "engine.h"
#include "output.h"
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <algorithm>
#include <limits>
namespace py=pybind11;
using namespace evsound;
static OrderConfig read_config(py::object object){
    OrderConfig result;
    if(object.is_none())return result;
    py::dict data=py::isinstance<py::dict>(object)?py::cast<py::dict>(object):py::module_::import("dataclasses").attr("asdict")(object).cast<py::dict>();
    for(auto item:data){const auto key=py::cast<std::string>(item.first);
        if(key=="speed_pitch_curve")result.speed_pitch_curve=py::cast<std::string>(item.second);
        else if(result.values.count(key))result.values[key]=py::cast<double>(item.second);
        else if(result.curves.count(key))result.curves[key]=py::cast<Curve>(item.second);
        else throw py::type_error("Unknown order configuration field: "+key);
    }
    result.validate();return result;
}
static py::dict config_dict(const OrderConfig& config){
    py::dict result;
    for(const auto& [name,value]:config.values)result[py::str(name)]=value;
    for(const auto& [name,curve]:config.curves){py::tuple points(curve.size());for(std::size_t i=0;i<curve.size();++i)points[i]=py::make_tuple(curve[i].first,curve[i].second);result[py::str(name)]=points;}
    result["speed_pitch_curve"]=config.speed_pitch_curve;return result;
}
static py::object config_object(const OrderConfig& config){return py::module_::import("audio").attr("OrderSoundConfig")(**config_dict(config));}
static int rate(double value){if(!std::isfinite(value)||value<8000||value>std::numeric_limits<int>::max())throw py::value_error("Sample rate must be at least 8000 Hz.");return static_cast<int>(value);}
static std::size_t count(py::ssize_t frames){if(frames<0)throw py::value_error("Frame count must be nonnegative.");return static_cast<std::size_t>(frames);}
template<class T,std::size_t N>static py::array_t<T> array(const std::array<T,N>& data){py::array_t<T> out(N);std::copy(data.begin(),data.end(),out.mutable_data());return out;}
static py::array_t<double> array(const std::vector<double>& data){py::array_t<double> out(data.size());std::copy(data.begin(),data.end(),out.mutable_data());return out;}
static void vector(const py::array& a,py::ssize_t n){if(a.ndim()!=1||a.size()!=n)throw py::value_error("Audio buffers must be vectors of matching length.");}
using Input=py::array_t<double,py::array::c_style|py::array::forcecast>;
static void callback(Engine& e,py::array_t<float,py::array::c_style> out,py::ssize_t frames,py::object,py::object){
    count(frames);
    if(out.ndim()!=2||out.shape(0)!=frames||out.shape(1)<1||out.shape(1)>2||!out.writeable())throw py::value_error("Expected writable float32 (frames, 1 or 2) output.");
    py::gil_scoped_release release;e.render_offline(out.mutable_data(),frames,static_cast<int>(out.shape(1)));
}
PYBIND11_MODULE(_native_dsp,m){
    m.def("order_defaults",[]{return config_dict(OrderConfig());});
    m.def("validate_config",[](py::object c){read_config(c);});
    m.def("profiles",&profiles);m.def("sound_themes",[]{py::dict out;for(const auto& name:sound_theme_order())out[py::str(name)]=sound_themes().at(name);return out;});
    m.def("debug_themes",[]{py::dict out;for(const auto& name:debug_theme_order())out[py::str(name)]=debug_themes().at(name);return out;});
    m.def("set_output_library",&Output::set_library);
    m.def("smooth_curve",[](Input values,const Curve& curve){
        OrderConfig c;c.curves["load_gain_curve"]=curve;c.validate();
        auto info=values.request();py::array_t<double> out(info.shape);
        for(py::ssize_t i=0;i<values.size();++i)out.mutable_data()[i]=curve_at(values.data()[i],curve);return out;
    });
    py::class_<OrderSynth>(m,"OrderSynth",py::dynamic_attr())
        .def(py::init([](double sr,py::object config){return std::make_unique<OrderSynth>(rate(sr),read_config(config));}),py::arg("sample_rate")=44100,py::arg("config")=py::none())
        .def_readonly("sample_rate",&OrderSynth::sample_rate)
        .def_property("config",[](OrderSynth& s){std::lock_guard<std::recursive_mutex> lock(s.mutex);return config_object(s.config);},[](OrderSynth& s,py::object c){s.configure(read_config(c));})
        .def("reset",&OrderSynth::reset).def("resume",&OrderSynth::resume)
        .def("set_parameters",&OrderSynth::set_parameters,py::arg("virtual_rpm"),py::arg("throttle_percent"),py::arg("enabled")=true,py::kw_only(),py::arg("regen_mix")=0.)
        .def("set_driving_controls",&OrderSynth::set_driving_controls)
        .def("pitch_progression",&OrderSynth::pitch_progression)
        .def("spectral_weights",[](OrderSynth& s,Input f){py::array_t<double> out(f.size());for(py::ssize_t i=0;i<f.size();++i)out.mutable_data()[i]=s.spectral_weight(f.data()[i]);return out;})
        .def("render",[](OrderSynth& s,py::ssize_t n){py::array_t<double> out(count(n));{py::gil_scoped_release release;s.render(n,out.mutable_data());}return out;})
        .def_property_readonly("phases",[](OrderSynth& s){std::lock_guard<std::recursive_mutex> lock(s.mutex);return array(s.phases);})
        .def_property_readonly("request",[](OrderSynth& s){std::lock_guard<std::recursive_mutex> lock(s.mutex);return py::make_tuple(s.requested_rpm,s.requested_throttle,s.enabled);})
        .def_property_readonly("driving_controls",[](OrderSynth& s)->py::object{std::lock_guard<std::recursive_mutex> lock(s.mutex);if(!s.driving_controls)return py::none();return py::make_tuple((*s.driving_controls)[0],(*s.driving_controls)[1]);})
#define ORDER_VALUE(name) .def_property_readonly(#name,[](OrderSynth& s){std::lock_guard<std::recursive_mutex> lock(s.mutex);return s.name;})
        ORDER_VALUE(rpm) ORDER_VALUE(throttle) ORDER_VALUE(gain) ORDER_VALUE(regen_mix) ORDER_VALUE(regen_request) ORDER_VALUE(accel_fast) ORDER_VALUE(accel_baseline)
#undef ORDER_VALUE
        ;
    py::class_<Engine>(m,"Engine",py::dynamic_attr())
        .def(py::init([](double sr,py::object c){return std::make_unique<Engine>(rate(sr),read_config(c));}),py::arg("sample_rate")=44100,py::arg("order_config")=py::none())
        .def_readonly("sample_rate",&Engine::sample_rate)
        .def_readonly("order_synth",&Engine::order_synth)
        .def_property_readonly("backend",[](Engine&){return "cpp";})
        .def_static("fundamental_for_rpm",&Engine::fundamental_for_rpm,py::arg("rpm"),py::arg("max_rpm"),py::arg("base_hz")=42.)
        .def("set_parameters",&Engine::set_parameters,py::arg("rpm"),py::arg("max_rpm"),py::arg("drive_power"),py::arg("regen_power"),py::arg("profile"),py::arg("throttle")=0.,py::kw_only(),py::arg("motor_load")=std::nullopt,py::arg("regen_load")=std::nullopt,py::arg("acceleration_m_s2")=0.)
        .def("set_driving_parameters",&Engine::set_driving_parameters,py::arg("speed_kmh"),py::arg("accelerator_percent"),py::arg("signed_motor_load"),py::arg("acceleration_m_s2"),py::arg("operating_state"),py::arg("profile"),py::kw_only(),py::arg("master_volume")=1.,py::arg("sound_enabled")=true)
        .def("set_order_parameters",&Engine::set_order_parameters,py::arg("virtual_rpm"),py::arg("throttle_percent"),py::arg("enabled")=true)
        .def("_reset",&Engine::reset)
        .def("_callback",&callback,py::arg("outdata").noconvert(),py::arg("frames"),py::arg("time"),py::arg("status"))
        .def("start",&Engine::start,py::call_guard<py::gil_scoped_release>())
        .def("stop",&Engine::stop,py::call_guard<py::gil_scoped_release>())
        .def_static("refresh_devices",&Engine::refresh_devices,py::call_guard<py::gil_scoped_release>())
        .def_property_readonly("active",&Engine::active)
        .def_property_readonly("stream",[](Engine& e)->py::object{if(!e.opened())return py::none();return py::cast(&e,py::return_value_policy::reference);})
        .def_property_readonly("params",[](Engine& e){std::lock_guard<std::recursive_mutex> lock(e.mutex);py::tuple out(6);for(int i=0;i<6;++i)out[i]=e.params[i];return out;})
        .def_property_readonly("source",[](Engine& e){std::lock_guard<std::recursive_mutex> lock(e.mutex);py::array_t<double> out({static_cast<py::ssize_t>(2),static_cast<py::ssize_t>(e.source.size()/2)});std::copy(e.source.begin(),e.source.end(),out.mutable_data());return out;})
        .def_property("debug_output",[](Engine& e){std::lock_guard<std::recursive_mutex> lock(e.mutex);return array(e.debug_output);},[](Engine& e,Input samples){vector(samples,4096);for(py::ssize_t i=0;i<4096;++i)if(!std::isfinite(samples.data()[i]))throw py::value_error("Debug samples must be finite.");std::lock_guard<std::recursive_mutex> lock(e.mutex);std::copy_n(samples.data(),4096,e.debug_output.begin());})
        .def_property_readonly("grains",[](Engine& e){std::lock_guard<std::recursive_mutex> lock(e.mutex);return py::list(e.active_grains());})
        .def_property_readonly("render_counts",[](Engine& e){std::lock_guard<std::recursive_mutex> lock(e.mutex);return array(e.render_counts);})
        .def_property("startup_sample",[](Engine& e)->py::object{std::lock_guard<std::recursive_mutex> lock(e.mutex);return e.startup_sample<0?py::object(py::none()):py::object(py::int_(e.startup_sample));},[](Engine& e,py::object v){std::lock_guard<std::recursive_mutex> lock(e.mutex);e.startup_sample=v.is_none()?-1:v.cast<int>();})
#define ENGINE_VALUE(name) .def_property(#name,[](Engine& e){std::lock_guard<std::recursive_mutex> lock(e.mutex);return e.name;},[](Engine& e,decltype(Engine::name) v){std::lock_guard<std::recursive_mutex> lock(e.mutex);e.name=v;})
        ENGINE_VALUE(hz) ENGINE_VALUE(richness) ENGINE_VALUE(drive_level) ENGINE_VALUE(regen_level) ENGINE_VALUE(output_gain)
        ENGINE_VALUE(electric_mix) ENGINE_VALUE(order_mix) ENGINE_VALUE(electric_hz) ENGINE_VALUE(electric_hz_target) ENGINE_VALUE(sound_speed)
        ENGINE_VALUE(order_active) ENGINE_VALUE(debug_enabled) ENGINE_VALUE(operating_state)
#undef ENGINE_VALUE
        .def_property("_order_sleeping",[](Engine& e){std::lock_guard<std::recursive_mutex> lock(e.mutex);return e.order_sleeping;},[](Engine& e,bool v){std::lock_guard<std::recursive_mutex> lock(e.mutex);e.order_sleeping=v;})
        .def_property_readonly("electric_phases",[](Engine& e){std::lock_guard<std::recursive_mutex> lock(e.mutex);return array(e.electric_state.phases);})
        .def_property_readonly("response_target",[](Engine& e){std::lock_guard<std::recursive_mutex> lock(e.mutex);return array(e.response_target);})
        .def_property_readonly("traction_phases",[](Engine& e){std::lock_guard<std::recursive_mutex> lock(e.mutex);return array(e.traction_state.phases);})
        .def_property_readonly("orchestral_phases",[](Engine& e){std::lock_guard<std::recursive_mutex> lock(e.mutex);py::array_t<double> out({3,3});std::copy(e.orchestra_state.phases.begin(),e.orchestra_state.phases.end(),out.mutable_data());return out;})
        .def_property_readonly("traction_morph_phase",[](Engine& e){std::lock_guard<std::recursive_mutex> lock(e.mutex);return e.cycle_state.morph_phase;})
        .def_property_readonly("traction_cycle_phases",[](Engine& e){std::lock_guard<std::recursive_mutex> lock(e.mutex);return array(e.cycle_state.phases);})
        .def_property("traction_cycle_controls",[](Engine& e){std::lock_guard<std::recursive_mutex> lock(e.mutex);return array(e.cycle_state.controls);},[](Engine& e,std::array<double,5> v){std::lock_guard<std::recursive_mutex> lock(e.mutex);e.cycle_state.controls=v;})
        .def_property("traction_cycle_position",[](Engine& e){std::lock_guard<std::recursive_mutex> lock(e.mutex);return e.cycle_state.position;},[](Engine& e,double v){std::lock_guard<std::recursive_mutex> lock(e.mutex);e.cycle_state.position=v;})
#define CYCLE_VALUE(name,index) .def_property(name,[](Engine& e){std::lock_guard<std::recursive_mutex> lock(e.mutex);return e.cycle_target[index];},[](Engine& e,double v){std::lock_guard<std::recursive_mutex> lock(e.mutex);e.cycle_target[index]=v;})
        CYCLE_VALUE("traction_cycle_seconds",0) CYCLE_VALUE("traction_crossfade_seconds",1) CYCLE_VALUE("traction_sweep_hz",2) CYCLE_VALUE("traction_morph_mix",3) CYCLE_VALUE("traction_stage_colour",4)
#undef CYCLE_VALUE
        .def("_render_traction_cycle",[](Engine& e,Input a,Input b,Input c,Input d){const auto n=a.size();for(const auto& input:{a,b,c,d})vector(input,n);py::array_t<double> out(n);{py::gil_scoped_release release;e.render_cycle(a.data(),b.data(),c.data(),d.data(),n,out.mutable_data());}return out;})
        .def_static("traction_stage_weights",[](Input speed){vector(speed,speed.size());py::array_t<double> out({py::ssize_t(4),speed.size()});auto o=out.mutable_unchecked<2>();for(py::ssize_t j=0;j<speed.size();++j){double c[3];const double starts[]={18.,55.,95.},widths[]={24.,30.,40.};for(int i=0;i<3;++i){double t=std::clamp((speed.data()[j]-starts[i])/widths[i],0.,1.);c[i]=t*t*(3-2*t);}o(0,j)=1-c[0];o(1,j)=c[0]-c[1];o(2,j)=c[1]-c[2];o(3,j)=c[2];}return out;})
        .def_static("traction_cycle_envelopes",[](Input positions,double overlap){vector(positions,positions.size());if(!std::isfinite(overlap)||overlap<=0)throw py::value_error("Overlap must be positive.");py::array_t<double> ages({py::ssize_t(2),positions.size()}),weights({py::ssize_t(2),positions.size()});auto a=ages.mutable_unchecked<2>();auto w=weights.mutable_unchecked<2>();for(int i=0;i<2;++i)for(py::ssize_t j=0;j<positions.size();++j){a(i,j)=std::fmod(std::fmod(positions.data()[j]-i,2.)+2.,2.);double fi=std::clamp(a(i,j)/overlap,0.,1.),fo=std::clamp((a(i,j)-1)/overlap,0.,1.);fi=fi*fi*fi*(fi*(6*fi-15)+10);fo=fo*fo*fo*(fo*(6*fo-15)+10);w(i,j)=std::sin(.5*pi*fi)*std::cos(.5*pi*fo);if(a(i,j)>=1+overlap||(i==1&&positions.data()[j]<1))w(i,j)=0.;}return py::make_tuple(ages,weights);})
        ;
}
