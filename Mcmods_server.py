# Written by Claude Sonnet 4.6 / Claude Sonnet 5
#!/usr/bin/env python3
"""
Mcmods_server.py - Minecraft server mod/datapack manager (Modrinth)

Version: R_1.2 (2026-07-10)

Multi-profile server variant of Mcmods_templatev2.py (each profile is one
server's mod/datapack set). The profile is the first CLI argument, e.g.
'python Mcmods_server.py survival upgrade'. Each profile gets its own config
(Mcmods_server_<profile>.json) and, same as Mcmods.py, its download directory
is a full path typed in at 'init' rather than auto-derived from where this
script lives — so the script's own location never needs to match where mods
are actually stored, and moving the script elsewhere is safe.
Resource packs and shader packs are not supported.

Usage:
  python Mcmods_server.py <profile> init
  python Mcmods_server.py <profile> upgrade [slug]  # omit slug to upgrade everything
  python Mcmods_server.py <profile> set-version <version>

  python Mcmods_server.py <profile> add <slug>             # mods
  python Mcmods_server.py <profile> remove <slug>
  python Mcmods_server.py <profile> add-manual <filename>
  python Mcmods_server.py <profile> remove-manual <filename>
  python Mcmods_server.py <profile> legacy_on <slug> <version>
  python Mcmods_server.py <profile> legacy_off <slug>
  python Mcmods_server.py <profile> link <slug> <filename>

  python Mcmods_server.py <profile> add_dp <slug>          # datapacks
  python Mcmods_server.py <profile> remove_dp <slug>
  python Mcmods_server.py <profile> add_manual_dp <filename>
  python Mcmods_server.py <profile> remove_manual_dp <filename>
  python Mcmods_server.py <profile> legacy_on_dp <slug> <version>
  python Mcmods_server.py <profile> legacy_off_dp <slug>
  python Mcmods_server.py <profile> link_dp <slug> <filename>

  python Mcmods_server.py <profile> freeze <slug|all>
  python Mcmods_server.py <profile> unfreeze <slug|all>
  python Mcmods_server.py <profile> clear <slug|all|mods|dp>

  python Mcmods_server.py <profile> choose <slug>
  python Mcmods_server.py <profile> unchoose <slug>
  python Mcmods_server.py <profile> unchoose_all
  python Mcmods_server.py <profile> choose_dp <slug>
  python Mcmods_server.py <profile> unchoose_dp <slug>
  python Mcmods_server.py <profile> unchoose_all_dp
  python Mcmods_server.py <profile> upgrade_chooseall
  python Mcmods_server.py <profile> upgrade_masterchoose

  python Mcmods_server.py <profile> list

  python Mcmods_server.py help                             # this text (no profile needed)

A profile is deleted simply by deleting its Mcmods_server_<profile>.json file.
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

# Windows consoles often default to a legacy codepage (e.g. cp1252) that can't
# encode the icons used below (❄ ✎ etc.) — reconfigure to UTF-8 so printing
# them degrades gracefully instead of crashing with UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_VERSION      = "R_1.2"
SCRIPT_VERSION_DATE = "2026-07-10"
SCRIPT_DIR          = Path(__file__).parent

CONFIG_FILE    = None  # set in main() once the profile is known
MODRINTH_API   = "https://api.modrinth.com/v2"
USER_AGENT     = "mcmods-script/2.0-server"
DP_LOADER      = "datapack"

# ANSI color helpers
def _ansi(code): return f"\033[{code}m"
_RESET  = _ansi(0)
_GREEN  = _ansi(32)
_YELLOW = _ansi(33)
_CYAN   = _ansi(36)
_BOLD   = _ansi(1)

def _supports_color():
    if os.environ.get("NO_COLOR"):
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            kernel = ctypes.windll.kernel32
            kernel.SetConsoleMode(kernel.GetStdHandle(-11), 7)
            return True
        except Exception:
            return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

_COLOR = _supports_color()

def green(s):  return f"{_GREEN}{s}{_RESET}"  if _COLOR else s
def yellow(s): return f"{_YELLOW}{s}{_RESET}" if _COLOR else s
def cyan(s):   return f"{_CYAN}{s}{_RESET}"   if _COLOR else s
def bold(s):   return f"{_BOLD}{s}{_RESET}"   if _COLOR else s


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config():
    if not CONFIG_FILE.exists():
        print("No config file found. Run 'init' first.")
        sys.exit(1)
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Modrinth API (stdlib only)
# ---------------------------------------------------------------------------

def modrinth_get(path, params=None):
    url = f"{MODRINTH_API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def get_all_versions(slug, mc_version, loader):
    try:
        params = {
            "game_versions": json.dumps([mc_version]),
            "loaders":       json.dumps([loader]),
        }
        versions = modrinth_get(f"/project/{slug}/version", params)
        if not versions:
            return None, "not_available"
        return versions, None
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, f"not_available (slug '{slug}' not found on Modrinth)"
        return None, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return None, f"error: {e}"


def get_latest_version(slug, mc_version, loader):
    versions, error = get_all_versions(slug, mc_version, loader)
    if error:
        return None, error
    return versions[0], None


def get_project_name(slug):
    try:
        data = modrinth_get(f"/project/{slug}")
        return data.get("title", slug)
    except Exception:
        return slug


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def delete_file(directory, filename):
    if filename:
        p = Path(directory) / filename
        if p.exists():
            p.unlink()
            return True
    return False


def download_file(url, dest_path):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest_path, "wb") as f:
        while chunk := resp.read(65536):
            f.write(chunk)


# ---------------------------------------------------------------------------
# Shared upgrade logic for a single entry list (mods or datapacks)
# ---------------------------------------------------------------------------

def _upgrade_entries(config, entries_key, dir_key, loader, mc_version, only_slug=None):
    """
    Upgrade one category (mods or datapacks).
    only_slug: if given, only that single entry is processed.
    Returns (updated, ok, pending, legacy, errors, frozen, choose_details) lists.
    choose_details: list of (name, detail_string)
    """
    entries_dir = config.get(dir_key, "")
    dirty       = False

    updated        = []
    ok             = []
    pending        = []
    legacy         = []   # (name, legacy_version)
    errors         = []
    frozen         = []
    choose_details = []

    entries = config.get(entries_key, [])
    if only_slug is not None:
        entries = [e for e in entries if e["slug"] == only_slug]

    for entry in entries:
        slug       = entry["slug"]
        name       = entry.get("name", slug)
        legacy_ver = entry.get("legacy_version")

        if entry.get("frozen"):
            frozen.append(name)
            continue

        versions, error = get_all_versions(slug, mc_version, loader)
        is_not_available = error == "not_available" or (error and "not_available" in error)

        if entry.get("choose") and versions and not is_not_available:
            result = _upgrade_entry_with_choose(entry, versions, entries_dir, force_prompt=False)
            dirty = True
            if result == "updated":
                updated.append(name)
                vtype = versions[0].get("version_type", "?")
                vnum  = versions[0].get("version_number", "?")
                choose_details.append((name, green(f"manual selection — updated to {vnum} [{vtype}]")))
            elif result == "ok":
                ok.append(name)
                vtype = versions[0].get("version_type", "?")
                vnum  = versions[0].get("version_number", "?")
                choose_details.append((name, green(f"manual selection — up to date ({vnum} [{vtype}])")))
            elif result == "skipped":
                choose_details.append((name, yellow(f"manual selection — skipped")))
            else:
                errors.append((name, result[1]))
                choose_details.append((name, "manual selection — error"))
            save_config(config)
            continue

        version_info = versions[0] if versions else None

        if version_info and not is_not_available and not error:
            files   = version_info.get("files", [])
            primary = next((f for f in files if f.get("primary")), files[0] if files else None)

            if not primary:
                errors.append((name, "no downloadable file in API response"))
                continue

            new_filename = primary["filename"]

            if entry.get("file") == new_filename and not entry.get("pending") and not entry.get("legacy_active"):
                ok.append(name)
                continue

            old_filename = entry.get("file")
            if old_filename and old_filename != new_filename:
                delete_file(entries_dir, old_filename)

            dest = Path(entries_dir) / new_filename
            print(f"  Downloading {name}  ({new_filename}) ...", end="", flush=True)
            try:
                download_file(primary["url"], dest)
                print("  OK")
                if entry.get("legacy_active"):
                    print(f"    Legacy mode cleared — now on current version.")
                entry["file"]          = new_filename
                entry["pending"]       = False
                entry.pop("legacy_active",  None)
                entry.pop("legacy_version", None)
                dirty = True
                updated.append(name)
            except Exception as e:
                print("  FAILED")
                errors.append((name, str(e)))

        elif error and not is_not_available:
            errors.append((name, error))

        else:
            if legacy_ver:
                legacy_info, legacy_error = get_latest_version(slug, legacy_ver, loader)

                if legacy_error:
                    if entry.get("file"):
                        delete_file(entries_dir, entry["file"])
                        entry["file"] = None
                        dirty = True
                    entry["pending"]       = True
                    entry["legacy_active"] = False
                    dirty = True
                    pending.append(name)
                else:
                    files   = legacy_info.get("files", [])
                    primary = next((f for f in files if f.get("primary")), files[0] if files else None)

                    if not primary:
                        errors.append((name, "no downloadable file in legacy API response"))
                        continue

                    new_filename = primary["filename"]

                    if entry.get("file") == new_filename and entry.get("legacy_active"):
                        legacy.append((name, legacy_ver))
                        continue

                    old_filename = entry.get("file")
                    if old_filename and old_filename != new_filename:
                        delete_file(entries_dir, old_filename)

                    dest = Path(entries_dir) / new_filename
                    print(f"  Downloading {name}  ({new_filename}, legacy {legacy_ver}) ...", end="", flush=True)
                    try:
                        download_file(primary["url"], dest)
                        print("  OK")
                        entry["file"]          = new_filename
                        entry["pending"]       = False
                        entry["legacy_active"] = True
                        dirty = True
                        legacy.append((name, legacy_ver))
                    except Exception as e:
                        print("  FAILED")
                        errors.append((name, str(e)))
            else:
                if entry.get("file"):
                    delete_file(entries_dir, entry["file"])
                    entry["file"] = None
                    dirty = True
                entry["pending"] = True
                dirty = True
                pending.append(name)

    if dirty:
        save_config(config)

    return updated, ok, pending, legacy, errors, frozen, choose_details


def _print_category_summary(label, updated, ok, pending, legacy, errors, frozen, mc_version, choose_details):
    print(f"\n{label}:")
    if updated:
        auto_updated = [n for n in updated if not any(n == c[0] for c in choose_details)]
        if auto_updated:
            print(f"  Updated ({len(auto_updated)}):     {', '.join(auto_updated)}")
    if ok:
        auto_ok = [n for n in ok if not any(n == c[0] for c in choose_details)]
        if auto_ok:
            print(f"  Up to date ({len(auto_ok)}):  {', '.join(auto_ok)}")
    for name, detail in choose_details:
        print(f"  ✎  {name}: {detail}")
    for name in frozen:
        print(f"  ❄  {name}: FROZEN — skipped, kept current file (run 'unfreeze' to resume)")
    for name in pending:
        print(f"  ⚠  {name}: PENDING — not available for {mc_version}, will retry")
    for name, lver in legacy:
        print(f"  ⚠  {name}: LEGACY — running on {lver} (not available for {mc_version})")
    for name, msg in errors:
        if not any(name == c[0] and "error" in c[1] for c in choose_details):
            print(f"  ✗  {name}: {msg}")
    if not (updated or ok or choose_details or frozen or pending or legacy or errors):
        print("  (none)")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_init():
    if CONFIG_FILE.exists():
        print(f"Config already exists at {CONFIG_FILE}. Delete it first to re-init.")
        return

    print("=== mcmods server setup ===\n")
    mc_version = input("Minecraft version (e.g. 1.21.4):    ").strip()
    loader     = input("Mod loader (e.g. fabric):            ").strip().lower()
    mods_dir   = input("Download directory (full path):      ").strip().strip('"')

    Path(mods_dir).mkdir(parents=True, exist_ok=True)

    config = {
        "mc_version":       mc_version,
        "loader":           loader,
        "mods_dir":         mods_dir,
        "mods":             [],
        "manual_mods":      [],
        "datapacks":        [],
        "manual_datapacks": [],
    }
    save_config(config)
    print(f"\nConfig saved to {CONFIG_FILE}")
    print(f"Mods and datapacks will be downloaded to: {mods_dir}")


def cmd_upgrade(config, target=None):
    mc_version = config["mc_version"]
    loader     = config["loader"]

    only_key = None
    if target is not None:
        entry, only_key = _find_entry(config, target)
        if not entry:
            print(f"No managed mod/datapack with slug '{target}' found.")
            sys.exit(1)
        print(f"Upgrading only '{entry.get('name', target)}' — Minecraft {mc_version} ({loader})\n")
    else:
        print(f"Upgrading for Minecraft {mc_version} ({loader})\n")

    # Mods
    if only_key in (None, "mods"):
        m_updated, m_ok, m_pending, m_legacy, m_errors, m_frozen, m_choose = _upgrade_entries(
            config, "mods", "mods_dir", loader, mc_version,
            only_slug=(target if only_key == "mods" else None)
        )
    else:
        m_updated = m_ok = m_pending = m_legacy = m_errors = m_frozen = m_choose = []

    # Datapacks
    if only_key in (None, "datapacks"):
        if only_key is None and config.get("datapacks"):
            print("\n-- Datapacks --")
        dp_updated, dp_ok, dp_pending, dp_legacy, dp_errors, dp_frozen, dp_choose = _upgrade_entries(
            config, "datapacks", "mods_dir", DP_LOADER, mc_version,
            only_slug=(target if only_key == "datapacks" else None)
        )
    else:
        dp_updated = dp_ok = dp_pending = dp_legacy = dp_errors = dp_frozen = dp_choose = []

    # Summary
    if only_key in (None, "mods"):
        _print_category_summary("Mods", m_updated, m_ok, m_pending, m_legacy, m_errors, m_frozen, mc_version, m_choose)
    if only_key in (None, "datapacks"):
        _print_category_summary("Datapacks", dp_updated, dp_ok, dp_pending, dp_legacy, dp_errors, dp_frozen, mc_version, dp_choose)

    all_frozen = m_frozen + dp_frozen
    if all_frozen:
        print(f"\n❄  Frozen ({len(all_frozen)}): {', '.join(all_frozen)}")

    if target is None:
        for label, key in [("Manual mods", "manual_mods"), ("Manual datapacks", "manual_datapacks")]:
            manual = config.get(key, [])
            if manual:
                print(f"\n{label} (not managed): {', '.join(manual)}")

    print("\nDone.")


def cmd_upgrade_chooseall(config):
    mc_version = config["mc_version"]
    loader     = config["loader"]

    for label, entries_key, dir_key, ld in [
        ("mods",      "mods",      "mods_dir",      loader),
        ("datapacks", "datapacks", "mods_dir",  DP_LOADER),
    ]:
        choose_entries = [e for e in config.get(entries_key, []) if e.get("choose") and not e.get("frozen")]
        if not choose_entries:
            continue

        print(f"\nManual version selection for {len(choose_entries)} {label} — Minecraft {mc_version}\n")
        dirty = False
        for entry in choose_entries:
            name = entry.get("name", entry["slug"])
            versions, error = get_all_versions(entry["slug"], mc_version, ld)
            if error or not versions:
                print(f"  ✗  {name}: {error or 'no versions found'}")
                continue
            result = _upgrade_entry_with_choose(entry, versions, config.get(dir_key, ""), force_prompt=True)
            dirty = True
            if result == "updated":
                print(f"  ✎  {name}: {green('updated to ' + entry.get('file', '?'))}")
            elif result in ("ok", "skipped"):
                print(f"  ✎  {name}: {yellow('skipped (no change)')}")
            else:
                print(f"  ✗  {name}: {result[1]}")

        if dirty:
            save_config(config)

    print("\nDone.")


def cmd_upgrade_masterchoose(config):
    mc_version = config["mc_version"]
    loader     = config["loader"]

    for label, entries_key, dir_key, ld in [
        ("mods",      "mods",      "mods_dir",      loader),
        ("datapacks", "datapacks", "mods_dir",  DP_LOADER),
    ]:
        entries = [e for e in config.get(entries_key, []) if not e.get("frozen")]
        if not entries:
            continue

        print(f"\nMaster version selection — {label} — Minecraft {mc_version}")
        print("Pick a version for each entry, or skip to leave it unchanged.\n")

        dirty = False
        for entry in entries:
            name    = entry.get("name", entry["slug"])
            versions, error = get_all_versions(entry["slug"], mc_version, ld)
            if error or not versions:
                print(f"  ✗  {name}: {error or 'no versions found'}")
                continue

            current_id = entry.get("chosen_version_id")
            chosen = _prompt_version_choice(name, versions, current_version_id=current_id, current_filename=entry.get("file"))

            if chosen is None:
                print(f"  {yellow('→ skipped')}")
                continue

            picked_id = chosen["id"]
            if picked_id == current_id:
                print(f"  {green('→ already installed, no change')}")
                continue

            files   = chosen.get("files", [])
            primary = next((f for f in files if f.get("primary")), files[0] if files else None)
            if not primary:
                print(f"  ✗  {name}: no downloadable file in chosen version")
                continue

            new_filename = primary["filename"]
            old_filename = entry.get("file")
            entries_dir  = config.get(dir_key, "")
            if old_filename and old_filename != new_filename:
                delete_file(entries_dir, old_filename)

            dest = Path(entries_dir) / new_filename
            print(f"  Downloading {name}  ({new_filename}) ...", end="", flush=True)
            try:
                download_file(primary["url"], dest)
                print("  OK")
                entry["file"]              = new_filename
                entry["pending"]           = False
                entry["chosen_version_id"] = picked_id
                entry.pop("skipped_version_id", None)
                entry.pop("legacy_active", None)
                entry.pop("legacy_version", None)
                if not entry.get("choose"):
                    entry["choose"] = True
                    print(f"  {cyan('→ choose enabled automatically')}")
                dirty = True
            except Exception as e:
                print("  FAILED")
                print(f"  ✗  {name}: {e}")

        if dirty:
            save_config(config)

    print("\nDone.")


def cmd_set_version(config, new_version):
    old = config["mc_version"]
    config["mc_version"] = new_version
    save_config(config)
    print(f"Version changed: {old}  →  {new_version}\n")
    cmd_upgrade(config)


# ---------------------------------------------------------------------------
# Shared version picker helpers
# ---------------------------------------------------------------------------

def _prompt_version_choice(name, versions, current_version_id=None, current_filename=None):
    print(f"\n  New versions available for {bold(name)}:")
    for i, v in enumerate(versions, 1):
        vtype   = v.get("version_type", "?")
        vnum    = v.get("version_number", "?")
        date    = v.get("date_published", "")[:10]
        line    = f"    {i:2d}.  [{vtype:7s}]  {vnum}  ({date})"
        files   = v.get("files", [])
        primary = next((f for f in files if f.get("primary")), files[0] if files else None)
        v_filename = primary["filename"] if primary else None
        is_installed = (
            (current_version_id and v.get("id") == current_version_id) or
            (current_filename and v_filename == current_filename)
        )
        if is_installed:
            line = green(line + "  ← installed")
        print(line)
    print(f"    {yellow('-1 / Enter = skip for now')}")
    while True:
        raw = input(f"  Pick version for {name} [1-{len(versions)}, Enter=skip]: ").strip()
        if raw in ("", "-1"):
            return None
        try:
            idx = int(raw)
            if 1 <= idx <= len(versions):
                return versions[idx - 1]
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {len(versions)}, or -1/Enter to skip.")


def _upgrade_entry_with_choose(entry, versions, entries_dir, force_prompt=False):
    name      = entry.get("name", entry["slug"])
    newest    = versions[0]
    newest_id = newest["id"]

    if not force_prompt:
        if newest_id == entry.get("chosen_version_id"):
            return "ok"
        if newest_id == entry.get("skipped_version_id"):
            return "skipped"

    chosen = _prompt_version_choice(name, versions, current_version_id=entry.get("chosen_version_id"), current_filename=entry.get("file"))

    if chosen is None:
        entry["skipped_version_id"] = newest_id
        return "skipped"

    files   = chosen.get("files", [])
    primary = next((f for f in files if f.get("primary")), files[0] if files else None)
    if not primary:
        return ("error", "no downloadable file in chosen version")

    new_filename = primary["filename"]
    old_filename = entry.get("file")
    if old_filename and old_filename != new_filename:
        delete_file(entries_dir, old_filename)

    dest = Path(entries_dir) / new_filename
    print(f"  Downloading {name}  ({new_filename}) ...", end="", flush=True)
    try:
        download_file(primary["url"], dest)
        print("  OK")
        entry["file"]              = new_filename
        entry["pending"]           = False
        entry["chosen_version_id"] = chosen["id"]
        entry.pop("skipped_version_id", None)
        entry.pop("legacy_active", None)
        entry.pop("legacy_version", None)
        return "updated"
    except Exception as e:
        print("  FAILED")
        return ("error", str(e))


# ---------------------------------------------------------------------------
# Mod commands
# ---------------------------------------------------------------------------

def cmd_add(config, slug):
    if any(m["slug"] == slug for m in config.get("mods", [])):
        print(f"'{slug}' is already in the mod list.")
        return
    print(f"Looking up '{slug}' on Modrinth...", end="", flush=True)
    name = get_project_name(slug)
    print(f"  found: {name}")
    config.setdefault("mods", []).append({"slug": slug, "name": name, "file": None, "pending": True})
    save_config(config)
    print(f"Added '{name}'. Run 'upgrade' to download it.")


def cmd_remove(config, slug):
    mod = next((m for m in config.get("mods", []) if m["slug"] == slug), None)
    if not mod:
        print(f"No managed mod with slug '{slug}' found.")
        return
    name = mod.get("name", slug)
    if mod.get("file"):
        if delete_file(config["mods_dir"], mod["file"]):
            print(f"Deleted file: {mod['file']}")
    config["mods"] = [m for m in config["mods"] if m["slug"] != slug]
    save_config(config)
    print(f"Removed '{name}' from the list.")


def cmd_add_manual(config, filename):
    config.setdefault("manual_mods", [])
    if filename in config["manual_mods"]:
        print(f"'{filename}' is already registered as a manual mod.")
        return
    if not (Path(config["mods_dir"]) / filename).exists():
        print(f"Note: '{filename}' not found in mods directory yet.")
    config["manual_mods"].append(filename)
    save_config(config)
    print(f"Registered manual mod: {filename}")


def cmd_remove_manual(config, filename):
    if filename not in config.get("manual_mods", []):
        print(f"'{filename}' is not registered as a manual mod.")
        return
    config["manual_mods"].remove(filename)
    save_config(config)
    print(f"Unregistered manual mod: {filename} (file not deleted)")


def cmd_legacy_on(config, slug, legacy_version):
    mod = next((m for m in config.get("mods", []) if m["slug"] == slug), None)
    if not mod:
        print(f"No managed mod with slug '{slug}' found. Add it first with 'add'.")
        return
    mod["legacy_version"] = legacy_version
    save_config(config)
    print(f"Legacy fallback set for '{mod.get('name', slug)}': will use {legacy_version} if {config['mc_version']} is unavailable.")
    print("Running upgrade to apply...")
    cmd_upgrade(config)


def cmd_legacy_off(config, slug):
    mod = next((m for m in config.get("mods", []) if m["slug"] == slug), None)
    if not mod:
        print(f"No managed mod with slug '{slug}' found.")
        return
    if mod.get("file") and mod.get("legacy_active"):
        if delete_file(config["mods_dir"], mod["file"]):
            print(f"Deleted legacy file: {mod['file']}")
        mod["file"] = None
    mod["pending"]       = True
    mod["legacy_active"] = False
    mod.pop("legacy_version", None)
    save_config(config)
    print(f"Legacy mode cleared for '{mod.get('name', slug)}'. Marked as pending — run 'upgrade' to retry current version.")


def cmd_link(config, slug, filename):
    entry = next((e for e in config.get("mods", []) if e["slug"] == slug), None)
    if not entry:
        print(f"No managed mod with slug '{slug}' found. Add it first.")
        return
    d = config.get("mods_dir", "")
    if d and not (Path(d) / filename).exists():
        print(f"Note: '{filename}' not found in the mods directory yet — linking anyway.")
    entry["file"]    = filename
    entry["pending"] = False
    save_config(config)
    print(f"Linked '{filename}' to mod '{entry.get('name', slug)}'.")
    print("You can now 'freeze' it to keep this file across upgrades.")


def cmd_choose(config, slug):
    mod = next((m for m in config.get("mods", []) if m["slug"] == slug), None)
    if not mod:
        print(f"No managed mod with slug '{slug}' found.")
        return
    mod["choose"] = True
    save_config(config)
    print(f"Manual version selection enabled for '{mod.get('name', slug)}'.")


def cmd_unchoose(config, slug):
    mod = next((m for m in config.get("mods", []) if m["slug"] == slug), None)
    if not mod:
        print(f"No managed mod with slug '{slug}' found.")
        return
    mod.pop("choose", None)
    mod.pop("chosen_version_id", None)
    mod.pop("skipped_version_id", None)
    save_config(config)
    print(f"Manual version selection disabled for '{mod.get('name', slug)}'. It will auto-update normally from now on.")


def cmd_unchoose_all(config):
    count = 0
    for mod in config.get("mods", []):
        if mod.get("choose"):
            mod.pop("choose", None)
            mod.pop("chosen_version_id", None)
            mod.pop("skipped_version_id", None)
            count += 1
    save_config(config)
    print(f"Cleared manual version selection from {count} mod{'s' if count != 1 else ''}.")


# ---------------------------------------------------------------------------
# Datapack commands
# ---------------------------------------------------------------------------

def cmd_add_dp(config, slug):
    if any(d["slug"] == slug for d in config.get("datapacks", [])):
        print(f"'{slug}' is already in the datapack list.")
        return
    print(f"Looking up '{slug}' on Modrinth...", end="", flush=True)
    name = get_project_name(slug)
    print(f"  found: {name}")
    config.setdefault("datapacks", []).append({"slug": slug, "name": name, "file": None, "pending": True})
    save_config(config)
    print(f"Added datapack '{name}'. Run 'upgrade' to download it.")


def cmd_remove_dp(config, slug):
    dp = next((d for d in config.get("datapacks", []) if d["slug"] == slug), None)
    if not dp:
        print(f"No managed datapack with slug '{slug}' found.")
        return
    name = dp.get("name", slug)
    if dp.get("file"):
        if delete_file(config.get("mods_dir", ""), dp["file"]):
            print(f"Deleted file: {dp['file']}")
    config["datapacks"] = [d for d in config["datapacks"] if d["slug"] != slug]
    save_config(config)
    print(f"Removed datapack '{name}' from the list.")


def cmd_add_manual_dp(config, filename):
    config.setdefault("manual_datapacks", [])
    if filename in config["manual_datapacks"]:
        print(f"'{filename}' is already registered as a manual datapack.")
        return
    dp_dir = config.get("mods_dir", "")
    if dp_dir and not (Path(dp_dir) / filename).exists():
        print(f"Note: '{filename}' not found in datapacks directory yet.")
    config["manual_datapacks"].append(filename)
    save_config(config)
    print(f"Registered manual datapack: {filename}")


def cmd_remove_manual_dp(config, filename):
    if filename not in config.get("manual_datapacks", []):
        print(f"'{filename}' is not registered as a manual datapack.")
        return
    config["manual_datapacks"].remove(filename)
    save_config(config)
    print(f"Unregistered manual datapack: {filename} (file not deleted)")


def cmd_legacy_on_dp(config, slug, legacy_version):
    dp = next((d for d in config.get("datapacks", []) if d["slug"] == slug), None)
    if not dp:
        print(f"No managed datapack with slug '{slug}' found. Add it first with 'add_dp'.")
        return
    dp["legacy_version"] = legacy_version
    save_config(config)
    print(f"Legacy fallback set for '{dp.get('name', slug)}': will use {legacy_version} if {config['mc_version']} is unavailable.")
    print("Running upgrade to apply...")
    cmd_upgrade(config)


def cmd_legacy_off_dp(config, slug):
    dp = next((d for d in config.get("datapacks", []) if d["slug"] == slug), None)
    if not dp:
        print(f"No managed datapack with slug '{slug}' found.")
        return
    if dp.get("file") and dp.get("legacy_active"):
        if delete_file(config.get("mods_dir", ""), dp["file"]):
            print(f"Deleted legacy file: {dp['file']}")
        dp["file"] = None
    dp["pending"]       = True
    dp["legacy_active"] = False
    dp.pop("legacy_version", None)
    save_config(config)
    print(f"Legacy mode cleared for '{dp.get('name', slug)}'. Marked as pending — run 'upgrade' to retry current version.")


def cmd_link_dp(config, slug, filename):
    entry = next((d for d in config.get("datapacks", []) if d["slug"] == slug), None)
    if not entry:
        print(f"No managed datapack with slug '{slug}' found. Add it first.")
        return
    d = config.get("mods_dir", "")
    if d and not (Path(d) / filename).exists():
        print(f"Note: '{filename}' not found in the datapacks directory yet — linking anyway.")
    entry["file"]    = filename
    entry["pending"] = False
    save_config(config)
    print(f"Linked '{filename}' to datapack '{entry.get('name', slug)}'.")
    print("You can now 'freeze' it to keep this file across upgrades.")


def cmd_choose_dp(config, slug):
    dp = next((d for d in config.get("datapacks", []) if d["slug"] == slug), None)
    if not dp:
        print(f"No managed datapack with slug '{slug}' found.")
        return
    dp["choose"] = True
    save_config(config)
    print(f"Manual version selection enabled for '{dp.get('name', slug)}'.")


def cmd_unchoose_dp(config, slug):
    dp = next((d for d in config.get("datapacks", []) if d["slug"] == slug), None)
    if not dp:
        print(f"No managed datapack with slug '{slug}' found.")
        return
    dp.pop("choose", None)
    dp.pop("chosen_version_id", None)
    dp.pop("skipped_version_id", None)
    save_config(config)
    print(f"Manual version selection disabled for '{dp.get('name', slug)}'. It will auto-update normally from now on.")


def cmd_unchoose_all_dp(config):
    count = 0
    for dp in config.get("datapacks", []):
        if dp.get("choose"):
            dp.pop("choose", None)
            dp.pop("chosen_version_id", None)
            dp.pop("skipped_version_id", None)
            count += 1
    save_config(config)
    print(f"Cleared manual version selection from {count} datapack{'s' if count != 1 else ''}.")


# ---------------------------------------------------------------------------
# Freeze / unfreeze (mods + datapacks)
# ---------------------------------------------------------------------------

_FREEZE_CATEGORIES = [("mods", "mods"), ("datapacks", "datapacks")]


def _find_entry(config, slug):
    for key, _ in _FREEZE_CATEGORIES:
        for e in config.get(key, []):
            if e["slug"] == slug:
                return e, key
    return None, None


def cmd_freeze(config, target):
    if target == "all":
        names = []
        for key, _ in _FREEZE_CATEGORIES:
            for e in config.get(key, []):
                e["frozen"] = True
                names.append(e.get("name", e["slug"]))
        save_config(config)
        print(f"Froze {len(names)} entr{'y' if len(names) == 1 else 'ies'}. They will be skipped during upgrade until unfrozen.")
        return

    entry, _ = _find_entry(config, target)
    if not entry:
        print(f"No managed mod/datapack with slug '{target}' found.")
        return
    entry["frozen"] = True
    save_config(config)
    print(f"Froze '{entry.get('name', target)}'. It will be skipped during upgrade until unfrozen.")


def cmd_unfreeze(config, target):
    if target == "all":
        count = 0
        for key, _ in _FREEZE_CATEGORIES:
            for e in config.get(key, []):
                if e.pop("frozen", None):
                    count += 1
        save_config(config)
        print(f"Unfroze {count} entr{'y' if count == 1 else 'ies'}. They will update on the next upgrade.")
        return

    entry, _ = _find_entry(config, target)
    if not entry:
        print(f"No managed mod/datapack with slug '{target}' found.")
        return
    if not entry.pop("frozen", None):
        print(f"'{entry.get('name', target)}' was not frozen.")
        return
    save_config(config)
    print(f"Unfroze '{entry.get('name', target)}'. It will update on the next upgrade.")


# ---------------------------------------------------------------------------
# Clear
# ---------------------------------------------------------------------------

def _clear_entry(entry, entries_dir):
    if entry.get("file"):
        if delete_file(entries_dir, entry["file"]):
            print(f"  Deleted: {entry['file']}")
    entry["file"]    = None
    entry["pending"] = True


def cmd_clear(config, target):
    do_mods = target in ("all", "mods")
    do_dp   = target in ("all", "dp", "datapacks")

    if do_mods or do_dp:
        if do_mods:
            print("Mods (deleting files):")
            if not config.get("mods"):
                print("  (none)")
            for mod in config.get("mods", []):
                _clear_entry(mod, config.get("mods_dir", ""))
        if do_dp:
            print("Datapacks (deleting files):")
            if not config.get("datapacks"):
                print("  (none)")
            for dp in config.get("datapacks", []):
                _clear_entry(dp, config.get("mods_dir", ""))
        save_config(config)
        print("\nCleared. Run 'upgrade' to re-download non-frozen entries.")
        return

    entry, key = _find_entry(config, target)
    if not entry:
        print(f"No managed mod/datapack with slug '{target}' found.")
        return
    dir_key = "mods_dir" if key == "mods" else "mods_dir"
    print(f"Clearing '{entry.get('name', target)}':")
    _clear_entry(entry, config.get(dir_key, ""))
    save_config(config)
    if entry.get("frozen"):
        print("Note: this entry is frozen, so 'upgrade' will NOT re-download it. Unfreeze first.")
    print("Done.")


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

def _entry_status(entry):
    if entry.get("frozen"):     return "FROZEN"
    if entry.get("choose"):     return "CHOOSE"
    if entry.get("legacy_active"): return "LEGACY"
    if entry.get("pending"):    return "PENDING"
    return "OK"


def cmd_list(config):
    print(f"Minecraft {config['mc_version']}  |  loader: {config['loader']}")
    print(f"Download dir:  {config.get('mods_dir', '(not set)')}")
    print()

    for label, entries_key, manual_key in [
        ("Mods",      "mods",      "manual_mods"),
        ("Datapacks", "datapacks", "manual_datapacks"),
    ]:
        entries = config.get(entries_key, [])
        print(f"=== {label} ===")
        if entries:
            for e in entries:
                status   = _entry_status(e)
                fileinfo = e.get("file") or "(no file)"
                name     = e.get("name", e["slug"])
                legacy   = f"  [legacy fallback: {e['legacy_version']}]" if e.get("legacy_version") else ""
                print(f"  [{status:8s}]  {name} ({e['slug']})  —  {fileinfo}{legacy}")
        else:
            print("  (none)")

        manual = config.get(manual_key, [])
        if manual:
            print(f"\n  Manual {label.lower()}:")
            for f in manual:
                print(f"    {f}")
        print()

    frozen = []
    for key, _ in _FREEZE_CATEGORIES:
        frozen += [e.get("name", e["slug"]) for e in config.get(key, []) if e.get("frozen")]
    if frozen:
        print(f"❄  Frozen ({len(frozen)}): {', '.join(frozen)}")


def print_help():
    print(f"""
