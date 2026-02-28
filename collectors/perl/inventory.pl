#!/usr/bin/env perl
# collectors/perl/inventory.pl
# Version: 0.6.0
# Usage: perl inventory.pl <workdir>
# Prints inventory to stdout.

use warnings;

my $workdir = $ARGV[0] // ".";
chomp(my $ts = `date -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null`);
chomp(my $uname = `uname -a 2>/dev/null`);

print "perl_inventory_version=0.6.0\n";
print "workdir=$workdir\n";
print "ts_utc=$ts\n" if $ts;
print "uname=$uname\n" if $uname;
print "perl=$^V\n";
