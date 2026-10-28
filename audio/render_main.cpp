#include "engine.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

namespace {
double number(const char* text) {
    std::size_t end = 0;
    const std::string value(text);
    const double result = std::stod(value, &end);
    if (end != value.size() || !std::isfinite(result))
        throw std::invalid_argument("Expected a finite number");
    return result;
}
void little_endian(std::ostream& file, std::uint32_t value, int bytes) {
    for (int i = 0; i < bytes; ++i) file.put(static_cast<char>((value >> (8 * i)) & 255));
}
} // namespace

int main(int argc, char** argv) {
    if (argc < 2 || argc > 5) {
        std::cerr << "Usage: evsound_render output.wav [Comfort|Sport|Deep|debug name] [seconds] [sample_rate]\n";
        return 1;
    }
    try {
        const std::string theme = argc > 2 ? argv[2] : "Comfort";
        const double seconds = argc > 3 ? number(argv[3]) : 5.;
        const double rate = argc > 4 ? number(argv[4]) : 44100.;
        if (seconds <= 0 || seconds > 600)
            throw std::invalid_argument("Duration must be greater than 0 and at most 600 seconds");
        if (rate < 8000 || rate > 192000 || rate != std::floor(rate))
            throw std::invalid_argument("Sample rate must be an integer from 8000 to 192000");
        const auto frames = static_cast<std::uint64_t>(std::llround(seconds * rate));
        if (!frames || frames > (std::numeric_limits<std::uint32_t>::max() - 36ULL) / 4)
            throw std::invalid_argument("Duration does not fit a PCM16 stereo RIFF file");
        const evsound::Profile* profile = nullptr;
        const auto& themes = evsound::sound_themes();
        const auto& debug = evsound::debug_themes();
        auto match = themes.find(theme);
        if (match != themes.end()) profile = &match->second;
        else {
            auto debug_match = debug.find(theme);
            if (debug_match != debug.end()) profile = &debug_match->second;
        }
        if (!profile) throw std::invalid_argument("Unknown sound theme: " + theme);
        evsound::Engine engine(static_cast<int>(rate));
        engine.prepare(512);
        engine.set_driving_parameters(80., 70., .7, 3., "ready", *profile);
        std::ofstream file;
        file.exceptions(std::ios::badbit | std::ios::failbit);
        file.open(argv[1], std::ios::binary | std::ios::trunc);
        const auto data_bytes = static_cast<std::uint32_t>(frames * 4);
        file.write("RIFF", 4); little_endian(file, 36 + data_bytes, 4);
        file.write("WAVEfmt ", 8); little_endian(file, 16, 4);
        little_endian(file, 1, 2); little_endian(file, 2, 2);
        little_endian(file, static_cast<std::uint32_t>(rate), 4);
        little_endian(file, static_cast<std::uint32_t>(rate) * 4, 4);
        little_endian(file, 4, 2); little_endian(file, 16, 2);
        file.write("data", 4); little_endian(file, data_bytes, 4);
        std::array<float, 1024> buffer{};
        for (std::uint64_t position = 0; position < frames;) {
            const auto count = static_cast<std::size_t>(std::min<std::uint64_t>(512, frames - position));
            engine.render(buffer.data(), count, 2);
            for (std::size_t i = 0; i < count * 2; ++i) {
                if (!std::isfinite(buffer[i])) throw std::runtime_error("Renderer produced a non-finite sample");
                const auto sample = static_cast<std::int16_t>(std::lround(std::clamp(buffer[i], -1.f, 1.f) * 32767.f));
                little_endian(file, static_cast<std::uint16_t>(sample), 2);
            }
            position += count;
        }
        file.close();
        std::cout << "Wrote " << argv[1] << ": " << frames << " frames, " << static_cast<int>(rate) << " Hz, " << theme << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "evsound_render: " << error.what() << '\n';
        return 1;
    }
}
