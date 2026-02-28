#!/usr/bin/env ruby
# collectors/ruby/inventory.rb
# Version: 0.6.0
# Usage: ruby inventory.rb <workdir>
# Prints inventory to stdout.

workdir = ARGV[0] || "."
ts = `date -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null`.strip
uname = `uname -a 2>/dev/null`.strip

puts "ruby_inventory_version=0.6.0"
puts "workdir=#{workdir}"
puts "ts_utc=#{ts}" unless ts.empty?
puts "uname=#{uname}" unless uname.empty?
puts "ruby=#{RUBY_VERSION}"
