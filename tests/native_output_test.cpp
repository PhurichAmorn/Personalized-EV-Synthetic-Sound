#include "../audio/output.h"
#include <cassert>
#include <cstdlib>
#include <stdexcept>

static void environment(const char* key, bool enabled) {
#ifdef _WIN32
    _putenv_s(key, enabled ? "1" : "");
#else
    if (enabled) setenv(key, "1", 1); else unsetenv(key);
#endif
}
template<class Function> void fails(Function function) {
    bool failed = false;
    try { function(); } catch (const std::exception&) { failed = true; }
    assert(failed);
}
int main(int argc, char** argv) {
    assert(argc == 2);
    evsound::Output::set_library(argv[1]);
    auto device = evsound::Output::default_device();
    assert(device.sample_rate == 48000 && device.channels == 2 && device.index == 0);
    evsound::Output output;
    auto render = [](float* data, unsigned long frames, int channels) {
        for (unsigned long i = 0; i < frames * channels; ++i) data[i] = .1f;
    };
    output.start(device, render);
    assert(output.opened() && output.active());
    fails([] { evsound::Output::refresh_devices(); });
    environment("FAKE_STOP_FAIL", true);
    fails([&] { output.stop(); });
    assert(!output.opened());
    environment("FAKE_STOP_FAIL", false);
    evsound::Output::refresh_devices();
    environment("FAKE_START_FAIL", true);
    fails([&] { output.start(device, render); });
    assert(!output.opened());
    environment("FAKE_START_FAIL", false);
    output.start(device, [](float*, unsigned long, int) { throw std::runtime_error("callback"); });
    fails([&] { output.active(); });
    output.stop();
    environment("FAKE_NO_DEVICE", true);
    fails([] { evsound::Output::default_device(); });
    environment("FAKE_NO_DEVICE", false);
    { evsound::Output scoped; scoped.start(device, render); environment("FAKE_STOP_FAIL", true); }
    environment("FAKE_STOP_FAIL", false);
    evsound::Output::refresh_devices();
}
