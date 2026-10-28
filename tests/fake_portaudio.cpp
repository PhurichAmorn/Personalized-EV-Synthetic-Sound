// Standalone PortAudio lifecycle fixture; no hardware or Python required.
#include <algorithm>
#include <cassert>
#include <cstdlib>

extern "C" {
struct DeviceInfo { int version; const char* name; int api, inputs, outputs; double lowIn, lowOut, highIn, highOut, rate; };
struct Parameters { int device, channels; unsigned long format; double latency; void* extra; };
struct TimeInfo { double input, current, output; };
using Callback = int (*)(const void*, void*, unsigned long, const TimeInfo*, unsigned long, void*);
static DeviceInfo device{2, "Fake output", 0, 0, 2, 0, .01, 0, .1, 48000};
static Callback callback;
static void* userdata;
static bool open = false, active = false;
static int channels;
int Pa_Initialize() { return 0; }
int Pa_Terminate() { assert(!open); return 0; }
int Pa_GetDefaultOutputDevice() { return std::getenv("FAKE_NO_DEVICE") ? -1 : 0; }
const DeviceInfo* Pa_GetDeviceInfo(int index) { return index == 0 ? &device : nullptr; }
const char* Pa_GetErrorText(int) { return "fake error"; }
int Pa_OpenStream(void** stream, const Parameters* input, const Parameters* output, double rate,
                  unsigned long frames, unsigned long flags, Callback cb, void* user) {
    assert(!open && !input && output->format == 1 && rate == 48000 && frames == 512 && flags == 0);
    channels = output->channels; callback = cb; userdata = user; open = true; *stream = &device; return 0;
}
int Pa_StartStream(void*) {
    if (std::getenv("FAKE_START_FAIL")) return -1;
    float buffer[1024]; std::fill_n(buffer, 1024, 10.f);
    const int result = callback(nullptr, buffer, 512, nullptr, 0, userdata);
    if (result == 2) for (int i = 0; i < 512 * channels; ++i) assert(buffer[i] == 0);
    active = result == 0; return 0;
}
int Pa_StopStream(void*) { active = false; return std::getenv("FAKE_STOP_FAIL") ? -1 : 0; }
int Pa_CloseStream(void*) { assert(open); open = false; return 0; }
int Pa_IsStreamActive(void*) { return active ? 1 : 0; }
}
