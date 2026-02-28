#!/opt/bin/lua
local out = arg[1]
if not out then
  io.stderr:write("usage: inventory.lua <out_file>\n")
  os.exit(2)
end
local f = assert(io.open(out, "w"))
f:write("# lua inventory collector\n")
f:write("# time: " .. os.date("!%Y-%m-%dT%H:%M:%SZ") .. "\n\n")
local cmds = {
  "lua -v 2>&1",
  "uname -a 2>&1",
  "id 2>&1",
}
for _, c in ipairs(cmds) do
  f:write("### CMD: " .. c .. "\n")
  local p = io.popen(c)
  if p then
    f:write(p:read("*a"))
    p:close()
  end
  f:write("\n")
end
f:close()
