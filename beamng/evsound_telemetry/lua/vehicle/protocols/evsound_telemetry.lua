-- BeamNG custom protocol interface, following lua/vehicle/protocols/outgauge.lua.
local M = {}
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
  o.marker = "EVS1"
  o.speed = e.wheelspeed or e.airspeed or 0
  o.throttle = e.throttle or 0
  o.brake = e.brake or 0
  o.rpm = e.rpm or 0
  o.motorRPM = e.motorRPM or e.motorRpm or -1
  o.motorTorque = e.motorTorque or e.torqueMotor or -1
  o.motorPower = e.motorPower or e.powerMotor or -1
  o.regen = e.regen or e.regenActive or -1
  o.regenTorque = e.regenTorque or e.torqueRegen or -1
  o.regenPower = e.regenPower or e.powerRegen or -1
  o.motorLoad = e.motorLoad or -1
  o.watts = e.watts or -1
end
M.init = function() end
M.reset = function() end
M.getAddress = getAddress
M.getPort = getPort
M.getMaxUpdateRate = getMaxUpdateRate
M.getStructDefinition = getStructDefinition
M.fillStruct = fillStruct
M.isPhysicsStepUsed = isPhysicsStepUsed
return M
