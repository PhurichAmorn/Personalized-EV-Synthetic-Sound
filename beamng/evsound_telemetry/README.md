# EV Sound Lab BeamNG telemetry mod

Development mod for BeamNG.drive 0.32+. Copy `evsound_telemetry` into the BeamNG user folder's `mods/unpacked/` directory. Enable the custom protocol under **Options → Other → Protocols**, then reload the vehicle with **Ctrl+R**. Start the listener on the mod's default port:

```powershell
py .\tools\beamng_outgauge_listener.py --port 4445
```

The protocol emits `EVSL1` text packets at up to 30 Hz to `127.0.0.1:4445`. It reports speed and whichever listed electrics exist on the current vehicle. These names are exploratory; values are raw game signals and not yet verified as motor torque or regeneration. No vehicle physics is changed.
