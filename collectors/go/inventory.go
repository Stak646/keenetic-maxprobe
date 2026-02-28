package main

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"time"
)

const Version = "0.6.0"

func sh(cmd string) string {
	c := exec.Command("sh", "-c", cmd)
	out, err := c.CombinedOutput()
	if err != nil {
		// still return output (may contain useful error text)
	}
	return string(out)
}

func main() {
	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()

	fmt.Fprintf(w, "go_inventory_version=%s
", Version)
	fmt.Fprintf(w, "ts_utc=%s
", time.Now().UTC().Format(time.RFC3339))
	fmt.Fprintln(w, "go_version="+stringTrim(sh("go version 2>/dev/null")))
	fmt.Fprintln(w, "uname="+stringTrim(sh("uname -a 2>/dev/null")))

	// Optional extras (best-effort)
	fmt.Fprintln(w, "")
	fmt.Fprintln(w, "=== df -h ===")
	fmt.Fprintln(w, sh("df -h 2>/dev/null"))
	fmt.Fprintln(w, "=== ip addr ===")
	fmt.Fprintln(w, sh("ip addr 2>/dev/null"))
}

func stringTrim(s string) string {
	// trim spaces/newlines at both ends without extra deps
	i := 0
	j := len(s)

	for i < j && (s[i] == ' ' || s[i] == '\n' || s[i] == '\r' || s[i] == '\t') {
		i++
	}
	for j > i && (s[j-1] == ' ' || s[j-1] == '\n' || s[j-1] == '\r' || s[j-1] == '\t') {
		j--
	}
	return s[i:j]
}
