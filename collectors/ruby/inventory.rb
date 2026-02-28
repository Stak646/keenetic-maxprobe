#!/usr/bin/env ruby
# keenetic-maxprobe Ruby collector (inventory)
# Version: 0.5.0

work = ARGV[0] || "."
puts "keenetic-maxprobe Ruby inventory"
puts "work=#{work}"
puts "ts_utc=#{Time.now.utc.strftime("%Y-%m-%dT%H:%M:%SZ")}"

def readfile(path, max = 65536)
  data = File.binread(path)
  return data.byteslice(0, max) + "\n...<truncated>...\n" if data.bytesize > max
  data
rescue
  ""
end

ver = readfile("/proc/version", 4096).strip
puts "kernel=#{ver}" unless ver.empty?

mem = readfile("/proc/meminfo", 4096)
unless mem.empty?
  puts "\n== /proc/meminfo =="
  print mem
end
