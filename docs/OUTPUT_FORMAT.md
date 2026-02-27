# Output format

A successful run generates:

- `keenetic-maxprobe-<host>-<timestamp>/` (directory)
- `keenetic-maxprobe-<host>-<timestamp>.tar.gz` (archive)

Inside the directory:

```
SUMMARY.txt
keenetic-maxprobe.log
errors.log
meta/
  meta.txt
env/
  uname.txt
  os_release.txt
  proc_version.txt
  cpuinfo.txt
  meminfo.txt
  uptime.txt
  mounts.txt
  df.txt
  df_inodes.txt
  partitions.txt
  lsmod.txt
  dmesg_tail.txt
  ps.txt
  top.txt (optional)
net/
  ip_addr.txt
  ip_link.txt
  ip_route.txt
  ip_rule.txt
  ip_neigh.txt
  ip6_route.txt
  ss_listen.txt (or netstat_listen.txt)
  iptables_save.txt (optional)
  ip6tables_save.txt (optional)
ndm/
  ndmc_version.txt
  show_version.txt
  show_system.txt
  show_running-config.txt
  more_system_running-config.txt
  more_flash_startup-config.txt
  show_log.txt
  show_interface.txt
  show_ip_route.txt
  show_ip_policy.txt
  show_users.txt
  show_service.txt
  components_list.txt
  help.txt
entware/
  opkg_version.txt
  opkg_list_installed.txt
  opkg_status.txt
  opkg_conf_dump.txt
  opt_etc_tree.txt
  init_d_list.txt
  opt_var_log_list.txt
hooks/
  opt_etc_ndm_tree.txt
  find_dotd_dirs.txt
fs/
  tree_root_maxdepth3.txt
  config_files_list.txt
  filemeta_*.txt
  file_*.txt
api/
  http_probe.txt
```

Notes:
- `ndm/*` and collected file contents are **sanitized** (secrets redacted).
- `filemeta_*` contain metadata (ls/stat/hash) for a captured file.
- `file_*` contain captured file content (if not too large and not binary).

