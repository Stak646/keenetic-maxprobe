-- keenetic-maxprobe Lua collector (inventory)
-- Version: 0.5.0

local work = arg[1] or "."
local function readfile(path, max)
  local f = io.open(path, "r")
  if not f then return "" end
  local data = f:read(max or 65536) or ""
  f:close()
  return data
end

print("keenetic-maxprobe Lua inventory")
print("work=" .. work)
print("ts_utc=" .. os.date("!%Y-%m-%dT%H:%M:%SZ"))
print("kernel=" .. (readfile("/proc/version", 4096):gsub("%s+$","")))

local mem = readfile("/proc/meminfo", 4096)
if mem ~= "" then
  print("\n== /proc/meminfo (head) ==")
  io.write(mem)
end
