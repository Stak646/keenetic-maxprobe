#!/bin/sh
# One-shot installer for keenetic-maxprobe
# - Installs required Entware packages via opkg
# - Installs /opt/bin/keenetic-maxprobe
# - Runs it immediately

PATH="/opt/sbin:/opt/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

say() { printf "%s\n" "$*"; }

die() { say "ERROR: $*" >&2; exit 1; }

need_root() {
  uid="$(id -u 2>/dev/null)"
  [ "$uid" = "0" ] || die "Run as root (admin). Try: sudo -i" 
}

have() { command -v "$1" >/dev/null 2>&1; }

need_root

# Check Entware/opkg
if ! have opkg && [ ! -x /opt/bin/opkg ]; then
  say "opkg not found."
  say "You need KeeneticOS OPKG/Entware installed (OPKG component enabled)."
  say "Official guide: Installing OPKG Entware ... (Help Center)"
  die "Install Entware first, then re-run this one-liner."
fi

OPKG_BIN="$(command -v opkg 2>/dev/null)"
[ -n "$OPKG_BIN" ] || OPKG_BIN="/opt/bin/opkg"

say "[1/3] opkg update"
$OPKG_BIN update || say "WARN: opkg update failed (maybe no Internet?)"

say "[2/3] Installing dependencies (best-effort)"
# Keep it small but useful; some may already exist.
PKGS="curl ca-bundle wget-ssl coreutils findutils tar gzip procps-ng ip-full iptables jq openssl-util"
for p in $PKGS; do
  $OPKG_BIN install "$p" >/dev/null 2>&1 && say "  + $p" || say "  ~ $p (skipped/failed)"
done

say "[3/3] Installing keenetic-maxprobe to /opt/bin"
INSTALL_PATH="/opt/bin/keenetic-maxprobe"
mkdir -p /opt/bin 2>/dev/null || true

cat > "$INSTALL_PATH" <<'SCRIPT_EOF'
#!/bin/sh
# keenetic-maxprobe.sh
# Collects maximum diagnostic information from KeeneticOS + Entware (OPKG)
# without requiring user configuration.
#
# This tool is intended for OWN router diagnostics and building integrations (e.g. Telegram bot).
# It REDACTS secrets by default.

KM_VERSION="0.1.0"

# Ensure /opt bins are in PATH (Entware)
PATH="/opt/sbin:/opt/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

umask 077

now_utc() {
  # BusyBox date may not support %N
  date -u "+%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date "+%Y-%m-%dT%H:%M:%SZ"
}

safe_hostname() {
  hn="$(hostname 2>/dev/null | tr -cd 'A-Za-z0-9._-' | cut -c1-64)"
  [ -n "$hn" ] && { echo "$hn"; return; }
  echo "keenetic"
}

pick_base_dir() {
  # Prefer persistent storage (Entware), fallback to RAM.
  for d in "/opt/var/tmp" "/opt/tmp" "/opt/var" "/opt" "/tmp"; do
    if [ -d "$d" ] && [ -w "$d" ]; then
      # quick writability check
      t="$d/.kmw.$$"
      ( : > "$t" ) 2>/dev/null && rm -f "$t" 2>/dev/null
      if [ $? -eq 0 ]; then
        echo "$d"
        return
      fi
    fi
  done
  echo "."
}

mkdir_p() {
  d="$1"
  [ -d "$d" ] || mkdir -p "$d" 2>/dev/null
}

