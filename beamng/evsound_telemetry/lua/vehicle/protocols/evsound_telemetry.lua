-- BeamNG custom protocol interface, following lua/vehicle/protocols/outgauge.lua.
local M = {}
local rearMotor

local function init()
  rearMotor = powertrain.getDevice("rearMotor")
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
  local e = electrics.values
  rearMotor = rearMotor or powertrain.getDevice("rearMotor")
  o.marker = "EVS1"
  o.speed = e.wheelspeed or e.airspeed or 0
  o.throttle = e.throttle or 0
  o.brake = e.brake or 0
  o.rpm = e.rpm or 0
  o.motorRPM = rearMotor and (rearMotor.outputRPM or 0) or -1
  o.motorTorque = rearMotor and (rearMotor.outputTorque1 or 0) or -1
  o.motorPower = rearMotor and (rearMotor.outputTorque1 or 0) * (rearMotor.outputAV1 or 0) or -1
  o.regen = rearMotor and (rearMotor.regenThrottle or 0) or -1
  o.regenTorque = rearMotor and (rearMotor.instantMaxRegenTorque or 0) or -1
  o.regenPower = rearMotor and (rearMotor.maxRegenPower or 0) or -1
  o.motorLoad = rearMotor and (rearMotor.instantEngineLoad or 0) or -1
  o.watts = rearMotor and (rearMotor.spentEnergy or 0) / math.max(dtSim or 0, 1e-6) or -1
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
