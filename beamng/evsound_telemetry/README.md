# EV Sound Lab BeamNG telemetry mod

Development mod for BeamNG.drive 0.32+. Copy `evsound_telemetry` into the BeamNG user folder's `mods/unpacked/` directory. Enable **EV Sound Lab telemetry** under **Options → Other → Protocols**, then reload the vehicle with **Ctrl+R**. Start the listener on the mod's port:

```powershell
py .\tools\beamng_outgauge_listener.py --port 4445
```

BeamNG's protocol manager sends fixed-layout `EVS1` binary packets to `127.0.0.1:4445` at up to 30 Hz. Listener prints speed, pedals, and candidate EV electrics. `None` means field unavailable on this vehicle; values remain raw and need in-game validation. The mod follows BeamNG's `getAddress`, `getPort`, `getMaxUpdateRate`, `getStructDefinition`, and `fillStruct` protocol interface. No vehicle physics is changed.
