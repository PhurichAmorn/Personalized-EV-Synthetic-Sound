-- EV Sound Lab telemetry protocol. Installs as a BeamNG vehicle protocol.
-- The JSON payload intentionally reports raw observed electrics, not inferred EV torque.
local M = {}

local socket = require('socket')
local udp
local timer = 0
local interval = 1 / 30
local host = '127.0.0.1'
local port = 4445

local function finite(value)
  return type(value) == 'number' and value == value and value ~= math.huge and value ~= -math.huge
end

local function number(value)
  return finite(value) and string.format('%.6g', value) or 'null'
end

local function sendTelemetry()
  if not udp then
    udp = socket.udp()
    udp:settimeout(0)
    udp:setpeername(host, port)
  end
  local e = electrics.values or {}
  local velocity = obj:getVelocity()
  local speed = velocity and velocity:length() or nil
  local fields = {'speed_m_s=' .. number(speed)}
  for _, key in ipairs({'throttle', 'brake', 'rpm', 'motorRPM', 'motorTorque', 'motorPower', 'regen', 'regenTorque', 'regenPower', 'motorLoad', 'watts'}) do
    if finite(e[key]) then fields[#fields + 1] = key .. '=' .. number(e[key]) end
  end
  local payload = 'EVSL1 ' .. table.concat(fields, ' ')
  udp:send(payload)
end

function M.init() end
function M.update(dt)
  timer = timer + dt
  if timer >= interval then
    timer = timer % interval
    pcall(sendTelemetry)
  end
end
function M.reset() timer = 0 end
function M.shutdown()
  if udp then udp:close(); udp = nil end
end
function M.setParameters(data)
  if data and data.host then host = data.host end
  if data and data.port then port = tonumber(data.port) or port end
end

return M
