package main

import (
  "bufio"
  "fmt"
  "os"
  "os/exec"
  "strings"
  "time"
)

func run(cmd string) string {
  c := exec.Command("sh", "-c", cmd)
  out, err := c.CombinedOutput()
  if err != nil {
    return string(out) + "\n# err: " + err.Error() + "\n"
  }
  return string(out)
}

func main() {
  if len(os.Args) < 2 {
    fmt.Fprintln(os.Stderr, "usage: inventory.go <out_file>")
    os.Exit(2)
  }
  outFile := os.Args[1]
  f, err := os.Create(outFile)
  if err != nil {
    fmt.Fprintln(os.Stderr, "open:", err)
    os.Exit(2)
  }
  defer f.Close()
  w := bufio.NewWriter(f)
  defer w.Flush()

  fmt.Fprintln(w, "# go inventory collector")
  fmt.Fprintln(w, "# time:", time.Now().UTC().Format(time.RFC3339))
  fmt.Fprintln(w, "")

  cmds := []string{
    "go version 2>&1",
    "uname -a 2>&1",
    "id 2>&1",
    "opkg print-architecture 2>/dev/null || true",
  }
  for _, c := range cmds {
    fmt.Fprintln(w, "### CMD:", c)
    fmt.Fprintln(w, run(c))
  }

  fmt.Fprintln(w, "### Executables (path list)")
  data := run("for d in /bin /sbin /usr/bin /usr/sbin /opt/bin /opt/sbin; do [ -d \"$d\" ] && find \"$d\" -maxdepth 2 -type f -perm -111 2>/dev/null; done | sort -u")
  lines := strings.Split(data, "\n")
  max := 200000
  if len(lines) > max {
    lines = lines[:max]
    lines = append(lines, "# ... truncated ...")
  }
  fmt.Fprintln(w, strings.Join(lines, "\n"))
}
