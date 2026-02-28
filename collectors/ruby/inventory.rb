#!/opt/bin/ruby
require 'time'
out = ARGV[0] or abort("usage: inventory.rb <out_file>")

File.open(out, "w") do |f|
  f.puts "# ruby inventory collector"
  f.puts "# time: #{Time.now.getutc.iso8601 rescue Time.now}"
  f.puts
  cmds = [
    "ruby -v 2>&1",
    "uname -a 2>&1",
    "id 2>&1",
  ]
  cmds.each do |c|
    f.puts "### CMD: #{c}"
    f.puts `#{c}`
    f.puts
  end
end
