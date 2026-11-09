-- BeamNG custom protocol interface, following lua/vehicle/protocols/outgauge.lua.
local M = {}
local rearMotor

local function init()
  rearMotor = powertrain.getDevice("rearMotor")
end

-- Mute BeamNG's low-speed pedestrian warning (the "avas" controller) so it does not play over EV Sound Lab.
-- The controller keeps its sounds in locals, so we find the module, silence its per-frame update and call its
-- own reset() to stop what is playing. Written defensively: any failure leaves the telemetry untouched.
local avasMuted = false
local avasAttempts = 0
local function isAvas(c)
  if type(c) ~= "table" or type(c.updateGFX) ~= "function" then return false end
  local ok, info = pcall(debug.getinfo, c.updateGFX, "S")
  return ok and info and type(info.source) == "string" and info.source:lower():find("avas", 1, true) ~= nil
end
local function muteAvas()
  avasAttempts = avasAttempts + 1
  local found
  pcall(function()
    local named = controller.getController and controller.getController("avas")
    if isAvas(named) then found = named return end
    for _, kind in ipairs({"auxiliary", "main"}) do
      local list = controller.getControllersByType and controller.getControllersByType(kind)
      for _, c in pairs(list or {}) do
        if isAvas(c) then found = c return end
      end
    end
  end)
  if found then
    pcall(function() if found.reset then found.reset() end end)
    found.updateGFX = function() end
    avasMuted = true
    log("I", "evsound", "Muted the AVAS pedestrian warning controller")
  elseif avasAttempts >= 120 then
    avasMuted = true  -- about 4 s at 30 Hz: no AVAS controller on this vehicle
    log("I", "evsound", "No AVAS controller found on this vehicle")
  end
end
local function getAddress() return "127.0.0.1" end
local function getPort() return 4445 end
local function getMaxUpdateRate() return 30 end
local function isPhysicsStepUsed() return false end
local function getStructDefinition()
  return [[
    char marker[4];
    float speed;
    float throttle;
    float brake;
    float rpm;
    float motorRPM;
    float motorTorque;
    float motorPower;
    float regen;
    float regenTorque;
    float regenPower;
    float motorLoad;
    float watts;
  ]]
end
local function fillStruct(o, dtSim)
  if not avasMuted then muteAvas() end
  local e = electrics.values
  rearMotor = rearMotor or powertrain.getDevice("rearMotor")
  o.marker = "EVS1"
  o.speed = e.wheelspeed or e.airspeed or 0
  o.throttle = e.throttle or 0
  o.brake = e.brake or 0
  o.rpm = e.rpm or 0
  o.motorRPM = rearMotor and (rearMotor.outputRPM or 0) or -999999
  o.motorTorque = rearMotor and (rearMotor.outputTorque1 or 0) or -999999
  o.motorPower = rearMotor and (rearMotor.outputTorque1 or 0) * (rearMotor.outputAV1 or 0) or -999999
  o.regen = rearMotor and (rearMotor.regenThrottle or 0) or -999999
  o.regenTorque = rearMotor and (rearMotor.outputTorque1 < 0 and rearMotor.outputTorque1 or 0) or -999999
  o.regenPower = rearMotor and (rearMotor.outputTorque1 < 0 and (rearMotor.outputTorque1 * rearMotor.outputAV1) or 0) or -999999
  o.motorLoad = rearMotor and (rearMotor.instantEngineLoad or 0) or -999999
  o.watts = -999999
end
M.init = init
M.reset = function() end
M.getAddress = getAddress
M.getPort = getPort
M.getMaxUpdateRate = getMaxUpdateRate
M.getStructDefinition = getStructDefinition
M.fillStruct = fillStruct
M.isPhysicsStepUsed = isPhysicsStepUsed
return M
