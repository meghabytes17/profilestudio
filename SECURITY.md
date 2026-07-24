# Security review — Profile Studio (Incoming Profile Utility)

**Deployment model:** a single-user desktop application that runs entirely on the operator's
Windows machine. There is **no server, no service, no listening port, and no network traffic
of any kind**. It reads and writes only files the user chooses, plus a small config in the
user's own profile directory.

This matters for interpreting the red-team prompt that assumed a client/server product: the
majority of that checklist describes an architecture this tool does not have.

---

## Scope: what did and did not apply

**Not applicable — no such component exists**

| Red-team dimension | Why it doesn't apply |
|---|---|
| Auth / LDAP / AD / SSO / cert, user vs admin roles | No accounts, no login, no roles. The app runs as the logged-in user with that user's rights. |
| Missing server-side authz ("client hides the button, API still serves it") | No API and no server. |
| Job lifecycle, queueing, double-submit, resubmit-while-running | No jobs, no queue, no background execution. Rendering is synchronous and local. |
| Multi-user isolation, "one user seeing another's results" | Single user, single process. Files are protected by ordinary OS permissions. |
| Client/server version skew, `schemaVersion` N±1 negotiation | Nothing to negotiate with. |
| Server unreachable, interrupted upload, backpressure | No uploads. |
| Session/token handling, secrets in a client bundle | No sessions, tokens, credentials, or keys anywhere in the codebase. |

**Applicable — reviewed, with findings below:** hostile input handling, what is written to disk
(IP retention), error-message leakage, airgap compliance, supply chain, and dependency
integrity.

---

## Findings

### 1. Preview renders were left in the shared temp directory — FIXED

**Severity: High** (for an IP-sensitive customer) · **Confirmed by demonstration** · **Fixed**

Every preview render was written to a fixed, predictable path in the shared temp directory and
**never deleted**. Verified: after closing the application, a 516 KB bitmap containing a
full-resolution render of the modelled cross-section remained on disk (mode `644`). Anyone with
access to the machine, a backup, a disk image, or a forensic capture could recover the
customer's process geometry without ever opening the application. Two concurrent instances also
overwrote each other's file.

*Fix:* each session now renders into its own private scratch directory (`0700`; on Windows,
inherited per-user ACLs on `%TEMP%`), removed both on normal exit and via an `atexit` handler
on an unclean exit. Verified: no leftovers in either path. Two regression tests fail if the old
behaviour returns.

### 2. Dependencies were unpinned — FIXED

**Severity: Medium** · **Confirmed** · **Fixed**

`pyproject.toml` used floating lower bounds (`numpy>=1.26`, …), so a rebuild pulls whatever is
current — the `.exe` you validated is not necessarily the `.exe` you ship, and an airgapped
rebuild is not reproducible.

*Fix:* added `requirements-lock.txt` with the exact verified-working versions; `build_exe.bat`
now builds from it. The file documents the vendored-wheelhouse procedure for a build machine
with no internet, and how to add `--generate-hashes` so a tampered wheel is rejected.

**Recommended before delivery:** regenerate the lock with hashes (`pip-compile
--generate-hashes`) and build with `pip install --require-hashes`. This is the one remaining
supply-chain hardening step and it is a build-process change, not a code change.

### 3. Raw exception text is shown in the UI

**Severity: Low** · **Confirmed** · **Accepted / optional**

Three paths surface the raw exception string (failed project open, failed CSV load, failed
render), which typically includes an absolute filesystem path. The only viewer is the operator
who triggered it, so this is not a privilege boundary — but such messages do end up in
screenshots and support tickets. If the customer objects to internal paths appearing in
screenshots, these can be reduced to a short message plus a log entry.

---

## Verified clean

These were actively attacked, not assumed:

- **No code execution from untrusted files.** No `eval`, `exec`, `pickle`, `marshal`,
  `subprocess`, `os.system`, `shell=True`, or `yaml.load` anywhere in `src/`. Project files are
  parsed with `json.load`, which cannot execute code. A hostile `project.json` cannot run
  commands. Enforced by a test.
- **No path traversal from file contents.** Material names taken from a project file are used
  only as palette dictionary keys; they never reach the filesystem. A name like
  `../../etc/passwd` is inert. All file paths come from the user's own OS file dialogs.
- **Airgap compliant.** No network code of any kind: no HTTP client, no sockets, no telemetry,
  no auto-update, no licence check, no remote fonts or CDN assets. Every asset (icon, palette,
  fonts) is local or bundled. The only URL in the codebase is the SVG XML namespace in exported
  files, which is an identifier and is not fetched. Enforced by a test.
- **The tracked base palette is never modified.** User colour changes are written to the user's
  own profile directory; `config/materials.json` is byte-identical after a recolour. Enforced by
  a test.
- **No credentials or secrets** in source, config, or the shipped bundle.

---

## What the app writes to disk (complete list)

Useful if the customer audits application file activity:

| Path | Contents | Lifetime |
|---|---|---|
| Wherever the user saves | `.bmp` renders, `.json` projects, `.svg`/`.json` polygon exports | User-controlled |
| `%LOCALAPPDATA%\...\user_materials.json` | Custom materials + colour overrides. No process geometry. | Persistent |
| `%TEMP%\ipu_<random>\preview.bmp` | Working render | **Deleted on exit** |

The application creates no logs, no crash dumps, and no history/recent-files list.

---

## Residual risk

The application inherits the trust level of the machine and the logged-in user. It does not
attempt to defend the customer's IP against someone who already controls that machine — the
files the user deliberately saves are plain `.bmp`/`.json` with no encryption or DRM, which is
the expected behaviour for an engineering tool. If the customer requires protection at rest,
that belongs in full-disk encryption and folder ACLs, not in this application.

---

## Verdict

**Ship**, after applying the two fixes above (both are in the current build) and, ideally, the
hash-pinned build step from finding 2. No architectural security work is required, because the
architecture the red-team prompt assumed — a network service handling multi-user jobs — does
not exist here.