Mcmods_server.py — Minecraft server mod/datapack manager  (version {SCRIPT_VERSION}, {SCRIPT_VERSION_DATE})

Every command below is run as:  python Mcmods_server.py <profile> <command> [args...]
<profile> selects Mcmods_server_<profile>.json next to this script. The download
directory is a full path you type in at 'init' (not auto-derived from where this
script lives), so give each profile its own folder to keep servers isolated.
A profile is created the first time you run its 'init', and deleted simply by
deleting its Mcmods_server_<profile>.json file — there's no dedicated delete command.

Commands:
  init                            Interactive setup — creates the config file
  upgrade [slug]                  Download/update all mods and datapacks. With a slug,
                                  only that one mod/datapack is checked/upgraded (still
                                  respects its FROZEN/CHOOSE flags).
  set-version <version>           Change MC version and immediately run upgrade
  list                            Show all entries (incl. FROZEN status)

  --- Mods ---
  add <slug>                      Add a mod by Modrinth slug
  remove <slug>                   Remove a mod (also deletes the JAR)
  add-manual <filename>           Register a manual JAR (never touched by upgrade)
  remove-manual <filename>        Unregister a manual mod (file is NOT deleted)
  legacy_on <slug> <version>      Set a legacy fallback version for a mod
  legacy_off <slug>               Clear legacy mode, delete legacy file, mark pending
  link <slug> <filename>          Attach a manually downloaded file to a managed mod
  choose <slug>                   Flag a mod for manual version selection on upgrade
  unchoose <slug>                 Remove the flag, resume auto-updating
  unchoose_all                    Remove the choose flag from every mod

  --- Datapacks ---
  add_dp <slug>                   Add a datapack by Modrinth slug
  remove_dp <slug>                Remove a datapack (also deletes the file)
  add_manual_dp <filename>        Register a manual datapack (never touched by upgrade)
  remove_manual_dp <filename>     Unregister a manual datapack (file is NOT deleted)
  legacy_on_dp <slug> <version>   Set a legacy fallback version for a datapack
  legacy_off_dp <slug>            Clear legacy mode, delete legacy file, mark pending
  link_dp <slug> <filename>       Attach a manually downloaded file to a managed datapack
  choose_dp <slug>                Flag a datapack for manual version selection on upgrade
  unchoose_dp <slug>              Remove the flag, resume auto-updating
  unchoose_all_dp                 Remove the choose flag from every datapack

  --- Freeze / clear ---
  freeze <slug|all>               Pin: keep the current file, skip updating it
  unfreeze <slug|all>             Resume normal updating
  clear <slug|all|mods|dp>        Delete files (re-downloaded on next upgrade unless frozen)

  --- Manual version selection ---
  upgrade_chooseall               Re-show the version picker for all choose-flagged entries
  upgrade_masterchoose            Show the version picker for every entry

  help                            Show this help text

