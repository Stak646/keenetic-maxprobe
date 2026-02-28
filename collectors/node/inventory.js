#!/opt/bin/node
const fs = require('fs');
const { execSync } = require('child_process');

const out = process.argv[2];
if (!out) {
  console.error("usage: inventory.js <out_file>");
  process.exit(2);
}

function run(cmd) {
  try { return execSync(cmd, { stdio: ['ignore','pipe','pipe'] }).toString(); }
  catch (e) { return (e.stdout?e.stdout.toString():"") + (e.stderr?e.stderr.toString():""); }
}

let s = "";
s += "# node inventory collector\n";
s += "# time: " + new Date().toISOString() + "\n\n";
for (const c of ["node -v 2>&1", "uname -a 2>&1", "id 2>&1"]) {
  s += "### CMD: " + c + "\n";
  s += run(c) + "\n";
}
fs.writeFileSync(out, s);
