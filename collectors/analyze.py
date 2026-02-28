#!/usr/bin/env python3
import os, sys, re, hashlib, json
from pathlib import Path

SENSITIVE_PATTERNS = [
  ("PASSWORD", re.compile(r"(?i)\b(pass(word)?|pwd)\b\s*[:=]\s*.+")),
  ("TOKEN", re.compile(r"(?i)\b(token|api[_-]?key|secret|client[_-]?secret)\b\s*[:=]\s*.+")),
  ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH|DSA|ED25519)? ?PRIVATE KEY-----")),
  ("BASIC_AUTH", re.compile(r"(?i)Authorization:\s*Basic\s+[A-Za-z0-9+/=]+")),
  ("BEARER", re.compile(r"(?i)Authorization:\s*Bearer\s+[A-Za-z0-9._-]+")),
]

TEXT_EXT = {".conf",".cfg",".ini",".json",".yaml",".yml",".toml",".xml",".sh",".rc",".rules",".lua",".py",".pl",".rb",".js",".ts",".env",".txt",".list",".ovpn",".wg",".pem",".crt",".key",".pub"}

def sha256_file(p: Path, max_bytes=None):
    h=hashlib.sha256()
    with p.open("rb") as f:
        if max_bytes is None:
            for chunk in iter(lambda: f.read(1024*1024), b""):
                h.update(chunk)
        else:
            h.update(f.read(max_bytes))
    return h.hexdigest()

def is_texty(p: Path):
    if p.suffix.lower() in TEXT_EXT:
        return True
    try:
        p.read_bytes()[:8192].decode("utf-8")
        return True
    except Exception:
        return False

def scan_sensitive(p: Path, rel: str):
    if not is_texty(p):
        return []
    try:
        lines = p.read_text(errors="ignore").splitlines()
    except Exception:
        return []
    out=[]
    for i, line in enumerate(lines, 1):
        for name, rx in SENSITIVE_PATTERNS:
            if rx.search(line):
                out.append({"type": name, "path": rel, "line": i, "excerpt": line[:240]})
    return out

def redact_line(line: str):
    line = re.sub(r'(?i)\b(pass(word)?|pwd)\b\s*[:=]\s*.*', 'PASSWORD: <REDACTED>', line)
    line = re.sub(r'(?i)\b(token|api[_-]?key|secret|client[_-]?secret)\b\s*[:=]\s*.*', 'SECRET: <REDACTED>', line)
    line = re.sub(r'(?i)(Authorization:\s*Basic)\s+.+', r'\1 <REDACTED>', line)
    line = re.sub(r'(?i)(Authorization:\s*Bearer)\s+.+', r'\1 <REDACTED>', line)
    return line

def redact_file(p: Path):
    try:
        txt = p.read_text(errors="ignore").splitlines(True)
    except Exception:
        return
    out=[]
    in_key=False
    for line in txt:
        if "BEGIN" in line and "PRIVATE KEY" in line:
            in_key=True
            out.append("-----BEGIN PRIVATE KEY-----\n<REDACTED PRIVATE KEY>\n")
            continue
        if in_key:
            if "END" in line and "PRIVATE KEY" in line:
                in_key=False
                out.append("-----END PRIVATE KEY-----\n")
            continue
        out.append(redact_line(line))
    try:
        p.write_text("".join(out), encoding="utf-8", errors="ignore")
    except Exception:
        pass

def main():
    if len(sys.argv) < 4:
        print("usage: analyze.py <WORKDIR> <MODE> <PROFILE>", file=sys.stderr)
        return 2
    work = Path(sys.argv[1]).resolve()
    mode = sys.argv[2].lower()
    profile = sys.argv[3].lower()
    fs = work/"fs"
    analysis = work/"analysis"; analysis.mkdir(parents=True, exist_ok=True)
    meta = work/"meta"; meta.mkdir(parents=True, exist_ok=True)

    files=[]
    findings=[]
    for p in fs.rglob("*"):
        if p.is_dir(): 
            continue
        try:
            st = p.lstat()
        except Exception:
            continue
        rel = str(p.relative_to(work))
        try:
            sha = sha256_file(p, None if st.st_size <= 50*1024*1024 else 10*1024*1024)
        except Exception:
            sha = "ERR"
        files.append((sha, oct(st.st_mode & 0o777), st.st_uid, st.st_gid, st.st_size, int(st.st_mtime), rel))
        findings.extend(scan_sensitive(p, rel))
        if mode == "safe":
            redact_file(p)

    files.sort(key=lambda x:x[-1])
    (meta/"files_manifest.tsv").write_text(
        "sha256\tmode\tuid\tgid\tsize\tmtime\tpath\n" + 
        "\n".join("\t".join(map(str,r)) for r in files) + "\n",
        encoding="utf-8"
    )

    findings.sort(key=lambda x:(x["path"], x["line"]))
    s = ["# Sensitive locations (для ручного скрытия перед отправкой)","",
         f"- MODE: `{mode}`  PROFILE: `{profile}`",
         "- В FULL файлы не редактируются. В SAFE копии редактируются автоматически.",""]
    if not findings:
        s.append("Ничего не найдено по шаблонам. Это не гарантирует отсутствие секретов.")
    else:
        s.append("## Найденные совпадения")
        last=None
        for it in findings:
            if it["path"]!=last:
                s.append(""); s.append(f"### {it['path']}")
                last=it["path"]
            s.append(f"- line {it['line']} **{it['type']}**: `{it['excerpt']}`")
    s.append(""); s.append("## Рекомендации")
    s.append("- Перед отправкой архива: удалите/замените секреты или зашифруйте архив.")
    (analysis/"SENSITIVE_LOCATIONS.md").write_text("\n".join(s)+"\n", encoding="utf-8")

    summary = {"mode": mode, "profile": profile, "collected_files": len(files), "sensitive_hits": len(findings)}
    (analysis/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    (analysis/"REPORT_RU.md").write_text(
        "# Отчёт keenetic-maxprobe\n\n"
        f"- MODE: `{mode}`\n- PROFILE: `{profile}`\n"
        f"- Всего файлов в fs/: **{len(files)}**\n"
        f"- Совпадений по секретам: **{len(findings)}** (см. SENSITIVE_LOCATIONS.md)\n\n"
        "## Где смотреть точки управления\n"
        "- Хуки: analysis/INDEX_HOOK_SCRIPTS.txt и fs/*/ndm/*\n"
        "- Entware службы: analysis/INDEX_INITD_SCRIPTS.txt и fs/opt/etc/init.d/*\n"
        "- OPKG: entware/opkg_files_all.txt\n"
        "- NDM дампы: ndm/\n",
        encoding="utf-8"
    )
    (analysis/"REPORT_EN.md").write_text(
        "# keenetic-maxprobe report\n\n"
        f"- MODE: `{mode}`\n- PROFILE: `{profile}`\n"
        f"- Files in fs/: **{len(files)}**\n"
        f"- Sensitive hits: **{len(findings)}** (see SENSITIVE_LOCATIONS.md)\n",
        encoding="utf-8"
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
