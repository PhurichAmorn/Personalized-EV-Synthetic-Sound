#include "output.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <limits>
#include <mutex>
#include <stdexcept>
#include <utility>
#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#endif

namespace evsound {
namespace detail {
struct CallbackTimeInfo { double inputBufferAdcTime, currentTime, outputBufferDacTime; };
}
namespace {
// PortAudio v19 public C ABI. Sample formats and stream flags are unsigned long.
struct DeviceInfo {
    int structVersion;
    const char* name;
    int hostApi, maxInputChannels, maxOutputChannels;
    double defaultLowInputLatency, defaultLowOutputLatency;
    double defaultHighInputLatency, defaultHighOutputLatency, defaultSampleRate;
};
struct Parameters {
    int device, channelCount;
    unsigned long sampleFormat;
    double suggestedLatency;
    void* hostApiSpecificStreamInfo;
};
using Render = int (*)(const void*, void*, unsigned long, const detail::CallbackTimeInfo*, unsigned long, void*);
struct Runtime {
    std::mutex mutex;
    void* library = nullptr;
    std::string path;
    bool initialized = false;
    unsigned streams = 0;
    int (*initialize)() = nullptr;
    int (*terminate)() = nullptr;
    int (*default_output)() = nullptr;
    const DeviceInfo* (*device_info)(int) = nullptr;
    const char* (*error_text)(int) = nullptr;
    int (*open)(void**, const Parameters*, const Parameters*, double, unsigned long,
                unsigned long, Render, void*) = nullptr;
    int (*start)(void*) = nullptr;
    int (*stop)(void*) = nullptr;
    int (*close)(void*) = nullptr;
    int (*active)(void*) = nullptr;

