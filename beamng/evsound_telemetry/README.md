# EV Sound Lab BeamNG telemetry mod

Development mod for BeamNG.drive 0.32+. Copy `evsound_telemetry` into the BeamNG user folder's `mods/unpacked/` directory. Enable **EV Sound Lab telemetry** under **Options → Other → Protocols**, then reload the vehicle with **Ctrl+R**. Start EV Sound Lab and select **BeamNG** as the telemetry source. The app receives on `127.0.0.1:4445` while its sidecar runs.

For packet inspection without the app, run the standalone listener:

```powershell
py .\tools\beamng_outgauge_listener.py --port 4445
```

BeamNG's protocol manager sends fixed-layout `EVS1` binary packets to `127.0.0.1:4445` at up to 30 Hz. The app maps speed, throttle, brake, regen, and signed motor load into its sound engine. `None` means field unavailable on this vehicle; values remain raw and need in-game validation. The mod follows BeamNG's `getAddress`, `getPort`, `getMaxUpdateRate`, `getStructDefinition`, and `fillStruct` protocol interface. No vehicle physics is changed.

BeamNG drivetrain audio is not muted by this mod. Stock and synthesized drivetrain sounds may overlap; target-vehicle-only muting needs a verified sound blend hook before it can be automated. The app fades its own sound when telemetry goes stale. The overlay and app sound are separate from BeamNG's audio mix.