# Redaction filter (awk) for configs and logs
sanitize_stream() {
  awk '
  BEGIN{in_pem=0}
  function lcase(s){return tolower(s)}
  function is_sensitive_key(k){
    k=lcase(k)
    return (k=="password"||k=="pass"||k=="passphrase"||k=="secret"||k=="token"||k=="apikey"||k=="api-key"||k=="psk"||k=="community"||k=="key"||k=="private-key"||k=="privatekey"||k=="private")
  }
  function redact_field(arr, n, i){
    # redact next token(s) after sensitive markers and key=value pairs
    for (i=1;i<=n;i++){
      k=lcase(arr[i])
      # key=value form
      if (index(arr[i],"=")>0) {
        split(arr[i],kv,"=")
        kk=lcase(kv[1])
        if (kk ~ /(pass|password|secret|token|apikey|api-key|psk|community|private|key)/) {
          arr[i]=kv[1]"=<REDACTED>"
        }
      }
      if (is_sensitive_key(k)){
        if (i<n) {
          alg=lcase(arr[i+1])
          if ((alg=="md5"||alg=="nt"||alg=="sha"||alg=="sha1"||alg=="sha256"||alg=="sha512"||alg=="plain"||alg=="text") && (i+2)<=n) {
            arr[i+2]="<REDACTED>"
          } else {
            arr[i+1]="<REDACTED>"
          }
        }
      }
    }
  }
  {
    line=$0
    if (in_pem==1) {
      if (line ~ /^-----END /) { in_pem=0; print line }
      next
    }
    if (line ~ /^-----BEGIN .*PRIVATE KEY-----/ || line ~ /^-----BEGIN OPENSSH PRIVATE KEY-----/) {
      in_pem=1
      print line
      print "<REDACTED PEM CONTENT>"
      next
    }

    # split by space preserving original spacing is hard; we rebuild with single spaces
    n=split(line,a," ")
    redact_field(a,n)
    out=a[1]
    for (i=2;i<=n;i++){ out=out" "a[i] }
    print out
  }
  '
}

# Global paths
HOST="$(safe_hostname)"
TS="$(now_utc | tr -cd '0-9TZ:-' | tr ':' '-')"
BASE="$(pick_base_dir)"
OUTDIR="$BASE/keenetic-maxprobe-${HOST}-${TS}"

mkdir_p "$OUTDIR" || {
  echo "ERROR: cannot create output directory: $OUTDIR" >&2
  exit 1
}

# Subdirs
mkdir_p "$OUTDIR/env"
mkdir_p "$OUTDIR/net"
mkdir_p "$OUTDIR/fs"
mkdir_p "$OUTDIR/ndm"
mkdir_p "$OUTDIR/entware"
mkdir_p "$OUTDIR/hooks"
mkdir_p "$OUTDIR/api"
mkdir_p "$OUTDIR/meta"

LOG="$OUTDIR/keenetic-maxprobe.log"
ERR="$OUTDIR/errors.log"

log() {
  msg="$1"
  printf "%s %s\n" "$(now_utc)" "$msg" | tee -a "$LOG" >/dev/null
}

