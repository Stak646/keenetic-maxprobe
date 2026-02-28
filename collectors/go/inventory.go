package main

import (
	"bufio"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"
)

type Inv struct {
	Tool      string            `json:"tool"`
	Version   string            `json:"version"`
	TsUTC     string            `json:"ts_utc"`
	GOOS      string            `json:"goos"`
	GOARCH    string            `json:"goarch"`
	Hostname  string            `json:"hostname,omitempty"`
	Work      string            `json:"work,omitempty"`
	Proc      map[string]string `json:"proc"`
	ListenTCP []Listen          `json:"listen_tcp"`
}

type Listen struct {
	Proto string `json:"proto"`
	Addr  string `json:"addr"`
	Port  int    `json:"port"`
}

const Version = "0.5.1"

func readSmall(path string, max int64) string {
	f, err := os.Open(path)
	if err != nil {
		return ""
	}
	defer f.Close()
	var b strings.Builder
	_, _ = io.CopyN(&b, f, max)
	return b.String()
}

func parseProcNetTCP(path string, proto string) []Listen {
	f, err := os.Open(path)
	if err != nil {
		return nil
	}
	defer f.Close()

	var out []Listen
	sc := bufio.NewScanner(f)
	first := true
	for sc.Scan() {
		ln := strings.TrimSpace(sc.Text())
		if ln == "" {
			continue
		}
		if first {
			first = false
			continue
		}
		fields := strings.Fields(ln)
		if len(fields) < 4 {
			continue
		}
		local := fields[1]
		state := fields[3]
		// 0A is LISTEN
		if state != "0A" {
			continue
		}
		parts := strings.Split(local, ":")
		if len(parts) != 2 {
			continue
		}
		addrHex := parts[0]
		portHex := parts[1]
		port64, err := strconv.ParseInt(portHex, 16, 32)
		if err != nil {
			continue
		}
		addr := addrHex
		// best-effort decode IPv4 hex (little endian)
		if len(addrHex) == 8 {
			raw, err := hex.DecodeString(addrHex)
			if err == nil && len(raw) == 4 {
				addr = fmt.Sprintf("%d.%d.%d.%d", raw[3], raw[2], raw[1], raw[0])
			}
		}
		out = append(out, Listen{Proto: proto, Addr: addr, Port: int(port64)})
	}
	return out
}

func main() {
	work := flag.String("work", "", "work directory (optional)")
	flag.Parse()

	host, _ := os.Hostname()
	inv := Inv{
		Tool:     "keenetic-maxprobe-go-inventory",
		Version:  Version,
		TsUTC:    time.Now().UTC().Format(time.RFC3339),
		GOOS:     runtime.GOOS,
		GOARCH:   runtime.GOARCH,
		Hostname: host,
		Work:     *work,
		Proc: map[string]string{
			"cpuinfo":  readSmall("/proc/cpuinfo", 64*1024),
			"meminfo":  readSmall("/proc/meminfo", 64*1024),
			"loadavg":  readSmall("/proc/loadavg", 1024),
			"uptime":   readSmall("/proc/uptime", 1024),
			"version":  readSmall("/proc/version", 8*1024),
			"cmdline":  readSmall("/proc/cmdline", 8*1024),
			"mounts":   readSmall("/proc/mounts", 64*1024),
		},
	}

	listen := []Listen{}
	listen = append(listen, parseProcNetTCP("/proc/net/tcp", "tcp")...)
	listen = append(listen, parseProcNetTCP("/proc/net/tcp6", "tcp6")...)
	inv.ListenTCP = listen

	// If work is provided, also drop a copy into sys/collectors (best-effort)
	if *work != "" {
		outPath := filepath.Join(*work, "sys", "collectors", "go_inventory.json")
		_ = os.MkdirAll(filepath.Dir(outPath), 0o755)
		if b, err := json.MarshalIndent(inv, "", "  "); err == nil {
			_ = os.WriteFile(outPath, b, 0o644)
		}
	}

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(inv)
}
