-- collectors/lua/inventory.lua
-- Version: 0.6.0
-- Usage: lua inventory.lua <workdir>
-- Prints inventory to stdout (caller redirects to file).

local workdir = arg[1] or "."

local function sh(cmd)
  local p = io.popen(cmd .. " 2>/dev/null")
  if not p then return "" end
  local out = p:read("*a") or ""
  p:close()
  return out
end

local function trim(s)
  return (s:gsub("^%s+", ""):gsub("%s+$", ""))
end

local uname = trim(sh("uname -a"))
local dateu = trim(sh("date -u '+%Y-%m-%dT%H:%M:%SZ'"))
local mem = trim(sh("awk '/MemTotal:/ {print $2" kB"}' /proc/meminfo"))
local cpu = trim(sh("awk -F: '/model name/ {print $2; exit}' /proc/cpuinfo"))

print("lua_inventory_version=0.6.0")
print("workdir=" .. workdir)
print("ts_utc=" .. dateu)
print("uname=" .. uname)
if cpu ~= "" then print("cpu_model=" .. trim(cpu)) end
if mem ~= "" then print("mem_total=" .. mem) end
print("lua=" .. (_VERSION or "lua"))
