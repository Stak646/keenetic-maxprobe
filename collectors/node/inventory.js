#!/usr/bin/env node
// collectors/node/inventory.js
// Version: 0.6.0
// Usage: node inventory.js <workdir>
// Prints inventory to stdout.

const { execSync } = require("child_process");

function sh(cmd) {
  try {
    return execSync(cmd, { stdio: ["ignore", "pipe", "ignore"], encoding: "utf8" }).trim();
  } catch {
    return "";
  }
}

const workdir = process.argv[2] || ".";
const ts = sh("date -u '+%Y-%m-%dT%H:%M:%SZ'") || "";
const uname = sh("uname -a") || "";

console.log("node_inventory_version=0.6.0");
console.log("workdir=" + workdir);
if (ts) console.log("ts_utc=" + ts);
if (uname) console.log("uname=" + uname);
console.log("node=" + process.version);
