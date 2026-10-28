#pragma once

#include <atomic>
#include <functional>
#include <string>

namespace evsound {
namespace detail { struct CallbackTimeInfo; }

struct OutputDevice {
    int index;
    int sample_rate;
    int channels;
    std::string name;
};

// Control methods must be called from one owner thread, never the audio callback.
class Output {
public:
    using Callback = std::function<void(float*, unsigned long, int)>;
    Output() = default;
    Output(const Output&) = delete;
    Output& operator=(const Output&) = delete;
    ~Output() noexcept;
    static void set_library(const std::string& path);
    static OutputDevice default_device();
    static void refresh_devices();
    void start(const OutputDevice& device, Callback callback);
    void stop();
    bool active() const;
    bool opened() const;
private:
    static int render(const void*, void*, unsigned long, const detail::CallbackTimeInfo*, unsigned long, void*) noexcept;
    void* stream_ = nullptr;
    Callback callback_;
    int channels_ = 0;
    std::atomic<bool> callback_failed_{false};
};

} // namespace evsound