log_err() {
  msg="$1"
  printf "%s %s\n" "$(now_utc)" "$msg" >> "$ERR"
  printf "%s %s\n" "$(now_utc)" "$msg" | tee -a "$LOG" >/dev/null
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

# Run a shell command and store output
run_cmd() {
  out="$1"; shift
  desc="$1"; shift
  cmd="$*"
  log "RUN [$desc] -> $out"
  (
    echo "# keenetic-maxprobe $KM_VERSION"
    echo "# host: $HOST"
    echo "# utc: $(now_utc)"
    echo "# cmd: $cmd"
    echo ""
    sh -c "$cmd"
    ec=$?
    echo ""
    echo "# exit_code: $ec"
    exit $ec
  ) >"$out" 2>&1
  ec=$?
  if [ $ec -ne 0 ]; then
    log_err "FAIL [$desc] exit=$ec cmd=$cmd"
  fi
  return 0
}

# Run a command, then sanitize into final file (keeps raw temporarily)
run_cmd_sanitized() {
  out="$1"; shift
  desc="$1"; shift
  cmd="$*"
  tmp="$OUTDIR/.tmp.$$.$(basename "$out")"
  run_cmd "$tmp" "$desc" "$cmd"
  sanitize_stream < "$tmp" > "$out" 2>/dev/null || cp "$tmp" "$out" 2>/dev/null
  rm -f "$tmp" 2>/dev/null
  return 0
}

# Capture a file: store metadata + sanitized content (if text)
capture_file() {
  src="$1"
  rel="$(echo "$src" | sed 's|/|_|g')"
  meta_out="$OUTDIR/fs/filemeta_${rel}.txt"
  body_out="$OUTDIR/fs/file_${rel}.txt"

  if [ ! -e "$src" ]; then
    log_err "MISSING file: $src"
    return 0
  fi

  # metadata
  {
    echo "# utc: $(now_utc)"
    echo "# path: $src"
    ls -l "$src" 2>&1
    if have_cmd stat; then
      stat "$src" 2>&1
    fi
    if have_cmd sha256sum && [ -f "$src" ]; then
      sha256sum "$src" 2>&1
    fi
  } > "$meta_out" 2>&1

  # content: best-effort only for regular files
  if [ -f "$src" ]; then
    # avoid dumping huge binaries; still record metadata above
    # limit is intentionally high to stay "maximum" without bricking storage
    max_bytes=5242880  # 5 MiB
    sz=""
    if have_cmd wc; then
      sz="$(wc -c < "$src" 2>/dev/null)"
    fi
    if [ -n "$sz" ] && [ "$sz" -gt "$max_bytes" ]; then
      echo "# NOTE: file size ${sz} bytes > ${max_bytes} bytes; content not included." > "$body_out"
      echo "# You can manually copy it if needed: $src" >> "$body_out"
      return 0
    fi

    # detect binary quickly
    if have_cmd grep && grep -q "\\x00" "$src" 2>/dev/null; then
      echo "# NOTE: binary file (NUL detected); content not included." > "$body_out"
      return 0
    fi

    sanitize_stream < "$src" > "$body_out" 2>/dev/null || cp "$src" "$body_out" 2>/dev/null
  fi
}

# Basic meta
{
  echo "keenetic-maxprobe_version=$KM_VERSION"
  echo "host=$HOST"
  echo "utc_start=$(now_utc)"
  echo "base_dir=$BASE"
  echo "output_dir=$OUTDIR"
  echo "path=$PATH"
  echo "uid=$(id -u 2>/dev/null)"
  echo "gid=$(id -g 2>/dev/null)"
  echo "id=$(id 2>/dev/null)"
} > "$OUTDIR/meta/meta.txt" 2>/dev/null

log "keenetic-maxprobe $KM_VERSION starting"
log "Output: $OUTDIR"

# --- ENV / OS ---
run_cmd "$OUTDIR/env/uname.txt" "uname" "uname -a"
run_cmd "$OUTDIR/env/os_release.txt" "os-release" "(cat /etc/os-release 2>/dev/null || true)"
run_cmd "$OUTDIR/env/proc_version.txt" "proc-version" "cat /proc/version 2>/dev/null || true"
run_cmd "$OUTDIR/env/cpuinfo.txt" "cpuinfo" "cat /proc/cpuinfo 2>/dev/null || true"
run_cmd "$OUTDIR/env/meminfo.txt" "meminfo" "cat /proc/meminfo 2>/dev/null || true"
run_cmd "$OUTDIR/env/uptime.txt" "uptime" "uptime 2>/dev/null || cat /proc/uptime 2>/dev/null || true"
run_cmd "$OUTDIR/env/mounts.txt" "mount" "mount 2>/dev/null || cat /proc/mounts 2>/dev/null || true"
run_cmd "$OUTDIR/env/df.txt" "df" "df -h 2>/dev/null || df 2>/dev/null || true"
run_cmd "$OUTDIR/env/df_inodes.txt" "df-inodes" "df -i 2>/dev/null || true"
run_cmd "$OUTDIR/env/partitions.txt" "partitions" "cat /proc/partitions 2>/dev/null || true"
run_cmd "$OUTDIR/env/lsmod.txt" "lsmod" "(lsmod 2>/dev/null || cat /proc/modules 2>/dev/null || true)"
run_cmd "$OUTDIR/env/dmesg_tail.txt" "dmesg-tail" "dmesg 2>/dev/null | tail -n 500 || true"

# Processes
run_cmd "$OUTDIR/env/ps.txt" "ps" "ps w 2>/dev/null || ps 2>/dev/null || true"
if have_cmd top; then
  run_cmd "$OUTDIR/env/top.txt" "top" "top -b -n 1 2>/dev/null || true"
fi

# --- NETWORK ---
if have_cmd ip; then
  run_cmd "$OUTDIR/net/ip_addr.txt" "ip-addr" "ip addr show 2>/dev/null || true"
  run_cmd "$OUTDIR/net/ip_link.txt" "ip-link" "ip link show 2>/dev/null || true"
  run_cmd "$OUTDIR/net/ip_route.txt" "ip-route" "ip route show table all 2>/dev/null || true"
  run_cmd "$OUTDIR/net/ip_rule.txt" "ip-rule" "ip rule show 2>/dev/null || true"
  run_cmd "$OUTDIR/net/ip_neigh.txt" "ip-neigh" "ip neigh show 2>/dev/null || true"
  run_cmd "$OUTDIR/net/ip6_route.txt" "ip6-route" "ip -6 route show table all 2>/dev/null || true"
else
  run_cmd "$OUTDIR/net/ifconfig.txt" "ifconfig" "ifconfig -a 2>/dev/null || true"
  run_cmd "$OUTDIR/net/route.txt" "route" "route -n 2>/dev/null || true"
fi

# Listening ports
if have_cmd ss; then
  run_cmd "$OUTDIR/net/ss_listen.txt" "ss" "ss -lntup 2>/dev/null || ss -lntp 2>/dev/null || true"
elif have_cmd netstat; then
  run_cmd "$OUTDIR/net/netstat_listen.txt" "netstat" "netstat -lntup 2>/dev/null || netstat -lntp 2>/dev/null || true"
fi

# Firewall rules
if have_cmd iptables-save; then
  run_cmd "$OUTDIR/net/iptables_save.txt" "iptables-save" "iptables-save 2>/dev/null || true"
fi
if have_cmd ip6tables-save; then
  run_cmd "$OUTDIR/net/ip6tables_save.txt" "ip6tables-save" "ip6tables-save 2>/dev/null || true"
fi

# --- NDM / KeeneticOS via ndmc (preferred) ---
NDMC_BIN=""
if have_cmd ndmc; then
  NDMC_BIN="$(command -v ndmc)"
elif [ -x /usr/sbin/ndmc ]; then
  NDMC_BIN="/usr/sbin/ndmc"
elif [ -x /bin/ndmc ]; then
  NDMC_BIN="/bin/ndmc"
fi

if [ -n "$NDMC_BIN" ]; then
  run_cmd "$OUTDIR/ndm/ndmc_version.txt" "ndmc-version" "$NDMC_BIN -h 2>&1 || true"

  # Core info
  run_cmd_sanitized "$OUTDIR/ndm/show_version.txt" "ndm-show-version" "$NDMC_BIN -c 'show version'"
  run_cmd_sanitized "$OUTDIR/ndm/show_system.txt" "ndm-show-system" "$NDMC_BIN -c 'show system'"

  # Configuration (these may include secrets -> sanitized)
  run_cmd_sanitized "$OUTDIR/ndm/show_running-config.txt" "ndm-running-config" "$NDMC_BIN -c 'show running-config'"
  run_cmd_sanitized "$OUTDIR/ndm/more_system_running-config.txt" "ndm-system-running-config" "$NDMC_BIN -c 'more system:running-config'"
  run_cmd_sanitized "$OUTDIR/ndm/more_flash_startup-config.txt" "ndm-flash-startup-config" "$NDMC_BIN -c 'more flash:startup-config'"

  # Log
  run_cmd_sanitized "$OUTDIR/ndm/show_log.txt" "ndm-show-log" "$NDMC_BIN -c 'show log'"

  # Interfaces and routes (state)
  run_cmd_sanitized "$OUTDIR/ndm/show_interface.txt" "ndm-show-interface" "$NDMC_BIN -c 'show interface'"
  run_cmd_sanitized "$OUTDIR/ndm/show_ip_route.txt" "ndm-show-ip-route" "$NDMC_BIN -c 'show ip route'"
  run_cmd_sanitized "$OUTDIR/ndm/show_ip_policy.txt" "ndm-show-ip-policy" "$NDMC_BIN -c 'show ip policy'"

  # Users / access / services
  run_cmd_sanitized "$OUTDIR/ndm/show_users.txt" "ndm-show-users" "$NDMC_BIN -c 'show users'"
  run_cmd_sanitized "$OUTDIR/ndm/show_service.txt" "ndm-show-service" "$NDMC_BIN -c 'show service'"
  run_cmd_sanitized "$OUTDIR/ndm/components_list.txt" "ndm-components-list" "$NDMC_BIN -c 'components list'"

  # Try to dump command index (best effort)
  run_cmd_sanitized "$OUTDIR/ndm/help.txt" "ndm-help" "$NDMC_BIN -c 'help'"
else
  log_err "ndmc not found; NDM CLI collection skipped. Ensure SSH/CLI access is enabled." 
fi

# --- ENTWARE / OPKG ---
OPKG_BIN=""
if have_cmd opkg; then
  OPKG_BIN="$(command -v opkg)"
elif [ -x /opt/bin/opkg ]; then
  OPKG_BIN="/opt/bin/opkg"
fi

if [ -n "$OPKG_BIN" ]; then
  run_cmd "$OUTDIR/entware/opkg_version.txt" "opkg-version" "$OPKG_BIN --version 2>/dev/null || $OPKG_BIN -V 2>/dev/null || true"
  run_cmd "$OUTDIR/entware/opkg_list_installed.txt" "opkg-list-installed" "$OPKG_BIN list-installed 2>/dev/null || true"
  run_cmd "$OUTDIR/entware/opkg_status.txt" "opkg-status" "$OPKG_BIN status 2>/dev/null || true"
  run_cmd "$OUTDIR/entware/opkg_conf_dump.txt" "opkg-conf" "(ls -la /opt/etc/opkg* /opt/etc/opkg 2>/dev/null || true); (find /opt/etc -maxdepth 2 -type f -name '*opkg*' -print 2>/dev/null || true)"

  # Capture common Entware config directories
  if [ -d /opt/etc ]; then
    run_cmd "$OUTDIR/entware/opt_etc_tree.txt" "opt-etc-tree" "find /opt/etc -maxdepth 4 -printf '%p\t%y\t%m\t%s\t%TY-%Tm-%TdT%TH:%TM:%TS\n' 2>/dev/null || find /opt/etc -maxdepth 4 -print 2>/dev/null || true"
  fi

  # Init scripts
  if [ -d /opt/etc/init.d ]; then
    run_cmd "$OUTDIR/entware/init_d_list.txt" "init-d-list" "ls -la /opt/etc/init.d 2>/dev/null || true"
  fi

  # Logs
  if [ -d /opt/var/log ]; then
    run_cmd "$OUTDIR/entware/opt_var_log_list.txt" "opt-var-log" "ls -la /opt/var/log 2>/dev/null || true"
  fi
else
  log_err "opkg not found; Entware collection limited. If you use Entware, install OPKG component and Entware first." 
fi

# --- HOOKS discovery (OPKG component + generic *.d hooks) ---
# OPKG/NDM integration hooks are usually in /opt/etc/ndm/*.d
if [ -d /opt/etc/ndm ]; then
  run_cmd "$OUTDIR/hooks/opt_etc_ndm_tree.txt" "hooks-opt-etc-ndm" "find /opt/etc/ndm -maxdepth 3 -printf '%p\t%y\t%m\t%s\t%TY-%Tm-%TdT%TH:%TM:%TS\n' 2>/dev/null || find /opt/etc/ndm -maxdepth 3 -print 2>/dev/null || true"
  # Capture hook scripts content (sanitized)
  find /opt/etc/ndm -type f 2>/dev/null | while IFS= read -r f; do
    capture_file "$f"
  done
fi

# Generic hook-like dirs
run_cmd "$OUTDIR/hooks/find_dotd_dirs.txt" "hooks-find-dotd" "find / -type d -name '*.d' -maxdepth 6 2>/dev/null | head -n 2000 || true"

# --- FILESYSTEM structure / config inventory ---
# Directory tree snapshot (limited depth to avoid /proc explosion)
run_cmd "$OUTDIR/fs/tree_root_maxdepth3.txt" "fs-tree" "find / -maxdepth 3 -xdev \( -path /proc -o -path /sys -o -path /dev \) -prune -o -printf '%p\t%y\t%m\t%s\t%TY-%Tm-%TdT%TH:%TM:%TS\n' 2>/dev/null || true"

# Config-like files inventory (paths only)
run_cmd "$OUTDIR/fs/config_files_list.txt" "fs-config-list" "find /etc /opt/etc /opt/var 2>/dev/null \( -path /opt/var/opkg-lists -o -path /opt/var/cache \) -prune -o -type f \( -name '*.conf' -o -name '*.cfg' -o -name '*.ini' -o -name '*.json' -o -name '*.yaml' -o -name '*.yml' -o -name '*.lua' -o -name '*.sh' -o -name '*.rules' -o -name '*.list' -o -name '*.cnf' \) -print 2>/dev/null | sort 2>/dev/null || true"

# Capture selected key files (best effort) - you can extend this list later
KEY_FILES="/opt/etc/opkg.conf /opt/etc/profile /opt/etc/rc.local /opt/etc/initrc /etc/passwd /etc/group"
for f in $KEY_FILES; do
  [ -e "$f" ] && capture_file "$f"
done

# --- API probing (no login) ---
# Discover web management port and existence of /auth and /rci/ endpoints.

http_probe_one() {
  proto="$1"; port="$2"; path="$3"
  url="$proto://127.0.0.1:$port$path"
  if have_cmd curl; then
    curl -skI --max-time 4 "$url" 2>/dev/null | tr -d '\r'
    return 0
  elif have_cmd wget; then
    # busybox wget may not support --server-response on https
    wget -S -O - "$url" 2>&1 | tr -d '\r'
    return 0
  fi
  return 1
}

probe_ports="80 81 280 591 777 5080 8080 8090 65080"
{
  echo "# keenetic-maxprobe $KM_VERSION"
  echo "# utc: $(now_utc)"
  echo "# Probing management ports from Keenetic docs (possible HTTP ports)."
  echo "# NOTE: No authentication is performed. Only headers are collected."
  echo ""
  for p in $probe_ports; do
    echo "## PORT $p /auth (http)"
    http_probe_one "http" "$p" "/auth" || echo "(no curl/wget)"
    echo ""
    echo "## PORT $p /auth (https)"
    http_probe_one "https" "$p" "/auth" || echo "(no curl/wget)"
    echo ""
    echo "## PORT $p /rci/ (http)"
    http_probe_one "http" "$p" "/rci/" || echo "(no curl/wget)"
    echo ""
    echo "## PORT $p /ci/startup-config.txt (http)"
    http_probe_one "http" "$p" "/ci/startup-config.txt" || echo "(no curl/wget)"
    echo ""
    echo "## PORT $p /ci/self-test.txt (http)"
    http_probe_one "http" "$p" "/ci/self-test.txt" || echo "(no curl/wget)"
    echo ""
  done
} > "$OUTDIR/api/http_probe.txt" 2>/dev/null

# --- FINAL SUMMARY ---
{
  echo "keenetic-maxprobe $KM_VERSION"
  echo "UTC start: $(cat "$OUTDIR/meta/meta.txt" 2>/dev/null | grep '^utc_start=' | cut -d= -f2-)"
  echo "UTC end:   $(now_utc)"
  echo "Output dir: $OUTDIR"
  echo "Log:        $LOG"
  echo "Errors:     $ERR"
  echo ""
  echo "Key artifacts:" 
  echo "  - NDM config:   ndm/show_running-config.txt (sanitized)"
  echo "  - startup-config: ndm/more_flash_startup-config.txt (sanitized)"
  echo "  - NDM log:      ndm/show_log.txt"
  echo "  - Entware pkgs: entware/opkg_list_installed.txt"
  echo "  - Hooks:        hooks/opt_etc_ndm_tree.txt"
  echo "  - API probe:    api/http_probe.txt"
  echo ""
  echo "Security note: secrets (passwords/keys/tokens) are REDACTED automatically." 
} > "$OUTDIR/SUMMARY.txt" 2>/dev/null

# Package into archive
ARCHIVE="$OUTDIR.tar.gz"
log "Creating archive: $ARCHIVE"
(base_parent="$(dirname "$OUTDIR")" && base_name="$(basename "$OUTDIR")" && tar -czf "$ARCHIVE" -C "$base_parent" "$base_name" ) 2>>"$ERR" || log_err "Failed to create archive"

if have_cmd sha256sum && [ -f "$ARCHIVE" ]; then
  sha256sum "$ARCHIVE" > "$ARCHIVE.sha256" 2>/dev/null
fi

log "DONE"
log "Archive: $ARCHIVE"
[ -f "$ARCHIVE.sha256" ] && log "SHA256:  $(cat "$ARCHIVE.sha256" 2>/dev/null | awk '{print $1}')"

# Final user-facing output
cat "$OUTDIR/SUMMARY.txt" 2>/dev/null

exit 0
SCRIPT_EOF

chmod 0755 "$INSTALL_PATH" || die "cannot chmod $INSTALL_PATH"

say "Installed: $INSTALL_PATH"

say "Running keenetic-maxprobe..."
"$INSTALL_PATH"
