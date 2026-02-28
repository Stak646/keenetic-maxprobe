#!/opt/bin/perl
use strict;
use warnings;

my $out = shift @ARGV or die "usage: inventory.pl <out_file>\n";
open(my $fh, ">", $out) or die "open($out): $!\n";

print $fh "# perl inventory collector\n";
print $fh "# time: " . scalar(gmtime()) . " UTC\n\n";

my @cmds = (
  "perl -v 2>/dev/null | head -n 5",
  "uname -a",
  "id",
  "env | sort",
);

for my $c (@cmds) {
  print $fh "### CMD: $c\n";
  my $outp = `$c 2>&1`;
  print $fh $outp . "\n";
}
close($fh);
