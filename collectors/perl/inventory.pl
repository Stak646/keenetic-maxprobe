#!/usr/bin/env perl
# keenetic-maxprobe Perl collector (inventory)
# Version: 0.5.0
use strict;
use warnings;
use POSIX qw(strftime);

my $work = $ARGV[0] // ".";
print "keenetic-maxprobe Perl inventory\n";
print "work=$work\n";
print "ts_utc=" . strftime("%Y-%m-%dT%H:%M:%SZ", gmtime()) . "\n";

sub slurp {
  my ($path, $max) = @_;
  $max //= 65536;
  open(my $fh, "<", $path) or return "";
  binmode($fh);
  my $buf;
  read($fh, $buf, $max);
  close($fh);
  return $buf // "";
}

my $ver = slurp("/proc/version", 4096);
$ver =~ s/\s+$//;
print "kernel=$ver\n";

my $mem = slurp("/proc/meminfo", 4096);
if ($mem ne "") {
  print "\n== /proc/meminfo ==\n";
  print $mem;
}