Notes:
  - 'upgrade <slug>' upgrades just that one mod/datapack — everything else in the
    profile is left untouched. Plain 'upgrade' (no slug) still does all of them.
  - Datapacks use the 'datapack' loader on Modrinth (independent of the mod loader).
  - Slugs are the last part of the Modrinth URL, e.g. 'terralith' or 'tectonic'.
  - Config file is Mcmods_server_<profile>.json next to this script, e.g.
    'survival' → Mcmods_server_survival.json.
""")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _available_profiles():
    names = []
    for p in SCRIPT_DIR.glob("Mcmods_server_*.json"):
        names.append(p.stem[len("Mcmods_server_"):])
    return sorted(names)


def main():
    global CONFIG_FILE

    args = sys.argv[1:]

    if not args or args[0] in ("help", "--help", "-h"):
        print_help()
        return

    profile = args[0]

    if len(args) < 2:
        print(f"Usage: python Mcmods_server.py {profile} <command> [args...]")
        print("Run 'python Mcmods_server.py help' for the full command list.")
        sys.exit(1)

    cmd  = args[1]
    rest = args[2:]

    if cmd in ("help", "--help", "-h"):
        print_help()
        return

    CONFIG_FILE = SCRIPT_DIR / f"Mcmods_server_{profile}.json"

    if cmd == "init":
        cmd_init()
        return

    if not CONFIG_FILE.exists():
        print(f"No config found for profile '{profile}' (expected {CONFIG_FILE.name}).")
        available = _available_profiles()
        if available:
            print(f"Available profiles: {', '.join(available)}")
        print(f"Run 'python Mcmods_server.py {profile} init' to create it, or check for typos.")
        sys.exit(1)

    config = load_config()

    if cmd == "upgrade":
        cmd_upgrade(config, rest[0] if rest else None)
    elif cmd == "upgrade_chooseall":
        cmd_upgrade_chooseall(config)
    elif cmd == "upgrade_masterchoose":
        cmd_upgrade_masterchoose(config)
    elif cmd == "set-version":
        if len(rest) < 1: print(f"Usage: python Mcmods_server.py {profile} set-version <version>"); sys.exit(1)
        cmd_set_version(config, rest[0])
    elif cmd == "list":
        cmd_list(config)

    # Mods
    elif cmd == "add":
        if len(rest) < 1: print(f"Usage: python Mcmods_server.py {profile} add <slug>"); sys.exit(1)
        cmd_add(config, rest[0])
    elif cmd == "remove":
        if len(rest) < 1: print(f"Usage: python Mcmods_server.py {profile} remove <slug>"); sys.exit(1)
        cmd_remove(config, rest[0])
    elif cmd == "add-manual":
        if len(rest) < 1: print(f"Usage: python Mcmods_server.py {profile} add-manual <filename>"); sys.exit(1)
        cmd_add_manual(config, rest[0])
    elif cmd == "remove-manual":
        if len(rest) < 1: print(f"Usage: python Mcmods_server.py {profile} remove-manual <filename>"); sys.exit(1)
        cmd_remove_manual(config, rest[0])
    elif cmd == "legacy_on":
        if len(rest) < 2: print(f"Usage: python Mcmods_server.py {profile} legacy_on <slug> <version>"); sys.exit(1)
        cmd_legacy_on(config, rest[0], rest[1])
    elif cmd == "legacy_off":
        if len(rest) < 1: print(f"Usage: python Mcmods_server.py {profile} legacy_off <slug>"); sys.exit(1)
        cmd_legacy_off(config, rest[0])
    elif cmd == "link":
        if len(rest) < 2: print(f"Usage: python Mcmods_server.py {profile} link <slug> <filename>"); sys.exit(1)
        cmd_link(config, rest[0], rest[1])
    elif cmd == "choose":
        if len(rest) < 1: print(f"Usage: python Mcmods_server.py {profile} choose <slug>"); sys.exit(1)
        cmd_choose(config, rest[0])
    elif cmd == "unchoose":
        if len(rest) < 1: print(f"Usage: python Mcmods_server.py {profile} unchoose <slug>"); sys.exit(1)
        cmd_unchoose(config, rest[0])
    elif cmd == "unchoose_all":
        cmd_unchoose_all(config)

    # Datapacks
    elif cmd == "add_dp":
        if len(rest) < 1: print(f"Usage: python Mcmods_server.py {profile} add_dp <slug>"); sys.exit(1)
        cmd_add_dp(config, rest[0])
    elif cmd == "remove_dp":
        if len(rest) < 1: print(f"Usage: python Mcmods_server.py {profile} remove_dp <slug>"); sys.exit(1)
        cmd_remove_dp(config, rest[0])
    elif cmd == "add_manual_dp":
        if len(rest) < 1: print(f"Usage: python Mcmods_server.py {profile} add_manual_dp <filename>"); sys.exit(1)
        cmd_add_manual_dp(config, rest[0])
    elif cmd == "remove_manual_dp":
        if len(rest) < 1: print(f"Usage: python Mcmods_server.py {profile} remove_manual_dp <filename>"); sys.exit(1)
        cmd_remove_manual_dp(config, rest[0])
    elif cmd == "legacy_on_dp":
        if len(rest) < 2: print(f"Usage: python Mcmods_server.py {profile} legacy_on_dp <slug> <version>"); sys.exit(1)
        cmd_legacy_on_dp(config, rest[0], rest[1])
    elif cmd == "legacy_off_dp":
        if len(rest) < 1: print(f"Usage: python Mcmods_server.py {profile} legacy_off_dp <slug>"); sys.exit(1)
        cmd_legacy_off_dp(config, rest[0])
    elif cmd == "link_dp":
        if len(rest) < 2: print(f"Usage: python Mcmods_server.py {profile} link_dp <slug> <filename>"); sys.exit(1)
        cmd_link_dp(config, rest[0], rest[1])
    elif cmd == "choose_dp":
        if len(rest) < 1: print(f"Usage: python Mcmods_server.py {profile} choose_dp <slug>"); sys.exit(1)
        cmd_choose_dp(config, rest[0])
    elif cmd == "unchoose_dp":
        if len(rest) < 1: print(f"Usage: python Mcmods_server.py {profile} unchoose_dp <slug>"); sys.exit(1)
        cmd_unchoose_dp(config, rest[0])
    elif cmd == "unchoose_all_dp":
        cmd_unchoose_all_dp(config)

    # Freeze / clear
    elif cmd == "freeze":
        if len(rest) < 1: print(f"Usage: python Mcmods_server.py {profile} freeze <slug|all>"); sys.exit(1)
        cmd_freeze(config, rest[0])
    elif cmd == "unfreeze":
        if len(rest) < 1: print(f"Usage: python Mcmods_server.py {profile} unfreeze <slug|all>"); sys.exit(1)
        cmd_unfreeze(config, rest[0])
    elif cmd == "clear":
        if len(rest) < 1: print(f"Usage: python Mcmods_server.py {profile} clear <slug|all|mods|dp>"); sys.exit(1)
        cmd_clear(config, rest[0])

    else:
        print(f"Unknown command: '{cmd}'")
        print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