    void check(int code, const char* operation) const {
        if (code < 0) {
            const char* detail = error_text ? error_text(code) : nullptr;
            throw std::runtime_error(std::string(operation) + ": " + (detail ? detail : "PortAudio error"));
        }
    }
    template<class T> void symbol(T& target, const char* name) {
#ifdef _WIN32
        target = reinterpret_cast<T>(GetProcAddress(static_cast<HMODULE>(library), name));
#else
        target = reinterpret_cast<T>(dlsym(library, name));
#endif
        if (!target) throw std::runtime_error(std::string("Missing PortAudio symbol: ") + name);
    }
    void load() {
        if (!library) {
            const char* env = std::getenv("EV_SOUND_PORTAUDIO_LIBRARY");
            const std::string selected = !path.empty() ? path : (env ? env : "");
#ifdef _WIN32
            const char* names[] = {"portaudio.dll", "libportaudio64bit.dll", "libportaudio32bit.dll"};
            auto attempt = [&](const char* name) { return reinterpret_cast<void*>(LoadLibraryA(name)); };
#elif defined(__APPLE__)
            const char* names[] = {"libportaudio.2.dylib", "libportaudio.dylib", "/opt/homebrew/lib/libportaudio.dylib", "/usr/local/lib/libportaudio.dylib"};
            auto attempt = [&](const char* name) { return dlopen(name, RTLD_NOW | RTLD_LOCAL); };
#else
            const char* names[] = {"libportaudio.so.2", "libportaudio.so"};
            auto attempt = [&](const char* name) { return dlopen(name, RTLD_NOW | RTLD_LOCAL); };
#endif
            if (!selected.empty()) library = attempt(selected.c_str());
            else for (const char* name : names) if ((library = attempt(name))) break;
            if (!library) throw std::runtime_error("Cannot load PortAudio runtime: " + selected);
        }
        // Resolve again after a missing-symbol error; never use a partially loaded API.
        symbol(initialize, "Pa_Initialize"); symbol(terminate, "Pa_Terminate");
        symbol(default_output, "Pa_GetDefaultOutputDevice"); symbol(device_info, "Pa_GetDeviceInfo");
        symbol(error_text, "Pa_GetErrorText"); symbol(open, "Pa_OpenStream");
        symbol(start, "Pa_StartStream"); symbol(stop, "Pa_StopStream");
        symbol(close, "Pa_CloseStream"); symbol(active, "Pa_IsStreamActive");
        if (!initialized) { check(initialize(), "Pa_Initialize"); initialized = true; }
    }
};
// Keep library loaded for process lifetime; PortAudio can also be used by sounddevice.
Runtime& runtime() { static Runtime value; return value; }
const DeviceInfo& info(Runtime& r, int index) {
    const auto* value = r.device_info(index);
    if (!value || value->structVersion != 2 || value->maxOutputChannels < 1 ||
        !std::isfinite(value->defaultSampleRate) || value->defaultSampleRate < 1 ||
        value->defaultSampleRate > std::numeric_limits<int>::max())
        throw std::runtime_error("No usable PortAudio output device");
    return *value;
}
} // namespace

void Output::set_library(const std::string& path) {
    auto& r = runtime(); std::lock_guard<std::mutex> lock(r.mutex);
    if (r.library && path != r.path) throw std::runtime_error("PortAudio library already loaded");
    r.path = path;
}
OutputDevice Output::default_device() {
    auto& r = runtime(); std::lock_guard<std::mutex> lock(r.mutex); r.load();
    const int index = r.default_output();
    if (index < 0) throw std::runtime_error("No default PortAudio output device");
    const auto& d = info(r, index);
    return {index, static_cast<int>(std::lround(d.defaultSampleRate)), std::min(2, d.maxOutputChannels), d.name ? d.name : ""};
}
void Output::refresh_devices() {
    auto& r = runtime(); std::lock_guard<std::mutex> lock(r.mutex);
    if (r.streams) throw std::runtime_error("Close all output streams before refreshing devices");
    if (r.initialized) { r.check(r.terminate(), "Pa_Terminate"); r.initialized = false; }
    r.load();
}
int Output::render(const void*, void* output, unsigned long frames, const detail::CallbackTimeInfo*, unsigned long, void* user) noexcept {
    auto& self = *static_cast<Output*>(user);
    auto* samples = static_cast<float*>(output);
    if (!samples) { self.callback_failed_.store(true); return 2; }
    try {
        if (self.callback_failed_.load()) throw 0;
        self.callback_(samples, frames, self.channels_);
        return 0;
    } catch (...) {
        std::fill_n(samples, frames * static_cast<unsigned long>(self.channels_), 0.0f);
        self.callback_failed_.store(true);
        return 2; // paAbort; no exception may cross the C callback boundary.
    }
}
void Output::start(const OutputDevice& device, Callback callback) {
    if (!callback) throw std::invalid_argument("Output callback is empty");
    stop();
    auto& r = runtime(); std::lock_guard<std::mutex> lock(r.mutex); r.load();
    const auto& d = info(r, device.index);
    if (device.sample_rate < 1 || device.channels < 1 || device.channels > 2 || device.channels > d.maxOutputChannels)
        throw std::invalid_argument("Invalid output sample rate or channel count");
    if (!std::isfinite(d.defaultLowOutputLatency) || d.defaultLowOutputLatency < 0)
        throw std::runtime_error("Invalid PortAudio output latency");
    channels_ = device.channels; callback_ = std::move(callback); callback_failed_.store(false);
    Parameters parameters{device.index, channels_, 1UL, d.defaultLowOutputLatency, nullptr};
    int result = r.open(&stream_, nullptr, &parameters, device.sample_rate, 512, 0, &Output::render, this);
    if (result >= 0 && stream_) result = r.start(stream_);
    else if (result >= 0) result = -9988; // paBadStreamPtr
    if (result < 0) {
        if (stream_) r.close(stream_);
        stream_ = nullptr; callback_ = {};
        r.check(result, "Start output stream");
    }
    ++r.streams;
}
void Output::stop() {
    auto& r = runtime(); std::lock_guard<std::mutex> lock(r.mutex);
    if (!stream_) return;
    const int stopped = r.stop(stream_);
    const int closed = r.close(stream_);
    stream_ = nullptr; callback_ = {}; --r.streams;
    // paStreamIsStopped is normal after a callback abort.
    if (stopped != -9983) r.check(stopped, "Pa_StopStream");
    r.check(closed, "Pa_CloseStream");
}
bool Output::active() const {
    if (callback_failed_.load()) throw std::runtime_error("Native audio callback failed");
    auto& r = runtime(); std::lock_guard<std::mutex> lock(r.mutex);
    if (!stream_) return false;
    const int result = r.active(stream_); r.check(result, "Pa_IsStreamActive");
    return result != 0;
}
bool Output::opened() const { auto& r = runtime(); std::lock_guard<std::mutex> lock(r.mutex); return stream_ != nullptr; }
Output::~Output() noexcept { try { stop(); } catch (...) {} }
} // namespace evsound
