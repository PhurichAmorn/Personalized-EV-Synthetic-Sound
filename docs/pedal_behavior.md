# Pedal and regeneration behavior

The dashboard exposes **Compact EV** and **Performance EV** only. Their propulsion specifications derive from the internal Honda e and Model 3 Performance reference configurations. All four manufacturer configurations remain available to Python callers through `VehicleModel.from_name`; `SIMULATOR_PRESETS` is the dashboard allowlist. Neutral names do not imply legal clearance or OEM calibration.

## Normal two-pedal driving

At road speeds above 7.2 km/h, accelerator position maps to:

- 0–8%: progressively less regenerative braking as the pedal increases.
- 8–12%: zero requested motor torque (coasting).
- 12–100%: progressively increasing positive torque, reaching the existing available torque at full pedal.

The boundaries shrink with speed below 7.2 km/h and disappear at standstill, permitting a light-pedal launch. Existing controller deadzone and raw pedal visualization are unchanged. Torque follows the existing 80 ms response, crossing zero continuously on ordinary pedal changes. Thus actual regeneration starts after positive torque crosses zero, rather than instantly reversing torque.

Full lift-off requests motor braking equivalent to **0.03 g in addition to rolling resistance and aerodynamic drag**. This is a simulator comfort calibration, not a measured manufacturer pedal map. Low-speed regeneration fades smoothly; no lift-off friction braking, creep, stop-hold, or one-pedal stopping feature is added. Passive road resistance can still bring the forward-only model to rest.

## Service brake and limits

The brake blends from the current accelerator-derived braking demand toward the existing full-brake target. It overrides positive propulsion immediately. Available regeneration supplies part of the requested braking and friction supplies the remainder. Maximum stopping calibration is unchanged.

Regeneration remains subject to generator torque/power limits, battery SOC/temperature/charge acceptance, tire grip and low-speed fade. Limited lift-off regen is not replaced with friction braking; limited service-brake regen is. Shaft RPM remains mechanically tied to road speed and gear ratio in drive, coast and regeneration. Net battery charging also depends on drivetrain losses and auxiliary demand.

## Method references

- [BMW i3: accelerator neutral position and coasting](https://www.press.bmwgroup.com/united-kingdom/article/detail/T0144135EN_GB/the-new-bmw-i3-%E2%80%93-born-to-be-electric?showMedia=photo)
- [Porsche Taycan powertrain: coasting and brake regeneration](https://newsroom.porsche.com/en/products/taycan/powertrain-18555.html)
- [van Boekel et al. (2015): speed-dependent pedal regions](https://doi.org/10.3390/wevj7020226)

These sources support the control concepts, not the chosen 8/12% boundaries or 0.03 g setting. Original manufacturer reference configurations retain their earlier lift-off calibration for internal comparisons.
