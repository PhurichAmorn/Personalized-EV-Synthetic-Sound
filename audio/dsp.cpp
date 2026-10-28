#include "dsp.h"
#include <algorithm>
#include <cmath>

namespace evsound {
namespace {
static inline double clamp01(double x) { return std::min(1.0, std::max(0.0, x)); }
static inline double fade(double f, double sr) {
    return clamp01((.48 * sr - f) / (.06 * sr));
}
static inline double smoothstep(double x) {
    x = clamp01(x);
    return x * x * (3.0 - 2.0 * x);
}

}

void electric(const double* h,const double* d,const double* q,const Colours& c,
              ElectricState& state,double sr,std::size_t n,double* m,double* r) {
    if (n == 0) return;
    auto phase = state.phases;
    double pulse_phase = state.motion;
    for (std::size_t j = 0; j < n; ++j) {
        const double base = h[j], growl = c[5][j], cutoff = c[1][j];
        pulse_phase += 2 * pi * (2.5 + .012 * base) / sr;
        const std::array<double, 7> f = {
            .5 * base, base, (1 + c[2][j]) * base,
            (1.94 + .06 * growl) * base, (2.9 + .10 * growl) * base,
            (4.1 + .28 * c[8][j] * std::sin(pulse_phase)) * base, 5.15 * base};
        const double colour = std::min(3.0, std::max(0.0, q[j] / .30));
        std::array<double, 7> w = {.14, .36, .045, .16, .055, 0., 0.};
        w[0] = c[0][j]; w[5] = .22 * c[8][j] + .30 * c[10][j]; w[6] = .20 * c[10][j];
        std::array<double, 7> rw = {.16, .28, .025, .10, .02, 0., 0.};
        rw[0] = c[0][j] * (.16 / .14);
        double original_energy = 0, changed_energy = 0, motor_sample = 0, regen_sample = 0;
        std::array<double, 7> bands{};
        for (int i = 0; i < 7; ++i) {
            phase[i] += 2 * pi * f[i] / sr;
            double band = fade(f[i], sr) / (1 + std::pow(f[i] / cutoff, 4));
            if (i >= 5) band /= 1 + std::pow(f[i] / 1200., 6);
            bands[i] = band;
            if (i >= 3) w[i] *= 1 + colour - 1;
            const double load = (i == 3 ? .08 : (i == 4 ? .065 : 0.))
                              * d[j] * colour * c[3][j];
            motor_sample += (w[i] + load) * band * std::sin(phase[i]);
            original_energy += std::pow(rw[i] * band, 2);
            double varied = rw[i];
            if (i == 0) varied *= 1 + .10 * c[6][j];
            if (i == 1) varied *= 1 - .15 * c[6][j];
            if (i == 3) varied += .09 * c[6][j];
            if (i == 4) varied += .035 * c[6][j];
            changed_energy += std::pow(varied * band, 2);
            rw[i] = varied;
        }
        const double renorm = std::sqrt(original_energy / std::max(changed_energy, 1e-20));
        for (int i = 0; i < 7; ++i) regen_sample += rw[i] * renorm * bands[i] * std::sin(phase[i]);
        const double pulse = 1 - .36 * c[9][j] * (1 - std::cos(pulse_phase));
        motor_sample *= pulse / std::sqrt(1 - .72 * c[9][j] + .1944 * c[9][j] * c[9][j]);
        m[j] = motor_sample;
        r[j] = regen_sample * c[4][j] / .45;
    }
    for (int i = 0; i < 7; ++i) state.phases[i] = std::fmod(phase[i], 2 * pi);
    state.motion = std::fmod(pulse_phase, 2 * pi);
}

void orchestra(const double* h,const double* co,const double* q,OrchestraState& state,
               double sr,std::size_t n,double* o) {
    if (n == 0) return;
    std::fill_n(o, n, 0.);
    const double notes[3] = {1., 1.5, 2.};
    const double tuning[3] = {.9965, 1., 1.0038};
    const double offsets[3][3] = {{0., .7, 1.4}, {.4, 1.1, 1.8}, {.8, 1.5, 2.2}};
    const double row_weight[3] = {.52, .28, .20};
    const double voice_weight[3] = {.25, .50, .25};
    for (int a = 0; a < 3; ++a) for (int b = 0; b < 3; ++b) {
        double phase = state.phases[3 * a + b];
        for (std::size_t j = 0; j < n; ++j) {
            const double f = h[j] * notes[a] * tuning[b];
            phase += 2 * pi * f / sr;
            double voice = 0;
            const int harmonics[5] = {1, 2, 3, 4, 5};
            const double amplitudes[5] = {.50, .20, .09, .04, .018};
            for (int k = 0; k < 5; ++k) {
                const double harmonic = harmonics[k], hf = harmonic * f;
                const double band = fade(hf, sr) / (1 + std::pow(hf / co[j], 4));
                double amp = amplitudes[k];
                if (k == 1) amp += .08 * q[j];
                if (k == 2) amp += .05 * q[j];
                voice += amp * band * std::sin(harmonic * (phase + offsets[a][b]));
            }
            o[j] += .70 * row_weight[a] * voice_weight[b] * voice;
        }
        state.phases[3 * a + b] = std::fmod(phase, 2 * pi);
    }
}

void traction(const double* s,const double* h,const double* co,const double* q,
              TractionState& state,double sr,std::size_t n,double* o) {
    if (n == 0) return;
    std::fill_n(o, n, 0.);
    const double bases[4] = {125., 155., 185., 215.};
    const double spans[4] = {165., 175., 165., 90.};
    const double starts[4] = {0., 25., 60., 105.};
    const double widths[4] = {50., 60., 80., 100.};
    auto phase = state.phases;
    for (std::size_t j = 0; j < n; ++j) {
        double crossings[3];
        const double thresholds[3] = {18., 55., 95.}, widths_c[3] = {24., 30., 40.};
        for (int i = 0; i < 3; ++i) crossings[i] = smoothstep((s[j] - thresholds[i]) / widths_c[i]);
        const double weights[4] = {1 - crossings[0], crossings[0] - crossings[1],
                                   crossings[1] - crossings[2], crossings[2]};
        for (int i = 0; i < 4; ++i) {
            const double progress = clamp01((s[j] - starts[i]) / widths[i]);
            const double f = (bases[i] + spans[i] * progress) * h[j] / 90.;
            phase[i] += 2 * pi * f / sr;
            const double b1 = fade(f, sr) / (1 + std::pow(f / co[j], 4));
            const double f2 = 2 * f;
            const double b2 = fade(f2, sr) / (1 + std::pow(f2 / co[j], 4));
            const double voice = b1 * std::sin(phase[i]) + (.08 + .20 * q[j]) * b2 * std::sin(2 * phase[i]);
            o[j] += .70 * weights[i] * voice;
        }
    }
    for (int i = 0; i < 4; ++i) state.phases[i] = std::fmod(phase[i], 2 * pi);
}

void traction_cycle(const double* rt,const double* h,const double* co,const double* q,
                    const std::array<double,5>& target,CycleState& state,double sr,std::size_t n,double* o) {
    if (n == 0) return;
    const auto initial = state.controls;
    auto control = initial;
    double phase[3] = {state.phases[0], state.phases[1], state.morph_phase};
    double position = state.position;
    for (std::size_t j = 0; j < n; ++j) {
        const double alpha = std::exp(-(j + 1.) / (.30 * sr));
        for (int i = 0; i < 5; ++i) control[i] = target[i] + (initial[i] - target[i]) * alpha;
        const double seconds = control[0], overlap = control[1] / seconds;
        position += rt[j] / (seconds * sr);
        double age[2]; double weights[2];
        for (int i = 0; i < 2; ++i) {
            age[i] = std::fmod(position - i + 2., 2.);
            double fi = clamp01(age[i] / overlap), fo = clamp01((age[i] - 1.) / overlap);
            fi = fi * fi * fi * (fi * (6 * fi - 15) + 10);
            fo = fo * fo * fo * (fo * (6 * fo - 15) + 10);
            weights[i] = std::sin(.5 * pi * fi) * std::cos(.5 * pi * fo);
            if (age[i] >= 1 + overlap || (i == 1 && position < 1)) weights[i] = 0;
        }
        double frequencies[2];
        for (int i = 0; i < 2; ++i) {
            const double rise = smoothstep(age[i]);
            frequencies[i] = (130 + control[2] * rise) * h[j] / 90.;
        }
        const double power[2] = {weights[0] * weights[0], weights[1] * weights[1]};
        const double total = power[0] + power[1];
        const double merged = (power[0] * frequencies[0] + power[1] * frequencies[1]) / std::max(total, 1e-20);
        frequencies[0] = frequencies[0]; frequencies[1] = frequencies[1];
        const double f[3] = {frequencies[0], frequencies[1], merged};
        double voice[3] = {0., 0., 0.};
        for (int i = 0; i < 3; ++i) {
            phase[i] += 2 * pi * f[i] / sr;
            for (int harmonic = 1; harmonic <= 3; ++harmonic) {
                double amp = harmonic == 1 ? 1. : (harmonic == 2 ? .08 + .20 * q[j] : 1.);
                const double hf = harmonic * f[i];
                double band = fade(hf, sr) / (1 + std::pow(hf / co[j], 4));
                if (harmonic == 2 && i == 1) band *= 1 + .70 * control[4];
                if (harmonic == 3) band *= (i == 0 ? .03 : (i == 1 ? .22 : 0.)) * control[4];
                voice[i] += amp * band * std::sin(harmonic * phase[i]);
            }
        }
        const double separate = weights[0] * voice[0] + weights[1] * voice[1];
        const double merged_voice = std::sqrt(total) * voice[2];
        o[j] = .55 * ((1 - control[3]) * separate + control[3] * merged_voice);
    }
    state.controls = control;
    state.position = position;
    state.phases[0] = std::fmod(phase[0], 2 * pi);
    state.phases[1] = std::fmod(phase[1], 2 * pi);
    state.morph_phase = std::fmod(phase[2], 2 * pi);
}
}
