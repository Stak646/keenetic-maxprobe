#!/usr/bin/env node
// keenetic-maxprobe Node collector (inventory)
// Version: 0.5.0

const fs = require('fs');

const work = process.argv[2] || '.';
function readFile(path, maxBytes) {
  try {
    const buf = fs.readFileSync(path);
    if (buf.length > maxBytes) return buf.slice(0, maxBytes).toString('utf8') + '\n...<truncated>...\n';
    return buf.toString('utf8');
  } catch (_) {
    return '';
  }
}

console.log('keenetic-maxprobe Node inventory');
console.log('work=' + work);
console.log('ts_utc=' + new Date().toISOString().replace('.000',''));

const ver = readFile('/proc/version', 4096).trim();
if (ver) console.log('kernel=' + ver);

const loadavg = readFile('/proc/loadavg', 256).trim();
if (loadavg) console.log('loadavg=' + loadavg);
