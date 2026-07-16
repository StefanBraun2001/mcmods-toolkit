# Written by Claude Opus 4.8 / Claude Sonnet 5
#!/usr/bin/env python3
"""
Mcmods.py - Minecraft mod/resourcepack/shaderpack manager (Modrinth + manual)

Version: R_1.3 (2026-07-16)

Single script for every game profile (Main, Side, a test install, ...). The
profile is now the first CLI argument instead of being baked into the
filename — this replaced what used to be separate Mcmods_<profile>.py copies
(Mcmods_templatev2.py, Mcmods_main.py, Mcmods_side.py, Mcmods_meiktest.py).
Each profile's config is still just Mcmods_<profile>.json next to this
script, so existing config files keep working unchanged.

Features:
  - freeze / unfreeze: keep a mod/pack at its current file and skip updating it.
    Frozen entries are listed (with a warning) in the upgrade summary.
  - clear: delete mod files and quarantine resource/shader packs (incl. the shader
    .txt config) into a dedicated quarantine folder. Works on one entry or on all.
  - quarantine folder location is asked during init. If a file of the same name
    already exists there, the incoming dupe is moved into a Dupes_HH_mm_ss subfolder.
  - link / link_rp / link_sp: attach a manually downloaded file to a managed entry
    (e.g. so you can freeze it) without registering a separate "manual" item.
  - unload / load: temporarily move a mod/pack's file into the depot folder
    without losing it from the config. Unloaded entries are still
    upgraded/frozen/chosen normally (the file just lives in the depot instead of
    the active folder) and are flagged with a warning in the upgrade summary.
    'load' moves the file back but does NOT check for updates.
  - shelf / unshelf: whole-profile flag for a temporarily unused install.
    While shelved, 'upgrade' is blocked outright with an error; every other
    command warns and requires explicit confirmation before it runs.
  - add_dp / remove_dp / etc.: datapacks, tracked and auto-updated from
    Modrinth like everything else, but since a datapack belongs to a world
    (not an install), its file is kept in the depot's "Datapacks" subfolder
    instead of any live game folder — you copy it into a world yourself.
    Updated datapacks get a loud 🔔 callout in the upgrade summary so you
    notice there's something new to copy over.
  - The depot folder is now split into a "Shelf" subfolder (unloaded mod/pack
    files) and a "Datapacks" subfolder (datapack depot copies). Older loose
    files sitting directly in the depot root are swept into Shelf
    automatically the next time the script runs.
  - config: batch-add every mod/resourcepack/shaderpack/datapack slug listed
    in a preset file (Presets/Clients/<preset>.json next to this script,
    matched case-insensitively), then offers to add extra mods by hand and
    to run 'upgrade' immediately. add/add_rp/add_sp/add_dp all accept
    multiple space-separated slugs in one call, too.

Usage:
  python Mcmods.py <profile> init
  python Mcmods.py <profile> upgrade [slug]        # omit slug to upgrade everything
  python Mcmods.py <profile> set-version <version>
  python Mcmods.py <profile> config <preset>        # batch-add every slug from a preset file

  python Mcmods.py <profile> add <slug> [slug2 ...]  # mods
  python Mcmods.py <profile> remove <slug>
  python Mcmods.py <profile> add-manual <filename>
  python Mcmods.py <profile> remove-manual <filename>
  python Mcmods.py <profile> legacy_on <slug> <version>
  python Mcmods.py <profile> legacy_off <slug>
  python Mcmods.py <profile> link <slug> <filename>

  python Mcmods.py <profile> add_rp <slug> [slug2 ...]  # resource packs
  python Mcmods.py <profile> remove_rp <slug>
  python Mcmods.py <profile> add_manual_rp <filename>
  python Mcmods.py <profile> remove_manual_rp <filename>
  python Mcmods.py <profile> link_rp <slug> <filename>

  python Mcmods.py <profile> add_sp <slug> [slug2 ...]  # shader packs
  python Mcmods.py <profile> remove_sp <slug>
  python Mcmods.py <profile> add_manual_sp <filename>
  python Mcmods.py <profile> remove_manual_sp <filename>
  python Mcmods.py <profile> link_sp <slug> <filename>

  python Mcmods.py <profile> add_dp <slug> [slug2 ...]  # datapacks (kept in depot/Datapacks)
  python Mcmods.py <profile> remove_dp <slug>
  python Mcmods.py <profile> add_manual_dp <filename>
  python Mcmods.py <profile> remove_manual_dp <filename>
  python Mcmods.py <profile> link_dp <slug> <filename>

  python Mcmods.py <profile> freeze <slug|all>      # pin (keep file, skip updates)
  python Mcmods.py <profile> unfreeze <slug|all>
  python Mcmods.py <profile> unload <slug|all>      # move file to depot
  python Mcmods.py <profile> load <slug|all>        # move file back, no update check
  python Mcmods.py <profile> clear <slug|all|mods|rp|sp|dp>  # delete mods / quarantine packs

  python Mcmods.py <profile> shelf                  # block upgrades, warn on everything else
  python Mcmods.py <profile> unshelf

  python Mcmods.py <profile> choose <slug>          # manual version selection on upgrade
  python Mcmods.py <profile> unchoose <slug>
  python Mcmods.py <profile> upgrade_chooseall      # re-prompt all choose-flagged mods

  python Mcmods.py <profile> list

  python Mcmods.py help                             # this text (no profile needed)

A profile is deleted simply by deleting its Mcmods_<profile>.json file — there
is no dedicated 'delete profile' command.
"""

import json
import os
import sys
import shutil
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from pathlib import Path

# Windows consoles often default to a legacy codepage (e.g. cp1252) that can't
# encode the icons used below (📦 ❄ ✎ etc.) — reconfigure to UTF-8 so printing
# them degrades gracefully instead of crashing with UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_VERSION      = "R_1.3"
SCRIPT_VERSION_DATE = "2026-07-16"
SCRIPT_DIR          = Path(__file__).parent

CONFIG_FILE = None  # set in main() once the profile is known
MODRINTH_API = "https://api.modrinth.com/v2"
USER_AGENT = "mcmods-script/2.0"

# ANSI color helpers — gracefully disabled if the terminal doesn't support them.
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
            # Enable VIRTUAL_TERMINAL_PROCESSING (0x0004)
            kernel.SetConsoleMode(kernel.GetStdHandle(-11), 7)
            return True
        except Exception:
            return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

_COLOR = _supports_color()

def green(s):   return f"{_GREEN}{s}{_RESET}"  if _COLOR else s
def yellow(s):  return f"{_YELLOW}{s}{_RESET}" if _COLOR else s
def cyan(s):    return f"{_CYAN}{s}{_RESET}"   if _COLOR else s
def bold(s):    return f"{_BOLD}{s}{_RESET}"   if _COLOR else s


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
# Modrinth API (stdlib only — no requests dependency)
# ---------------------------------------------------------------------------

def modrinth_get(path, params=None):
    url = f"{MODRINTH_API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def get_all_versions(slug, mc_version, loader):
    """
    Returns (list of version dicts newest-first, None) on success,
            (None, "not_available") if nothing found,
            (None, "error: ...") on failure.
    """
    try:
        params = {
            "game_versions": json.dumps([mc_version]),
            "loaders": json.dumps([loader]),
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
    """
    Returns (version_info dict, None) on success,
            (None, "not_available") if no release exists for this version,
            (None, "error: ...") on network/API failure.
    """
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


def rename_shader_config(shaders_dir, old_filename, new_filename):
    """Rename the .txt config sidecar when a shaderpack file is replaced."""
    if not old_filename or old_filename == new_filename:
        return
    old_cfg = Path(shaders_dir) / (old_filename + ".txt")
    new_cfg = Path(shaders_dir) / (new_filename + ".txt")
    if old_cfg.exists():
        old_cfg.rename(new_cfg)
        print(f"    Config renamed: {old_cfg.name}  →  {new_cfg.name}")


def get_quarantine_dir(config):
    qdir = config.get("quarantine_dir", "")
    if not qdir:
        print("No quarantine directory configured.")
        print("Re-run 'init' or add a \"quarantine_dir\" path to the config file.")
        sys.exit(1)
    return qdir


def get_depot_dir(config):
    ddir = config.get("depot_dir", "")
    if not ddir:
        print("No depot directory configured.")
        print("Re-run 'init' or add a \"depot_dir\" path to the config file.")
        sys.exit(1)
    return ddir


def get_shelf_dir(config):
    """Where unloaded mod/pack files actually live: depot_dir/Shelf."""
    return str(Path(get_depot_dir(config)) / "Shelf")


def get_datapack_depot_dir(config):
    """Where datapack files live: depot_dir/Datapacks. Datapacks are per-world,
    so unlike mods/rp/sp there is no live game folder to keep them in — the
    depot copy IS the managed copy; you copy it into a world by hand."""
    return str(Path(get_depot_dir(config)) / "Datapacks")


def migrate_depot_layout(config):
    """
    Older configs kept unloaded files directly in depot_dir. Make sure the
    Shelf/Datapacks subfolders exist and sweep any loose files left over
    from that flat layout into Shelf, so upgrading this script doesn't
    strand anything.
    """
    ddir = config.get("depot_dir", "")
    if not ddir:
        return
    depot = Path(ddir)
    shelf = depot / "Shelf"
    datapacks = depot / "Datapacks"
    shelf.mkdir(parents=True, exist_ok=True)
    datapacks.mkdir(parents=True, exist_ok=True)
    if not depot.exists():
        return
    for item in depot.iterdir():
        if item.is_file():
            dest = shelf / item.name
            if not dest.exists():
                shutil.move(str(item), str(dest))


def quarantine_file(quarantine_dir, src_path):
    """
    Move src_path into the quarantine folder. If a file of the same name already
    exists there, the incoming dupe is moved into a Dupes_HH_mm_ss subfolder so the
    existing file is left untouched. Returns the destination Path, or None.
    """
    src = Path(src_path)
    if not src.exists():
        return None
    qdir = Path(quarantine_dir)
    qdir.mkdir(parents=True, exist_ok=True)

    dest = qdir / src.name
    if dest.exists():
        sub = qdir / datetime.now().strftime("Dupes_%H_%M_%S")
        sub.mkdir(parents=True, exist_ok=True)
        dest = sub / src.name
        # Guard against a clash inside the subfolder too (very unlikely).
        if dest.exists():
            dest = sub / f"{src.stem}_{datetime.now().strftime('%f')}{src.suffix}"

    shutil.move(str(src), str(dest))
    return dest


def move_managed_file(filename, src_dir, dest_dir):
    """
    Move filename from src_dir to dest_dir, keeping the same name.
    Returns (dest_path, None) on success, (None, "missing") if the source
    file doesn't exist, or (None, "conflict") if dest_dir already has a
    file of that name (never silently overwritten).
    """
    src = Path(src_dir) / filename
    if not src.exists():
        return None, "missing"
    dest_path = Path(dest_dir)
    dest_path.mkdir(parents=True, exist_ok=True)
    dest = dest_path / filename
    if dest.exists():
        return None, "conflict"
    shutil.move(str(src), str(dest))
    return dest, None


def entry_dir(config, entry, dir_key):
    """
    Where an entry's file actually lives right now. Datapacks always live in
    the depot's Datapacks subfolder (there's no live game folder for them —
    they're per-world). Everything else lives in the depot's Shelf subfolder
    if unloaded, otherwise in its normal category directory.
    """
    if dir_key == "datapacks_dir":
        return get_datapack_depot_dir(config)
    if entry.get("unloaded"):
        return get_shelf_dir(config)
    return config.get(dir_key, "")


# ---------------------------------------------------------------------------
# Generic upgrade logic for resource packs and shader packs
# ---------------------------------------------------------------------------

def upgrade_pack_category(config, category_key, dir_key, loader, keep_outdated=True, only_slug=None):
    """
    Upgrade one category of packs (resourcepacks or shaderpacks).
    keep_outdated=True: if no new version found, keep file and mark OUTDATED.
    only_slug: if given, only that single pack is processed.
    Returns (updated, ok, outdated, errors, frozen, unloaded, redownloaded) name lists.
    'redownloaded' entries are NOT a new version — the recorded version was still
    current, but its file had gone missing (moved/deleted by hand), so it was
    silently re-fetched. Kept separate from 'updated' so callers don't mistake a
    fail-safe re-fetch for an actual new release.
    """
    mc_version = config["mc_version"]
    dirty      = False

    updated      = []
    ok           = []
    outdated     = []
    errors       = []
    frozen       = []
    unloaded     = []
    redownloaded = []

    packs = config.get(category_key, [])
    if only_slug is not None:
        packs = [p for p in packs if p["slug"] == only_slug]

    for pack in packs:
        slug = pack["slug"]
        name = pack.get("name", slug)
        is_shader = (category_key == "shaderpacks")
        packs_dir = entry_dir(config, pack, dir_key)

        if pack.get("unloaded"):
            unloaded.append(name)

        if pack.get("frozen"):
            frozen.append(name)
            continue

        version_info, error = get_latest_version(slug, mc_version, loader)

        if error == "not_available" or (error and "not_available" in error):
            if keep_outdated:
                pack["outdated"] = True
                dirty = True
                outdated.append(name)
            else:
                if pack.get("file"):
                    delete_file(packs_dir, pack["file"])
                    pack["file"] = None
                    dirty = True
                pack["pending"] = True
                dirty = True
                outdated.append(name)

        elif error:
            errors.append((name, error))

        else:
            files   = version_info.get("files", [])
            primary = next((f for f in files if f.get("primary")), files[0] if files else None)

            if not primary:
                errors.append((name, "no downloadable file in API response"))
                continue

            new_filename = primary["filename"]

            file_present = pack.get("file") and (Path(packs_dir) / pack["file"]).exists()
            if file_present and pack.get("file") == new_filename and not pack.get("pending") and not pack.get("outdated"):
                ok.append(name)
                continue

            same_version_missing = (
                pack.get("file") == new_filename and not file_present
                and not pack.get("pending") and not pack.get("outdated")
            )

            old_filename = pack.get("file")

            if old_filename and old_filename != new_filename:
                delete_file(packs_dir, old_filename)

            dest = Path(packs_dir) / new_filename
            print(f"  Downloading {name}  ({new_filename}) ...", end="", flush=True)
            try:
                download_file(primary["url"], dest)
                print("  OK")

                if is_shader and old_filename and old_filename != new_filename:
                    rename_shader_config(packs_dir, old_filename, new_filename)

                pack["file"]     = new_filename
                pack["pending"]  = False
                pack["outdated"] = False
                dirty = True
                if same_version_missing:
                    redownloaded.append(name)
                else:
                    updated.append(name)
            except Exception as e:
                print("  FAILED")
                errors.append((name, str(e)))

    if dirty:
        save_config(config)

    return updated, ok, outdated, errors, frozen, unloaded, redownloaded


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_init():
    if CONFIG_FILE.exists():
        print(f"Config already exists at {CONFIG_FILE}. Delete it first to re-init.")
        return

    print("=== mcmods setup ===\n")
    mc_version    = input("Minecraft version (e.g. 1.21.4):          ").strip()
    loader        = input("Mod loader (e.g. fabric):                  ").strip().lower()
    mods_dir      = input("Mods directory (full path):                ").strip().strip('"')
    rp_dir        = input("Resourcepacks directory (full path):       ").strip().strip('"')
    sp_dir        = input("Shaderpacks directory (full path):         ").strip().strip('"')
    quarantine    = input("Quarantine directory (full path):          ").strip().strip('"')
    depot         = input("Depot directory (full path, for unload):   ").strip().strip('"')
    shader_loader = input("Shader loader (iris / optifine) [iris]:    ").strip().lower() or "iris"

    config = {
        "mc_version":           mc_version,
        "loader":               loader,
        "shader_loader":        shader_loader,
        "mods_dir":             mods_dir,
        "resourcepacks_dir":    rp_dir,
        "shaderpacks_dir":      sp_dir,
        "quarantine_dir":       quarantine,
        "depot_dir":            depot,
        "mods":                 [],
        "manual_mods":          [],
        "resourcepacks":        [],
        "manual_resourcepacks": [],
        "shaderpacks":          [],
        "manual_shaderpacks":   [],
        "datapacks":            [],
        "manual_datapacks":     [],
    }
    save_config(config)
    migrate_depot_layout(config)
    print(f"\nConfig saved to {CONFIG_FILE}")
    print(f"Datapacks (once added) are kept in: {get_datapack_depot_dir(config)}")


def cmd_upgrade(config, target=None):
    mc_version    = config["mc_version"]
    loader        = config["loader"]
    shader_loader = config.get("shader_loader", "iris")
    mods_dir      = config["mods_dir"]

    only_key = None
    if target is not None:
        entry, only_key = _find_entry(config, target)
        if not entry:
            print(f"No managed mod/pack with slug '{target}' found.")
            sys.exit(1)
        print(f"Upgrading only '{entry.get('name', target)}' — Minecraft {mc_version} ({loader})\n")
    else:
        print(f"Upgrading for Minecraft {mc_version} ({loader})\n")

    mods_updated  = []
    mods_ok       = []
    mods_pending  = []
    mods_legacy   = []   # (name, legacy_version)
    mods_errors   = []
    mods_frozen   = []
    mods_unloaded = []
    mods_choose   = []   # (name, detail_string)
    mods_skipped  = []   # name — choose-flagged but no new version to prompt
    mods_redownloaded = []   # name — same version, file was missing, silently refetched
    dirty         = False

    mods_to_process = config.get("mods", [])
    if only_key is not None:
        mods_to_process = [m for m in mods_to_process if m["slug"] == target] if only_key == "mods" else []

    for mod in mods_to_process:
        slug          = mod["slug"]
        name          = mod.get("name", slug)
        legacy_ver    = mod.get("legacy_version")
        mod_dir       = entry_dir(config, mod, "mods_dir")

        if mod.get("unloaded"):
            mods_unloaded.append(name)

        if mod.get("frozen"):
            mods_frozen.append(name)
            continue

        versions, error = get_all_versions(slug, mc_version, loader)
        is_not_available = error == "not_available" or (error and "not_available" in error)

        if mod.get("choose") and versions and not is_not_available:
            result = _upgrade_mod_with_choose(config, mod, versions, mods_dir, force_prompt=False)
            dirty = True
            if result == "updated":
                mods_updated.append(name)
                vtype = versions[0].get("version_type", "?")
                vnum  = versions[0].get("version_number", "?")
                mods_choose.append((name, green(f"manual selection — updated to {vnum} [{vtype}]")))
            elif result == "redownloaded":
                mods_redownloaded.append(name)
                vtype = versions[0].get("version_type", "?")
                vnum  = versions[0].get("version_number", "?")
                mods_choose.append((name, cyan(f"manual selection — redownloaded (file was missing, still {vnum} [{vtype}])")))
            elif result == "ok":
                mods_ok.append(name)
                vtype = versions[0].get("version_type", "?")
                vnum  = versions[0].get("version_number", "?")
                mods_choose.append((name, green(f"manual selection — up to date ({vnum} [{vtype}])")))
            elif result == "skipped":
                mods_skipped.append(name)
                vtype = versions[0].get("version_type", "?")
                vnum  = versions[0].get("version_number", "?")
                mods_choose.append((name, yellow(f"manual selection — skipped {vnum} [{vtype}]")))
            else:
                mods_errors.append((name, result[1]))
                mods_choose.append((name, "manual selection — error"))
            save_config(config)
            continue

        version_info = versions[0] if versions else None

        if version_info and not is_not_available and not error:
            # Current version available
            files   = version_info.get("files", [])
            primary = next((f for f in files if f.get("primary")), files[0] if files else None)

            if not primary:
                mods_errors.append((name, "no downloadable file in API response"))
                continue

            new_filename = primary["filename"]

            file_present = mod.get("file") and (Path(mod_dir) / mod["file"]).exists()
            if file_present and mod.get("file") == new_filename and not mod.get("pending") and not mod.get("legacy_active"):
                mods_ok.append(name)
                continue

            same_version_missing = (
                mod.get("file") == new_filename and not file_present
                and not mod.get("pending") and not mod.get("legacy_active")
            )

            old_filename = mod.get("file")
            if old_filename and old_filename != new_filename:
                delete_file(mod_dir, old_filename)

            dest = Path(mod_dir) / new_filename
            print(f"  Downloading {name}  ({new_filename}) ...", end="", flush=True)
            try:
                download_file(primary["url"], dest)
                print("  OK")
                if mod.get("legacy_active"):
                    print(f"    Legacy mode cleared — now on current version.")
                mod["file"]          = new_filename
                mod["pending"]       = False
                mod.pop("legacy_active",  None)
                mod.pop("legacy_version", None)
                dirty = True
                if same_version_missing:
                    mods_redownloaded.append(name)
                else:
                    mods_updated.append(name)
            except Exception as e:
                print("  FAILED")
                mods_errors.append((name, str(e)))

        elif error and not is_not_available:
            mods_errors.append((name, error))

        else:
            # Not available for current version — try legacy fallback
            if legacy_ver:
                legacy_info, legacy_error = get_latest_version(slug, legacy_ver, loader)

                if legacy_error:
                    # Neither version works
                    if mod.get("file"):
                        delete_file(mod_dir, mod["file"])
                        mod["file"] = None
                        dirty = True
                    mod["pending"]       = True
                    mod["legacy_active"] = False
                    dirty = True
                    mods_pending.append(name)
                else:
                    files   = legacy_info.get("files", [])
                    primary = next((f for f in files if f.get("primary")), files[0] if files else None)

                    if not primary:
                        mods_errors.append((name, "no downloadable file in legacy API response"))
                        continue

                    new_filename = primary["filename"]

                    file_present = mod.get("file") and (Path(mod_dir) / mod["file"]).exists()
                    if file_present and mod.get("file") == new_filename and mod.get("legacy_active"):
                        mods_legacy.append((name, legacy_ver))
                        continue

                    old_filename = mod.get("file")
                    if old_filename and old_filename != new_filename:
                        delete_file(mod_dir, old_filename)

                    dest = Path(mod_dir) / new_filename
                    print(f"  Downloading {name}  ({new_filename}, legacy {legacy_ver}) ...", end="", flush=True)
                    try:
                        download_file(primary["url"], dest)
                        print("  OK")
                        mod["file"]          = new_filename
                        mod["pending"]       = False
                        mod["legacy_active"] = True
                        dirty = True
                        mods_legacy.append((name, legacy_ver))
                    except Exception as e:
                        print("  FAILED")
                        mods_errors.append((name, str(e)))
            else:
                # No legacy fallback configured
                if mod.get("file"):
                    delete_file(mod_dir, mod["file"])
                    mod["file"] = None
                    dirty = True
                mod["pending"] = True
                dirty = True
                mods_pending.append(name)

    if dirty:
        save_config(config)

    # ---- Resource packs ----
    if only_key in (None, "resourcepacks"):
        if only_key is None and config.get("resourcepacks"):
            print("\n-- Resource packs --")
        rp_updated, rp_ok, rp_outdated, rp_errors, rp_frozen, rp_unloaded, rp_redownloaded = upgrade_pack_category(
            config, "resourcepacks", "resourcepacks_dir", "minecraft", keep_outdated=True,
            only_slug=(target if only_key == "resourcepacks" else None)
        )
    else:
        rp_updated = rp_ok = rp_outdated = rp_errors = rp_frozen = rp_unloaded = rp_redownloaded = []

    # ---- Shader packs ----
    if only_key in (None, "shaderpacks"):
        if only_key is None and config.get("shaderpacks"):
            print("\n-- Shader packs --")
        sp_updated, sp_ok, sp_outdated, sp_errors, sp_frozen, sp_unloaded, sp_redownloaded = upgrade_pack_category(
            config, "shaderpacks", "shaderpacks_dir", shader_loader, keep_outdated=True,
            only_slug=(target if only_key == "shaderpacks" else None)
        )
    else:
        sp_updated = sp_ok = sp_outdated = sp_errors = sp_frozen = sp_unloaded = sp_redownloaded = []

    # ---- Datapacks (always kept in depot/Datapacks — no live game folder) ----
    if only_key in (None, "datapacks"):
        if only_key is None and config.get("datapacks"):
            print("\n-- Datapacks --")
        dp_updated, dp_ok, dp_outdated, dp_errors, dp_frozen, dp_unloaded, dp_redownloaded = upgrade_pack_category(
            config, "datapacks", "datapacks_dir", "datapack", keep_outdated=True,
            only_slug=(target if only_key == "datapacks" else None)
        )
    else:
        dp_updated = dp_ok = dp_outdated = dp_errors = dp_frozen = dp_unloaded = dp_redownloaded = []

    # ---- Summary ----
    print()
    if only_key in (None, "mods"):
        print("Mods:")
        if mods_updated:
            auto_updated = [n for n in mods_updated if not any(n == c[0] for c in mods_choose)]
            if auto_updated:
                print(f"  Updated ({len(auto_updated)}):     {', '.join(auto_updated)}")
        if mods_redownloaded:
            auto_redownloaded = [n for n in mods_redownloaded if not any(n == c[0] for c in mods_choose)]
            if auto_redownloaded:
                print(f"  🔁  Redownloaded ({len(auto_redownloaded)}) — file was missing, same version refetched (not a new release): {', '.join(auto_redownloaded)}")
        if mods_ok:
            auto_ok = [n for n in mods_ok if not any(n == c[0] for c in mods_choose)]
            if auto_ok:
                print(f"  Up to date ({len(auto_ok)}):  {', '.join(auto_ok)}")
        for name, detail in mods_choose:
            print(f"  ✎  {name}: {detail}")
        for name in mods_frozen:
            print(f"  ❄  {name}: FROZEN — skipped, kept current file (run 'unfreeze' to resume)")
        for name in mods_unloaded:
            print(f"  📦  {name}: UNLOADED — file kept in depot, not active (run 'load' to restore)")
        for name in mods_pending:
            print(f"  ⚠  {name}: PENDING — not available for {mc_version}, will retry")
        for name, lver in mods_legacy:
            print(f"  ⚠  {name}: LEGACY — running on {lver} (not available for {mc_version})")
        for name, msg in mods_errors:
            if not any(name == c[0] and "error" in c[1] for c in mods_choose):
                print(f"  ✗  {name}: {msg}")
        if not (mods_updated or mods_redownloaded or mods_ok or mods_choose or mods_frozen or mods_unloaded or mods_pending or mods_legacy or mods_errors):
            print("  (none)")

    _print_summary("Resource packs", rp_updated, rp_ok, rp_outdated, rp_errors, rp_frozen, rp_unloaded, mc_version, pending_label="OUTDATED — kept as-is", redownloaded=rp_redownloaded)
    _print_summary("Shader packs",   sp_updated, sp_ok, sp_outdated, sp_errors, sp_frozen, sp_unloaded, mc_version, pending_label="OUTDATED — kept as-is", redownloaded=sp_redownloaded)

    # Datapacks get their own summary block — file changes here don't affect
    # a running world until you manually copy the depot file over, so updates
    # are called out with 🔔 instead of blending into a quiet "Updated" line.
    # A missing depot file (e.g. moved into a world instead of copied) that
    # gets silently re-fetched is called out separately as 🔁 REDOWNLOADED —
    # it's the same version as before, not a new release, so it's kept out of
    # the 🔔 UPDATED bucket and out of the "go copy this into your world"
    # reminder below (you may well have already moved it there on purpose).
    if only_key in (None, "datapacks"):
        if dp_updated or dp_ok or dp_outdated or dp_errors or dp_frozen or dp_redownloaded:
            print(f"\nDatapacks (depot copy — copy into your world's datapacks folder manually):")
            if dp_updated:
                print(f"  {bold(yellow(f'🔔 UPDATED ({len(dp_updated)}) — copy these into your world(s):'))}")
                for name in dp_updated:
                    print(f"      🔔  {bold(name)}")
            if dp_redownloaded:
                print(f"  {cyan(f'🔁 REDOWNLOADED ({len(dp_redownloaded)}) — file was missing, same version refetched (not a new release):')}")
                for name in dp_redownloaded:
                    print(f"      🔁  {name}")
            if dp_ok:
                print(f"  Up to date ({len(dp_ok)}):  {', '.join(dp_ok)}")
            for name in dp_frozen:
                print(f"  ❄  {name}: FROZEN — skipped, kept current file (run 'unfreeze' to resume)")
            for name in dp_outdated:
                print(f"  ⚠  {name}: OUTDATED — not available for {mc_version}, kept as-is")
            for name, msg in dp_errors:
                print(f"  ✗  {name}: {msg}")

    # Overall frozen / unloaded reminders
    all_frozen = mods_frozen + rp_frozen + sp_frozen + dp_frozen
    if all_frozen:
        print(f"\n❄  Frozen ({len(all_frozen)}): {', '.join(all_frozen)}")

    all_unloaded = mods_unloaded + rp_unloaded + sp_unloaded
    if all_unloaded:
        print(f"\n📦  Unloaded ({len(all_unloaded)}): {', '.join(all_unloaded)} — kept in depot, run 'load <slug>' to restore")

    for category, manual_key in [
        ("Manual mods", "manual_mods"),
        ("Manual resource packs", "manual_resourcepacks"),
        ("Manual shader packs", "manual_shaderpacks"),
        ("Manual datapacks", "manual_datapacks"),
    ] if target is None else []:
        manual = config.get(manual_key, [])
        if manual:
            print(f"\n{category} (not managed): {', '.join(manual)}")

    if dp_updated:
        print(f"\n{bold(yellow('🔔 DATAPACK UPDATE REMINDER'))}: {len(dp_updated)} datapack(s) changed in the depot — "
              f"copy into your world's datapacks folder to actually use them: {', '.join(dp_updated)}")

    if dp_redownloaded:
        print(f"\n{cyan('🔁 Note')}: {len(dp_redownloaded)} datapack(s) had their depot file re-fetched because it went "
              f"missing — same version as before, not a new release, so no action needed unless you didn't move it "
              f"yourself: {', '.join(dp_redownloaded)}")

    print("\nDone.")


def cmd_upgrade_chooseall(config):
    """
    Like upgrade, but for every choose-flagged mod the version picker is always
    shown regardless of whether a new version has appeared — lets you switch to
    any available version (e.g. an alpha that now works) at will.
    """
    mc_version = config["mc_version"]
    loader     = config["loader"]
    mods_dir   = config["mods_dir"]

    choose_mods = [m for m in config.get("mods", []) if m.get("choose") and not m.get("frozen")]
    if not choose_mods:
        print("No choose-flagged (and unfrozen) mods found. Use 'choose <slug>' to flag a mod.")
        return

    print(f"Manual version selection for {len(choose_mods)} mod(s) — Minecraft {mc_version} ({loader})\n")
    dirty = False
    for mod in choose_mods:
        name = mod.get("name", mod["slug"])
        versions, error = get_all_versions(mod["slug"], mc_version, loader)
        if error or not versions:
            print(f"  ✗  {name}: {error or 'no versions found'}")
            continue
        result = _upgrade_mod_with_choose(config, mod, versions, mods_dir, force_prompt=True)
        dirty = True
        if result == "updated":
            installed = mod.get("file", "?")
            print(f"  ✎  {name}: {green('updated to ' + installed)}")
        elif result in ("ok", "skipped"):
            print(f"  ✎  {name}: {yellow('skipped (no change)')}")
        else:
            print(f"  ✗  {name}: {result[1]}")

    if dirty:
        save_config(config)
    print("\nDone.")


def _print_summary(label, updated, ok, pending_or_outdated, errors, frozen, unloaded, mc_version, pending_label, redownloaded=None):
    redownloaded = redownloaded or []
    if not (updated or ok or pending_or_outdated or errors or frozen or unloaded or redownloaded):
        return
    print(f"\n{label}:")
    if updated:
        print(f"  Updated ({len(updated)}):     {', '.join(updated)}")
    if redownloaded:
        print(f"  🔁  Redownloaded ({len(redownloaded)}) — file was missing, same version refetched (not a new release): {', '.join(redownloaded)}")
    if ok:
        print(f"  Up to date ({len(ok)}):  {', '.join(ok)}")
    for name in frozen:
        print(f"  ❄  {name}: FROZEN — skipped, kept current file (run 'unfreeze' to resume)")
    for name in unloaded:
        print(f"  📦  {name}: UNLOADED — file kept in depot, not active (run 'load' to restore)")
    for name in pending_or_outdated:
        print(f"  ⚠  {name}: {pending_label} for {mc_version}")
    for name, msg in errors:
        print(f"  ✗  {name}: {msg}")


def cmd_set_version(config, new_version):
    old = config["mc_version"]
    config["mc_version"] = new_version
    save_config(config)
    print(f"Version changed: {old}  →  {new_version}\n")
    cmd_upgrade(config)


# ---------------------------------------------------------------------------
# Presets (point 5): batch-add every slug listed in a Presets/Clients/<name>.json
# file. Only registers entries — same as running 'add'/'add_rp'/'add_sp'/'add_dp'
# once per slug — so 'upgrade' still has to be run afterwards to download them.
# ---------------------------------------------------------------------------

def get_presets_dir():
    return SCRIPT_DIR / "Presets" / "Clients"


def _available_presets():
    presets_dir = get_presets_dir()
    if not presets_dir.exists():
        return []
    return sorted(p.stem for p in presets_dir.glob("*.json"))


def _find_preset_file(name):
    presets_dir = get_presets_dir()
    if not presets_dir.exists():
        return None
    target = name.lower()
    for p in presets_dir.glob("*.json"):
        if p.stem.lower() == target:
            return p
    return None


def cmd_config(config, name):
    preset_file = _find_preset_file(name)
    if not preset_file:
        print(f"No preset named '{name}' found in {get_presets_dir()}.")
        available = _available_presets()
        if available:
            print(f"Available presets: {', '.join(available)}")
        else:
            print("No preset files exist there yet.")
        return

    try:
        with open(preset_file, encoding="utf-8") as f:
            preset = json.load(f)
    except Exception as e:
        print(f"Failed to read preset '{preset_file.name}': {e}")
        return

    print(f"Applying preset '{preset_file.stem}' ({preset_file.name})...\n")

    categories = [
        ("Mods",           "mods",          cmd_add),
        ("Resource packs", "resourcepacks", cmd_add_rp),
        ("Shader packs",   "shaderpacks",   cmd_add_sp),
        ("Datapacks",      "datapacks",     cmd_add_dp),
    ]

    total_added   = []
    total_skipped = []
    for label, key, add_fn in categories:
        slugs = preset.get(key, [])
        if not slugs:
            continue
        print(f"-- {label} --")
        added, skipped = add_fn(config, slugs, prompt_upgrade=False, announce=False)
        total_added   += added
        total_skipped += skipped
        print()

    print("Add anything else by hand before downloading? (space-separated slugs, Enter to skip each)")
    for label, key, add_fn in categories:
        extra = input(f"  Extra {label.lower()}: ").strip()
        if not extra:
            continue
        added, skipped = add_fn(config, extra.split(), prompt_upgrade=False, announce=False)
        total_added   += added
        total_skipped += skipped
    print()

    print("=== Preset summary ===")
    _print_add_summary("entrie(s)", total_added, total_skipped)

    if total_added:
        _maybe_prompt_upgrade(config)


# ---------------------------------------------------------------------------
# Mod commands
# ---------------------------------------------------------------------------

def _add_slugs(config, category_key, slugs, extra_fields=None):
    """
    Register each slug in `slugs` under config[category_key], skipping any
    that are already present (within this call or already in the config).
    Returns (added, skipped): added is a list of (slug, name) tuples,
    skipped is a list of slugs that were already registered.
    """
    extra_fields = extra_fields or {}
    existing = {e["slug"] for e in config.get(category_key, [])}
    added   = []
    skipped = []
    for slug in slugs:
        if slug in existing:
            skipped.append(slug)
            continue
        print(f"Looking up '{slug}' on Modrinth...", end="", flush=True)
        name = get_project_name(slug)
        print(f"  found: {name}")
        entry = {"slug": slug, "name": name, "file": None, "pending": True}
        entry.update(extra_fields)
        config.setdefault(category_key, []).append(entry)
        existing.add(slug)
        added.append((slug, name))
    if added:
        save_config(config)
    return added, skipped


def _print_add_summary(label, added, skipped):
    if added:
        print(f"\nAdded {len(added)} {label}: {', '.join(n for _, n in added)}.")
        print("Run 'upgrade' to download them.")
    if skipped:
        print(f"Already registered, skipped {len(skipped)}: {', '.join(skipped)}.")
    if not added and not skipped:
        print("Nothing to add.")


def _maybe_prompt_upgrade(config):
    resp = input("Upgrade now? [Y/n]: ").strip().lower()
    if resp in ("", "y", "yes"):
        cmd_upgrade(config)


def cmd_add(config, slugs, prompt_upgrade=True, announce=True):
    added, skipped = _add_slugs(config, "mods", slugs)
    if announce:
        _print_add_summary("mod(s)", added, skipped)
    if added and prompt_upgrade:
        _maybe_prompt_upgrade(config)
    return added, skipped


def cmd_remove(config, slug):
    mod = next((m for m in config.get("mods", []) if m["slug"] == slug), None)
    if not mod:
        print(f"No managed mod with slug '{slug}' found.")
        return
    name = mod.get("name", slug)
    if mod.get("file"):
        if delete_file(entry_dir(config, mod, "mods_dir"), mod["file"]):
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
    name = mod.get("name", slug)
    mod["legacy_version"] = legacy_version
    save_config(config)
    print(f"Legacy fallback set for '{name}': will use {legacy_version} if {config['mc_version']} is unavailable.")
    print("Running upgrade to apply...")
    cmd_upgrade(config)


def cmd_legacy_off(config, slug):
    mod = next((m for m in config.get("mods", []) if m["slug"] == slug), None)
    if not mod:
        print(f"No managed mod with slug '{slug}' found.")
        return
    name = mod.get("name", slug)
    if mod.get("file") and mod.get("legacy_active"):
        if delete_file(entry_dir(config, mod, "mods_dir"), mod["file"]):
            print(f"Deleted legacy file: {mod['file']}")
        mod["file"] = None
    mod["pending"]       = True
    mod["legacy_active"] = False
    mod.pop("legacy_version", None)
    save_config(config)
    print(f"Legacy mode cleared for '{name}'. Marked as pending — run 'upgrade' to retry current version.")


# ---------------------------------------------------------------------------
# Choose / unchoose — manual version selection on upgrade
# ---------------------------------------------------------------------------

def cmd_choose(config, slug):
    mod = next((m for m in config.get("mods", []) if m["slug"] == slug), None)
    if not mod:
        print(f"No managed mod with slug '{slug}' found.")
        return
    mod["choose"] = True
    save_config(config)
    print(f"Manual version selection enabled for '{mod.get('name', slug)}'.")
    print("On the next 'upgrade', you will be prompted whenever a new version is available.")


def cmd_unchoose(config, slug):
    mod = next((m for m in config.get("mods", []) if m["slug"] == slug), None)
    if not mod:
        print(f"No managed mod with slug '{slug}' found.")
        return
    mod.pop("choose", None)
    mod.pop("chosen_version_id", None)
    mod.pop("skipped_version_id", None)
    save_config(config)
    print(f"Manual version selection disabled for '{mod.get('name', slug)}'. "
          f"It will auto-update normally from now on.")


def cmd_unchoose_all(config):
    count = 0
    for mod in config.get("mods", []):
        if mod.get("choose"):
            mod.pop("choose", None)
            mod.pop("chosen_version_id", None)
            mod.pop("skipped_version_id", None)
            count += 1
    save_config(config)
    print(f"Cleared manual version selection from {count} mod{'s' if count != 1 else ''}. "
          f"All mods will auto-update normally from now on.")


def cmd_upgrade_masterchoose(config):
    """
    Shows the version picker for every mod (not just choose-flagged ones).
    If the user picks a version that isn't already installed, 'choose' is
    automatically enabled on that mod. Skipping or picking the green
    (already installed) version leaves the choose flag untouched.
    """
    mc_version = config["mc_version"]
    loader     = config["loader"]
    mods       = [m for m in config.get("mods", []) if not m.get("frozen")]

    if not mods:
        print("No (unfrozen) mods found.")
        return

    print(f"Master version selection — Minecraft {mc_version} ({loader})")
    print("Pick a version for each mod, or skip to leave it unchanged.\n")

    dirty = False
    for mod in mods:
        name     = mod.get("name", mod["slug"])
        mods_dir = entry_dir(config, mod, "mods_dir")
        versions, error = get_all_versions(mod["slug"], mc_version, loader)
        if error or not versions:
            print(f"  ✗  {name}: {error or 'no versions found'}")
            continue

        current_id = mod.get("chosen_version_id")
        chosen = _prompt_version_choice(name, versions, current_version_id=current_id, current_filename=mod.get("file"))

        if chosen is None:
            print(f"  {yellow('→ skipped')}")
            continue

        picked_id = chosen["id"]
        if picked_id == current_id:
            print(f"  {green('→ already installed, no change')}")
            continue

        # User picked a different version — download it and auto-enable choose.
        files   = chosen.get("files", [])
        primary = next((f for f in files if f.get("primary")), files[0] if files else None)
        if not primary:
            print(f"  ✗  {name}: no downloadable file in chosen version")
            continue

        new_filename = primary["filename"]
        old_filename = mod.get("file")
        if old_filename and old_filename != new_filename:
            delete_file(mods_dir, old_filename)

        dest = Path(mods_dir) / new_filename
        print(f"  Downloading {name}  ({new_filename}) ...", end="", flush=True)
        try:
            download_file(primary["url"], dest)
            print("  OK")
            mod["file"]              = new_filename
            mod["pending"]           = False
            mod["chosen_version_id"] = picked_id
            mod.pop("skipped_version_id", None)
            mod.pop("legacy_active", None)
            mod.pop("legacy_version", None)
            if not mod.get("choose"):
                mod["choose"] = True
                print(f"  {cyan('→ choose enabled automatically')}")
            dirty = True
        except Exception as e:
            print("  FAILED")
            print(f"  ✗  {name}: {e}")

    if dirty:
        save_config(config)
    print("\nDone.")


def _prompt_version_choice(name, versions, current_version_id=None, current_filename=None):
    """
    Print a numbered menu of versions and return the chosen version dict,
    or None if the user skips (-1 or empty input).
    The currently installed version is highlighted in green, matched by
    version ID (for choose-flagged mods) or by filename (for all others).
    """
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


def _upgrade_mod_with_choose(config, mod, versions, mods_dir, force_prompt=False):
    """
    Handle upgrade for a single choose-flagged mod.
    versions: full list from get_all_versions (newest first).
    force_prompt: if True (upgrade_chooseall), always show the menu.
    Returns one of: "updated", "redownloaded", "ok", "skipped", ("error", msg).
    "redownloaded" means the already-chosen version was still current but its
    file had gone missing, so it was silently re-fetched — not a new choice.
    """
    name     = mod.get("name", mod["slug"])
    mods_dir = entry_dir(config, mod, "mods_dir")
    newest    = versions[0]
    newest_id = newest["id"]
    is_missing_refetch = False

    if not force_prompt:
        file_present = mod.get("file") and (Path(mods_dir) / mod["file"]).exists()
        if newest_id == mod.get("chosen_version_id"):
            if file_present:
                return "ok"
            # The chosen version is still current, but the file itself is gone
            # (e.g. moved out by hand) — silently re-fetch it instead of
            # re-prompting for a choice that's already been made.
            chosen = newest
            is_missing_refetch = True
        elif newest_id == mod.get("skipped_version_id"):
            return "skipped"
        else:
            chosen = _prompt_version_choice(name, versions, current_version_id=mod.get("chosen_version_id"), current_filename=mod.get("file"))
    else:
        chosen = _prompt_version_choice(name, versions, current_version_id=mod.get("chosen_version_id"), current_filename=mod.get("file"))

    if chosen is None:
        mod["skipped_version_id"] = newest_id
        return "skipped"

    files   = chosen.get("files", [])
    primary = next((f for f in files if f.get("primary")), files[0] if files else None)
    if not primary:
        return ("error", "no downloadable file in chosen version")

    new_filename = primary["filename"]
    old_filename = mod.get("file")
    if old_filename and old_filename != new_filename:
        delete_file(mods_dir, old_filename)

    dest = Path(mods_dir) / new_filename
    print(f"  Downloading {name}  ({new_filename}) ...", end="", flush=True)
    try:
        download_file(primary["url"], dest)
        print("  OK")
        mod["file"]              = new_filename
        mod["pending"]           = False
        mod["chosen_version_id"] = chosen["id"]
        mod.pop("skipped_version_id", None)
        mod.pop("legacy_active", None)
        mod.pop("legacy_version", None)
        return "redownloaded" if is_missing_refetch else "updated"
    except Exception as e:
        print("  FAILED")
        return ("error", str(e))


# ---------------------------------------------------------------------------
# Resource pack commands
# ---------------------------------------------------------------------------

def cmd_add_rp(config, slugs, prompt_upgrade=True, announce=True):
    added, skipped = _add_slugs(config, "resourcepacks", slugs, extra_fields={"outdated": False})
    if announce:
        _print_add_summary("resource pack(s)", added, skipped)
    if added and prompt_upgrade:
        _maybe_prompt_upgrade(config)
    return added, skipped


def cmd_remove_rp(config, slug):
    pack = next((p for p in config.get("resourcepacks", []) if p["slug"] == slug), None)
    if not pack:
        print(f"No managed resource pack with slug '{slug}' found.")
        return
    name = pack.get("name", slug)
    if pack.get("file"):
        if delete_file(entry_dir(config, pack, "resourcepacks_dir"), pack["file"]):
            print(f"Deleted file: {pack['file']}")
    config["resourcepacks"] = [p for p in config["resourcepacks"] if p["slug"] != slug]
    save_config(config)
    print(f"Removed resource pack '{name}' from the list.")


def cmd_add_manual_rp(config, filename):
    config.setdefault("manual_resourcepacks", [])
    if filename in config["manual_resourcepacks"]:
        print(f"'{filename}' is already registered as a manual resource pack.")
        return
    rp_dir = config.get("resourcepacks_dir", "")
    if rp_dir and not (Path(rp_dir) / filename).exists():
        print(f"Note: '{filename}' not found in resourcepacks directory yet.")
    config["manual_resourcepacks"].append(filename)
    save_config(config)
    print(f"Registered manual resource pack: {filename}")


def cmd_remove_manual_rp(config, filename):
    if filename not in config.get("manual_resourcepacks", []):
        print(f"'{filename}' is not registered as a manual resource pack.")
        return
    config["manual_resourcepacks"].remove(filename)
    save_config(config)
    print(f"Unregistered manual resource pack: {filename} (file not deleted)")


# ---------------------------------------------------------------------------
# Shader pack commands
# ---------------------------------------------------------------------------

def cmd_add_sp(config, slugs, prompt_upgrade=True, announce=True):
    added, skipped = _add_slugs(config, "shaderpacks", slugs, extra_fields={"outdated": False})
    if announce:
        _print_add_summary("shader pack(s)", added, skipped)
    if added and prompt_upgrade:
        _maybe_prompt_upgrade(config)
    return added, skipped


def cmd_remove_sp(config, slug):
    pack = next((p for p in config.get("shaderpacks", []) if p["slug"] == slug), None)
    if not pack:
        print(f"No managed shader pack with slug '{slug}' found.")
        return
    name   = pack.get("name", slug)
    sp_dir = entry_dir(config, pack, "shaderpacks_dir")
    if pack.get("file"):
        if delete_file(sp_dir, pack["file"]):
            print(f"Deleted file: {pack['file']}")
        # Shader .txt config goes to quarantine, never deleted (see point 3).
        cfg = Path(sp_dir) / (pack["file"] + ".txt")
        if cfg.exists():
            dest = quarantine_file(get_quarantine_dir(config), cfg)
            if dest:
                print(f"Shader config quarantined: {cfg.name}  →  {dest}")
    config["shaderpacks"] = [p for p in config["shaderpacks"] if p["slug"] != slug]
    save_config(config)
    print(f"Removed shader pack '{name}' from the list.")


def cmd_add_manual_sp(config, filename):
    config.setdefault("manual_shaderpacks", [])
    if filename in config["manual_shaderpacks"]:
        print(f"'{filename}' is already registered as a manual shader pack.")
        return
    sp_dir = config.get("shaderpacks_dir", "")
    if sp_dir and not (Path(sp_dir) / filename).exists():
        print(f"Note: '{filename}' not found in shaderpacks directory yet.")
    config["manual_shaderpacks"].append(filename)
    save_config(config)
    print(f"Registered manual shader pack: {filename}")


def cmd_remove_manual_sp(config, filename):
    if filename not in config.get("manual_shaderpacks", []):
        print(f"'{filename}' is not registered as a manual shader pack.")
        return
    config["manual_shaderpacks"].remove(filename)
    save_config(config)
    print(f"Unregistered manual shader pack: {filename} (file not deleted)")


# ---------------------------------------------------------------------------
# Datapack commands — Modrinth-managed like everything else, but a datapack
# belongs to a world, not an install, so its file is kept in the depot's
# Datapacks subfolder instead of any live game folder. You copy it into a
# world yourself; the upgrade summary calls out changes loudly (🔔) so that's
# easy to notice.
# ---------------------------------------------------------------------------

def cmd_add_dp(config, slugs, prompt_upgrade=True, announce=True):
    added, skipped = _add_slugs(config, "datapacks", slugs, extra_fields={"outdated": False})
    if announce:
        _print_add_summary("datapack(s)", added, skipped)
        if added:
            print("Datapacks are per-world — 'upgrade' only stages the file in the depot; copy")
            print("it into your world's datapacks folder yourself.")
    if added and prompt_upgrade:
        _maybe_prompt_upgrade(config)
    return added, skipped


def cmd_remove_dp(config, slug):
    pack = next((p for p in config.get("datapacks", []) if p["slug"] == slug), None)
    if not pack:
        print(f"No managed datapack with slug '{slug}' found.")
        return
    name = pack.get("name", slug)
    if pack.get("file"):
        if delete_file(entry_dir(config, pack, "datapacks_dir"), pack["file"]):
            print(f"Deleted depot file: {pack['file']}")
    config["datapacks"] = [p for p in config["datapacks"] if p["slug"] != slug]
    save_config(config)
    print(f"Removed datapack '{name}' from the list.")


def cmd_add_manual_dp(config, filename):
    config.setdefault("manual_datapacks", [])
    if filename in config["manual_datapacks"]:
        print(f"'{filename}' is already registered as a manual datapack.")
        return
    dp_dir = get_datapack_depot_dir(config)
    if dp_dir and not (Path(dp_dir) / filename).exists():
        print(f"Note: '{filename}' not found in the datapack depot folder yet.")
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


# ---------------------------------------------------------------------------
# Link commands (point 4): attach a manually downloaded file to a managed entry
# ---------------------------------------------------------------------------

def _cmd_link(config, category_key, dir_key, label, slug, filename):
    entry = next((e for e in config.get(category_key, []) if e["slug"] == slug), None)
    if not entry:
        print(f"No managed {label} with slug '{slug}' found. Add it first.")
        return
    d = get_datapack_depot_dir(config) if dir_key == "datapacks_dir" else config.get(dir_key, "")
    if d and not (Path(d) / filename).exists():
        print(f"Note: '{filename}' not found in the {label} directory yet — linking anyway.")
    entry["file"]     = filename
    entry["pending"]  = False
    entry.pop("unloaded", None)
    if "outdated" in entry:
        entry["outdated"] = False
    save_config(config)
    print(f"Linked '{filename}' to {label} '{entry.get('name', slug)}'.")
    print("You can now 'freeze' it to keep this file across upgrades.")


def cmd_link(config, slug, filename):
    _cmd_link(config, "mods", "mods_dir", "mod", slug, filename)


def cmd_link_rp(config, slug, filename):
    _cmd_link(config, "resourcepacks", "resourcepacks_dir", "resource pack", slug, filename)


def cmd_link_sp(config, slug, filename):
    _cmd_link(config, "shaderpacks", "shaderpacks_dir", "shader pack", slug, filename)


def cmd_link_dp(config, slug, filename):
    _cmd_link(config, "datapacks", "datapacks_dir", "datapack", slug, filename)


# ---------------------------------------------------------------------------
# Freeze / unfreeze (point 1): keep current file, skip updating
# ---------------------------------------------------------------------------

_FREEZE_CATEGORIES = ("mods", "resourcepacks", "shaderpacks", "datapacks")


def _find_entry(config, slug):
    for key in _FREEZE_CATEGORIES:
        for e in config.get(key, []):
            if e["slug"] == slug:
                return e, key
    return None, None


def cmd_freeze(config, target):
    if target == "all":
        names = []
        for key in _FREEZE_CATEGORIES:
            for e in config.get(key, []):
                e["frozen"] = True
                names.append(e.get("name", e["slug"]))
        save_config(config)
        print(f"Froze {len(names)} entr{'y' if len(names) == 1 else 'ies'}. "
              f"They will be skipped during upgrade until unfrozen.")
        return

    entry, _ = _find_entry(config, target)
    if not entry:
        print(f"No managed mod/pack with slug '{target}' found.")
        return
    entry["frozen"] = True
    save_config(config)
    print(f"Froze '{entry.get('name', target)}'. It will be skipped during upgrade until unfrozen.")


def cmd_unfreeze(config, target):
    if target == "all":
        count = 0
        for key in _FREEZE_CATEGORIES:
            for e in config.get(key, []):
                if e.pop("frozen", None):
                    count += 1
        save_config(config)
        print(f"Unfroze {count} entr{'y' if count == 1 else 'ies'}. They will update on the next upgrade.")
        return

    entry, _ = _find_entry(config, target)
    if not entry:
        print(f"No managed mod/pack with slug '{target}' found.")
        return
    if not entry.pop("frozen", None):
        print(f"'{entry.get('name', target)}' was not frozen.")
        return
    save_config(config)
    print(f"Unfroze '{entry.get('name', target)}'. It will update on the next upgrade.")


# ---------------------------------------------------------------------------
# Unload / load: move a managed file into/out of the depot, without dropping
# it from the config. Unloaded entries are still frozen/upgraded/chosen
# normally — 'upgrade' just operates on the depot copy instead of the active
# folder. 'load' only moves the file back; it never checks for updates.
# ---------------------------------------------------------------------------

def _unload_one(config, entry, key):
    dir_key    = f"{key}_dir"
    name       = entry.get("name", entry.get("slug"))
    is_shader  = (key == "shaderpacks")
    active_dir = config.get(dir_key, "")
    depot_dir  = get_shelf_dir(config)

    if entry.get("file"):
        dest, err = move_managed_file(entry["file"], active_dir, depot_dir)
        if err == "conflict":
            print(f"  ✗  {name}: a file named '{entry['file']}' already exists in the depot — not unloaded.")
            return False
        elif err == "missing":
            print(f"  ⚠  {name}: file '{entry['file']}' not found in {active_dir}; flagging unloaded anyway.")
        else:
            print(f"  📦  {name}: moved to depot ({entry['file']})")

        if is_shader:
            cfg_name = entry["file"] + ".txt"
            cdest, cerr = move_managed_file(cfg_name, active_dir, depot_dir)
            if not cerr:
                print(f"      shader config moved too ({cfg_name})")

    entry["unloaded"] = True
    return True


def _load_one(config, entry, key):
    dir_key    = f"{key}_dir"
    name       = entry.get("name", entry.get("slug"))
    is_shader  = (key == "shaderpacks")
    active_dir = config.get(dir_key, "")
    depot_dir  = get_shelf_dir(config)

    if entry.get("file"):
        dest, err = move_managed_file(entry["file"], depot_dir, active_dir)
        if err == "conflict":
            print(f"  ✗  {name}: a file named '{entry['file']}' already exists in {active_dir} — not loaded.")
            return False
        elif err == "missing":
            print(f"  ⚠  {name}: file '{entry['file']}' not found in the depot; clearing unloaded flag anyway.")
        else:
            print(f"  ✔  {name}: moved back from depot ({entry['file']})")

        if is_shader:
            cfg_name = entry["file"] + ".txt"
            cdest, cerr = move_managed_file(cfg_name, depot_dir, active_dir)
            if not cerr:
                print(f"      shader config moved back too ({cfg_name})")

    entry.pop("unloaded", None)
    return True


def cmd_unload(config, target):
    if target == "all":
        count = 0
        for key in _FREEZE_CATEGORIES:
            if key == "datapacks":
                continue  # already live in the depot — unload doesn't apply
            for e in config.get(key, []):
                if e.get("unloaded"):
                    continue
                if _unload_one(config, e, key):
                    count += 1
        save_config(config)
        print(f"\nUnloaded {count} entr{'y' if count == 1 else 'ies'} into the depot.")
        return

    entry, key = _find_entry(config, target)
    if not entry:
        print(f"No managed mod/pack with slug '{target}' found.")
        return
    if key == "datapacks":
        print(f"'{entry.get('name', target)}' is a datapack — it already lives in the depot, "
              f"so 'unload' doesn't apply. Use 'freeze' or 'clear' instead.")
        return
    if entry.get("unloaded"):
        print(f"'{entry.get('name', target)}' is already unloaded.")
        return
    if _unload_one(config, entry, key):
        save_config(config)
        print(f"Unloaded '{entry.get('name', target)}'. It stays frozen/upgraded/chosen normally; "
              f"run 'load' to bring it back.")


def cmd_load(config, target):
    if target == "all":
        count = 0
        for key in _FREEZE_CATEGORIES:
            if key == "datapacks":
                continue  # already live in the depot — load doesn't apply
            for e in config.get(key, []):
                if not e.get("unloaded"):
                    continue
                if _load_one(config, e, key):
                    count += 1
        save_config(config)
        print(f"\nLoaded {count} entr{'y' if count == 1 else 'ies'} back from the depot. No update check performed.")
        return

    entry, key = _find_entry(config, target)
    if not entry:
        print(f"No managed mod/pack with slug '{target}' found.")
        return
    if key == "datapacks":
        print(f"'{entry.get('name', target)}' is a datapack — it already lives in the depot, "
              f"so 'load' doesn't apply.")
        return
    if not entry.get("unloaded"):
        print(f"'{entry.get('name', target)}' is not unloaded.")
        return
    if _load_one(config, entry, key):
        save_config(config)
        print(f"Loaded '{entry.get('name', target)}' back from the depot. No update check performed.")


# ---------------------------------------------------------------------------
# Shelf / unshelf: whole-profile flag for a temporarily unused install.
# 'upgrade' (and set-version/upgrade_chooseall/upgrade_masterchoose) refuse
# outright while shelved. Every other command warns and requires explicit
# confirmation before proceeding (see the gate in main()).
# ---------------------------------------------------------------------------

def cmd_shelf(config):
    if config.get("shelved"):
        print("This profile is already shelved.")
        return

    still_present = []
    for key in _FREEZE_CATEGORIES:
        for e in config.get(key, []):
            if e.get("file"):
                still_present.append(e.get("name", e["slug"]))
    if still_present:
        print(f"Note: {len(still_present)} entr{'y' if len(still_present) == 1 else 'ies'} still have a file present: "
              f"{', '.join(still_present)}")
        print("Consider running 'clear all' first if you want a fully empty profile before shelving.\n")

    config["shelved"] = True
    save_config(config)
    print("Profile SHELVED.")
    print("  - 'upgrade' (and set-version / upgrade_chooseall / upgrade_masterchoose) will be blocked with an error.")
    print("  - Every other command will ask for confirmation before proceeding.")
    print("Run 'unshelf' to resume normal operation.")


def cmd_unshelf(config):
    if not config.get("shelved"):
        print("This profile is not shelved.")
        return
    config.pop("shelved", None)
    save_config(config)
    print("Profile UNSHELVED. Normal operation resumed.")


# ---------------------------------------------------------------------------
# Clear (point 2): delete mod files, quarantine resource/shader pack files
# ---------------------------------------------------------------------------

def _clear_mod(config, mod):
    if mod.get("file"):
        if delete_file(entry_dir(config, mod, "mods_dir"), mod["file"]):
            print(f"  Deleted mod file: {mod['file']}")
    mod["file"]    = None
    mod["pending"] = True
    mod.pop("unloaded", None)


def _clear_pack(config, pack, dir_key, is_shader):
    packs_dir = entry_dir(config, pack, dir_key)
    if pack.get("file"):
        qdir = get_quarantine_dir(config)
        src = Path(packs_dir) / pack["file"]
        if src.exists():
            dest = quarantine_file(qdir, src)
            if dest:
                print(f"  Quarantined: {pack['file']}  →  {dest}")
        if is_shader:
            cfg = Path(packs_dir) / (pack["file"] + ".txt")
            if cfg.exists():
                cdest = quarantine_file(qdir, cfg)
                if cdest:
                    print(f"  Quarantined shader config: {cfg.name}  →  {cdest}")
    pack["file"]     = None
    pack["pending"]  = True
    pack["outdated"] = False
    pack.pop("unloaded", None)


def cmd_clear(config, target):
    do_mods = target in ("all", "mods")
    do_rp   = target in ("all", "rp", "resourcepacks")
    do_sp   = target in ("all", "sp", "shaderpacks")
    do_dp   = target in ("all", "dp", "datapacks")

    if do_mods or do_rp or do_sp or do_dp:
        if do_mods:
            print("Mods (deleting files):")
            if not config.get("mods"):
                print("  (none)")
            for mod in config.get("mods", []):
                _clear_mod(config, mod)
        if do_rp:
            print("Resource packs (quarantining):")
            if not config.get("resourcepacks"):
                print("  (none)")
            for pack in config.get("resourcepacks", []):
                _clear_pack(config, pack, "resourcepacks_dir", False)
        if do_sp:
            print("Shader packs (quarantining):")
            if not config.get("shaderpacks"):
                print("  (none)")
            for pack in config.get("shaderpacks", []):
                _clear_pack(config, pack, "shaderpacks_dir", True)
        if do_dp:
            print("Datapacks (quarantining depot copy):")
            if not config.get("datapacks"):
                print("  (none)")
            for pack in config.get("datapacks", []):
                _clear_pack(config, pack, "datapacks_dir", False)
        save_config(config)
        print("\nCleared. Run 'upgrade' to re-download non-frozen entries.")
        return

    # Single entry by slug.
    entry, key = _find_entry(config, target)
    if not entry:
        print(f"No managed mod/pack with slug '{target}' found.")
        return
    print(f"Clearing '{entry.get('name', target)}':")
    if key == "mods":
        _clear_mod(config, entry)
    elif key == "resourcepacks":
        _clear_pack(config, entry, "resourcepacks_dir", False)
    elif key == "shaderpacks":
        _clear_pack(config, entry, "shaderpacks_dir", True)
    else:
        _clear_pack(config, entry, "datapacks_dir", False)
    save_config(config)
    if entry.get("frozen"):
        print("Note: this entry is frozen, so 'upgrade' will NOT re-download it. Unfreeze first.")
    print("Done.")


# ---------------------------------------------------------------------------
# List command
# ---------------------------------------------------------------------------

def _status_of(entry, is_pack):
    tags = []
    if entry.get("frozen"):
        tags.append("FROZEN")
    if entry.get("unloaded"):
        tags.append("UNLOADED")
    if not is_pack and entry.get("choose"):
        tags.append("CHOOSE")
    if is_pack and entry.get("outdated"):
        tags.append("OUTDATED")
    if not is_pack and entry.get("legacy_active"):
        tags.append("LEGACY")
    if entry.get("pending"):
        tags.append("PENDING")
    if not tags:
        tags.append("OK")
    return "+".join(tags)


def cmd_list(config):
    if config.get("shelved"):
        print(bold(yellow("*** THIS PROFILE IS SHELVED — 'upgrade' is blocked, other commands require confirmation. Run 'unshelf' to resume. ***")))
        print()
    print(f"Minecraft {config['mc_version']}  |  loader: {config['loader']}  |  shader loader: {config.get('shader_loader', 'iris')}")
    print()

    # Mods
    mods = config.get("mods", [])
    print("=== Mods ===")
    if mods:
        for mod in mods:
            status   = _status_of(mod, is_pack=False)
            fileinfo = mod.get("file") or "(no file)"
            name     = mod.get("name", mod["slug"])
            legacy   = f"  [legacy fallback: {mod['legacy_version']}]" if mod.get("legacy_version") else ""
            print(f"  [{status:8s}]  {name} ({mod['slug']})  —  {fileinfo}{legacy}")
    else:
        print("  (none)")

    manual_mods = config.get("manual_mods", [])
    if manual_mods:
        print("\n  Manual mods:")
        for f in manual_mods:
            print(f"    {f}")

    # Resource packs
    print("\n=== Resource Packs ===")
    rps = config.get("resourcepacks", [])
    if rps:
        for pack in rps:
            status   = _status_of(pack, is_pack=True)
            fileinfo = pack.get("file") or "(no file)"
            name     = pack.get("name", pack["slug"])
            print(f"  [{status:8s}]  {name} ({pack['slug']})  —  {fileinfo}")
    else:
        print("  (none)")

    manual_rps = config.get("manual_resourcepacks", [])
    if manual_rps:
        print("\n  Manual resource packs:")
        for f in manual_rps:
            print(f"    {f}")

    # Shader packs
    print("\n=== Shader Packs ===")
    sps = config.get("shaderpacks", [])
    if sps:
        for pack in sps:
            status   = _status_of(pack, is_pack=True)
            fileinfo = pack.get("file") or "(no file)"
            name     = pack.get("name", pack["slug"])
            print(f"  [{status:8s}]  {name} ({pack['slug']})  —  {fileinfo}")
    else:
        print("  (none)")

    manual_sps = config.get("manual_shaderpacks", [])
    if manual_sps:
        print("\n  Manual shader packs:")
        for f in manual_sps:
            print(f"    {f}")

    # Datapacks — depot copies only; there's no live game folder for these.
    print("\n=== Datapacks (depot copies — copy into your world's datapacks folder) ===")
    dps = config.get("datapacks", [])
    if dps:
        for pack in dps:
            status   = _status_of(pack, is_pack=True)
            fileinfo = pack.get("file") or "(no file)"
            name     = pack.get("name", pack["slug"])
            print(f"  [{status:8s}]  {name} ({pack['slug']})  —  {fileinfo}")
    else:
        print("  (none)")

    manual_dps = config.get("manual_datapacks", [])
    if manual_dps:
        print("\n  Manual datapacks:")
        for f in manual_dps:
            print(f"    {f}")

    # Frozen / unloaded overview
    frozen = []
    unloaded = []
    for key in _FREEZE_CATEGORIES:
        frozen   += [e.get("name", e["slug"]) for e in config.get(key, []) if e.get("frozen")]
        unloaded += [e.get("name", e["slug"]) for e in config.get(key, []) if e.get("unloaded")]
    if frozen:
        print(f"\n❄  Frozen ({len(frozen)}): {', '.join(frozen)}")
    if unloaded:
        print(f"\n📦  Unloaded ({len(unloaded)}): {', '.join(unloaded)}")

    print(f"\nMods dir:          {config.get('mods_dir', '(not set)')}")
    print(f"Resourcepacks dir: {config.get('resourcepacks_dir', '(not set)')}")
    print(f"Shaderpacks dir:   {config.get('shaderpacks_dir', '(not set)')}")
    print(f"Quarantine dir:    {config.get('quarantine_dir', '(not set)')}")
    print(f"Depot dir:         {config.get('depot_dir', '(not set)')}")
    if config.get("depot_dir"):
        print(f"  Shelf (unloaded): {get_shelf_dir(config)}")
        print(f"  Datapacks:        {get_datapack_depot_dir(config)}")


def print_help():
    print(f"""
Mcmods.py — Minecraft mod/resourcepack/shaderpack manager  (version {SCRIPT_VERSION}, {SCRIPT_VERSION_DATE})

Every command below is run as:  python Mcmods.py <profile> <command> [args...]
<profile> selects Mcmods_<profile>.json next to this script (e.g. 'main', 'side').
A profile is created the first time you run its 'init', and deleted simply by
deleting its Mcmods_<profile>.json file — there's no dedicated delete command.

Commands:
  init                            Interactive setup — creates the config file
  upgrade [slug]                  Download/update mods, resource packs, and shader packs.
                                  With a slug, only that one mod/pack is checked/upgraded
                                  (still respects its FROZEN/UNLOADED/CHOOSE flags).
  set-version <version>           Change MC version and immediately run upgrade
  config <preset>                 Batch-add every slug from Presets/Clients/<preset>.json
                                  (matched case-insensitively). Then asks for any extra
                                  mods/resourcepacks/shaderpacks/datapacks to add by hand,
                                  and offers "Upgrade now? [Y/n]" (Enter = yes) once
                                  everything's been registered.
  list                            Show all entries by category (incl. FROZEN status)

  --- Mods ---
  add <slug> [slug2 ...]          Add one or more mods by Modrinth slug. After adding,
                                  you're asked "Upgrade now? [Y/n]" (Enter = yes).
  remove <slug>                   Remove a mod (also deletes the JAR)
  add-manual <filename>           Register a manual JAR (never touched by upgrade)
  remove-manual <filename>        Unregister a manual mod (file is NOT deleted)
  legacy_on <slug> <version>      Set a legacy fallback version for a mod
  legacy_off <slug>               Clear legacy mode, delete legacy file, mark pending
  link <slug> <filename>          Attach a manually downloaded file to a managed mod

  --- Resource packs ---
  add_rp <slug> [slug2 ...]       Add one or more resource packs by Modrinth slug
  remove_rp <slug>                Remove a resource pack (also deletes the file)
  add_manual_rp <filename>        Register a manual resource pack
  remove_manual_rp <filename>     Unregister a manual resource pack (file NOT deleted)
  link_rp <slug> <filename>       Attach a manually downloaded file to a managed RP

  --- Shader packs ---
  add_sp <slug> [slug2 ...]       Add one or more shader packs by Modrinth slug
  remove_sp <slug>                Remove a shader pack (file deleted, .txt config quarantined)
  add_manual_sp <filename>        Register a manual shader pack
  remove_manual_sp <filename>     Unregister a manual shader pack (file NOT deleted)
  link_sp <slug> <filename>       Attach a manually downloaded file to a managed SP

  --- Datapacks ---
  add_dp <slug> [slug2 ...]       Add one or more datapacks by Modrinth slug (kept in
                                  depot/Datapacks — datapacks are per-world, so there's
                                  no live folder for them)
  remove_dp <slug>                Remove a datapack (also deletes its depot file)
  add_manual_dp <filename>        Register a manual datapack (never touched by upgrade)
  remove_manual_dp <filename>     Unregister a manual datapack (file is NOT deleted)
  link_dp <slug> <filename>       Attach a manually downloaded file to a managed datapack

  --- Freeze / unload / clear ---
  freeze <slug|all>               Pin: keep the current file, skip updating it
  unfreeze <slug|all>             Resume normal updating
  unload <slug|all>               Move the file into the depot; still upgraded/frozen/
                                  chosen normally, flagged with 📦 in the upgrade summary.
                                  Doesn't apply to datapacks — they already live in the depot.
  load <slug|all>                 Move the file back from the depot; no update check
  clear <slug|all|mods|rp|sp|dp>  Delete mod files; quarantine resource/shader/data packs
                                  (incl. the shader .txt config). 'all' covers everything.

  --- Shelf / unshelf (whole profile) ---
  shelf                           Mark the whole profile as shelved. 'upgrade' (and
                                  set-version / upgrade_chooseall / upgrade_masterchoose)
                                  is then blocked with an error; every other command
                                  warns and requires typing 'continue' to proceed.
  unshelf                        Clear the shelved flag, resume normal operation.

  --- Manual version selection ---
  choose <slug>                   Flag a mod: you will be prompted to pick a version
                                  whenever a new release appears on Modrinth
  unchoose <slug>                 Remove the flag, resume auto-updating
  unchoose_all                    Remove the choose flag from every mod
  upgrade_chooseall               Re-show the version picker for every choose-flagged mod,
                                  regardless of whether a new version has appeared —
                                  useful when you want to switch to a specific alpha/beta
  upgrade_masterchoose            Show the version picker for every mod (not just
                                  choose-flagged). Picking a non-installed version
                                  automatically enables choose on that mod. Skipping
                                  or picking the already-installed version does nothing.

  help                            Show this help text

Notes:
  - 'config <preset>' reads Presets/Clients/<preset>.json (next to this script) and
    registers every slug listed under its "mods" / "resourcepacks" / "shaderpacks" /
    "datapacks" keys — same as running 'add'/'add_rp'/'add_sp'/'add_dp' once per slug.
    The preset name is matched case-insensitively against filenames in that folder.
    It never re-registers an already-added slug. Afterwards it asks, once per
    category, for any extra mods/resourcepacks/shaderpacks/datapacks to add by hand
    (space-separated slugs, Enter to skip each), prints a summary of everything
    added/skipped, and offers "Upgrade now? [Y/n]" (Enter = yes) to download it all
    immediately. See Presets/Clients/README.md for the file format.
  - 'add'/'add_rp'/'add_sp'/'add_dp' all accept multiple slugs in one call
    (e.g. 'add sodium lithium fabric-api') — just separate them with spaces, the
    same way you'd pass any other multiple command-line arguments. Each command
    prints a summary of what was added/already-registered, then asks "Upgrade
    now? [Y/n]" (Enter = yes) if anything new was added.
  - 'upgrade <slug>' upgrades just that one mod/resourcepack/shaderpack/datapack —
    everything else in the profile is left untouched. Plain 'upgrade' (no slug) does all.
  - Datapacks are per-world, not per-install, so they're never placed in a live game
    folder — the depot's Datapacks subfolder IS the managed copy. Copy it into a
    world's datapacks folder yourself. Updated datapacks get a loud 🔔 callout (and a
    final reminder line) in the upgrade summary, since a file change there is easy to miss.
  - The depot folder (used for 'unload'/'load') is split into a Shelf subfolder
    (unloaded mod/pack files) and a Datapacks subfolder. Both are created automatically,
    and any files left over from the old flat depot layout are swept into Shelf.
  - Frozen entries keep their current file and are listed (with ❄) in the upgrade summary.
  - 'clear' deletes mod JARs (re-downloaded on next upgrade unless frozen) and MOVES
    resource/shader pack files into the quarantine folder. Shader .txt configs are
    quarantined too, never deleted.
  - If a file of the same name already exists in quarantine, the incoming dupe goes
    into a Dupes_HH_mm_ss subfolder (24h clock) so the existing file is preserved.
  - 'link' lets you point a managed entry at a file you downloaded by hand, so you can
    freeze it without registering a separate manual item.
  - 'unload' moves an entry's file into the depot folder (separate from quarantine).
    It keeps freezing/upgrading/choosing working as normal — 'upgrade' just downloads
    into the depot instead of the active folder — and is flagged with 📦 in the
    summary and 'list'. 'load' moves the file back to its active folder but performs
    no update check. Freeze and unload are independent and can be combined.
  - 'shelf' is a whole-profile flag, unlike freeze/unload which target one entry (or
    'all'). It doesn't touch any files by itself — pair it with 'clear all' first if
    you want an empty profile. While shelved, 'upgrade' always errors out; every other
    command (except 'list'/'help'/'shelf'/'unshelf') prints a warning and requires
    typing 'continue' at the prompt, so accidental changes to a parked profile need a
    deliberate confirmation.
  - choose-flagged mods are listed with ✎ in the upgrade summary, always.
    Skipping a version (Enter or -1) remembers that version — no re-prompt until
    something newer is uploaded. 'upgrade_chooseall' overrides this memory.
  - Mods unavailable for the current version are removed and retried each upgrade.
  - If a mod has a legacy fallback set, upgrade tries the legacy version before giving up.
  - Resource/shader packs unavailable for the current version are kept and marked OUTDATED.
  - Slugs are the last part of the Modrinth URL, e.g. 'sodium' or 'complementary-reimagined'.
  - Config file is Mcmods_<profile>.json next to this script, e.g. 'main' → Mcmods_main.json.
""")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _available_profiles():
    names = []
    for p in SCRIPT_DIR.glob("Mcmods_*.json"):
        stem = p.stem  # "Mcmods_<profile>"
        if stem.startswith("Mcmods_server"):
            continue
        names.append(stem[len("Mcmods_"):])
    return sorted(names)


# Every recognized command — used to spot the common mistake of typing a
# command as the first argument and forgetting the profile in front of it.
_ALL_COMMANDS = {
    "init", "upgrade", "upgrade_chooseall", "upgrade_masterchoose", "set-version", "config", "list",
    "add", "remove", "add-manual", "remove-manual", "legacy_on", "legacy_off", "choose", "unchoose",
    "unchoose_all", "link",
    "add_rp", "remove_rp", "add_manual_rp", "remove_manual_rp", "link_rp",
    "add_sp", "remove_sp", "add_manual_sp", "remove_manual_sp", "link_sp",
    "add_dp", "remove_dp", "add_manual_dp", "remove_manual_dp", "link_dp",
    "freeze", "unfreeze", "unload", "load", "clear",
    "shelf", "unshelf",
    "help",
}


def main():
    global CONFIG_FILE

    args = sys.argv[1:]

    if not args or args[0] in ("help", "--help", "-h"):
        print_help()
        return

    profile = args[0]

    if len(args) < 2:
        if profile in _ALL_COMMANDS:
            print(f"'{profile}' looks like a command, but the profile name has to come first.")
            print(f"Usage: python Mcmods.py <profile> {profile} [args...]")
            print(f"Example: python Mcmods.py main {profile}")
        else:
            print(f"Usage: python Mcmods.py {profile} <command> [args...]")
        print("Run 'python Mcmods.py help' for the full command list.")
        sys.exit(1)

    cmd  = args[1]
    rest = args[2:]

    if cmd in ("help", "--help", "-h"):
        print_help()
        return

    CONFIG_FILE = SCRIPT_DIR / f"Mcmods_{profile}.json"

    if cmd == "init":
        cmd_init()
        return

    if not CONFIG_FILE.exists():
        print(f"No config found for profile '{profile}' (expected {CONFIG_FILE.name}).")
        available = _available_profiles()
        if available:
            print(f"Available profiles: {', '.join(available)}")
        print(f"Run 'python Mcmods.py {profile} init' to create it, or check for typos.")
        sys.exit(1)

    config = load_config()
    migrate_depot_layout(config)

    _UPGRADE_CMDS = {"upgrade", "upgrade_chooseall", "upgrade_masterchoose", "set-version"}
    _SHELF_EXEMPT_CMDS = {"list", "help", "shelf", "unshelf"}

    if config.get("shelved"):
        if cmd in _UPGRADE_CMDS:
            print(f"✗  This profile is SHELVED — '{cmd}' is blocked. Run 'unshelf' first.")
            sys.exit(1)
        elif cmd not in _SHELF_EXEMPT_CMDS:
            print("⚠  This profile is SHELVED.")
            print(f"You're about to run '{cmd}' on a shelved profile — this is usually unintentional.")
            resp = input("Type 'continue' to proceed anyway, or press Enter to abort: ").strip().lower()
            if resp != "continue":
                print("Aborted.")
                return

    if cmd == "upgrade":
        cmd_upgrade(config, rest[0] if rest else None)
    elif cmd == "upgrade_chooseall":
        cmd_upgrade_chooseall(config)
    elif cmd == "upgrade_masterchoose":
        cmd_upgrade_masterchoose(config)
    elif cmd == "set-version":
        if len(rest) < 1:
            print(f"Usage: python Mcmods.py {profile} set-version <version>")
            sys.exit(1)
        cmd_set_version(config, rest[0])
    elif cmd == "config":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} config <preset>"); sys.exit(1)
        cmd_config(config, rest[0])
    elif cmd == "list":
        cmd_list(config)

    # Mods
    elif cmd == "add":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} add <slug> [slug2 ...]"); sys.exit(1)
        cmd_add(config, rest)
    elif cmd == "remove":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} remove <slug>"); sys.exit(1)
        cmd_remove(config, rest[0])
    elif cmd == "add-manual":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} add-manual <filename>"); sys.exit(1)
        cmd_add_manual(config, rest[0])
    elif cmd == "remove-manual":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} remove-manual <filename>"); sys.exit(1)
        cmd_remove_manual(config, rest[0])
    elif cmd == "legacy_on":
        if len(rest) < 2: print(f"Usage: python Mcmods.py {profile} legacy_on <slug> <version>"); sys.exit(1)
        cmd_legacy_on(config, rest[0], rest[1])
    elif cmd == "legacy_off":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} legacy_off <slug>"); sys.exit(1)
        cmd_legacy_off(config, rest[0])
    elif cmd == "choose":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} choose <slug>"); sys.exit(1)
        cmd_choose(config, rest[0])
    elif cmd == "unchoose":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} unchoose <slug>"); sys.exit(1)
        cmd_unchoose(config, rest[0])
    elif cmd == "unchoose_all":
        cmd_unchoose_all(config)
    elif cmd == "link":
        if len(rest) < 2: print(f"Usage: python Mcmods.py {profile} link <slug> <filename>"); sys.exit(1)
        cmd_link(config, rest[0], rest[1])

    # Resource packs
    elif cmd == "add_rp":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} add_rp <slug> [slug2 ...]"); sys.exit(1)
        cmd_add_rp(config, rest)
    elif cmd == "remove_rp":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} remove_rp <slug>"); sys.exit(1)
        cmd_remove_rp(config, rest[0])
    elif cmd == "add_manual_rp":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} add_manual_rp <filename>"); sys.exit(1)
        cmd_add_manual_rp(config, rest[0])
    elif cmd == "remove_manual_rp":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} remove_manual_rp <filename>"); sys.exit(1)
        cmd_remove_manual_rp(config, rest[0])
    elif cmd == "link_rp":
        if len(rest) < 2: print(f"Usage: python Mcmods.py {profile} link_rp <slug> <filename>"); sys.exit(1)
        cmd_link_rp(config, rest[0], rest[1])

    # Shader packs
    elif cmd == "add_sp":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} add_sp <slug> [slug2 ...]"); sys.exit(1)
        cmd_add_sp(config, rest)
    elif cmd == "remove_sp":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} remove_sp <slug>"); sys.exit(1)
        cmd_remove_sp(config, rest[0])
    elif cmd == "add_manual_sp":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} add_manual_sp <filename>"); sys.exit(1)
        cmd_add_manual_sp(config, rest[0])
    elif cmd == "remove_manual_sp":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} remove_manual_sp <filename>"); sys.exit(1)
        cmd_remove_manual_sp(config, rest[0])
    elif cmd == "link_sp":
        if len(rest) < 2: print(f"Usage: python Mcmods.py {profile} link_sp <slug> <filename>"); sys.exit(1)
        cmd_link_sp(config, rest[0], rest[1])

    # Datapacks
    elif cmd == "add_dp":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} add_dp <slug> [slug2 ...]"); sys.exit(1)
        cmd_add_dp(config, rest)
    elif cmd == "remove_dp":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} remove_dp <slug>"); sys.exit(1)
        cmd_remove_dp(config, rest[0])
    elif cmd == "add_manual_dp":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} add_manual_dp <filename>"); sys.exit(1)
        cmd_add_manual_dp(config, rest[0])
    elif cmd == "remove_manual_dp":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} remove_manual_dp <filename>"); sys.exit(1)
        cmd_remove_manual_dp(config, rest[0])
    elif cmd == "link_dp":
        if len(rest) < 2: print(f"Usage: python Mcmods.py {profile} link_dp <slug> <filename>"); sys.exit(1)
        cmd_link_dp(config, rest[0], rest[1])

    # Freeze / clear
    elif cmd == "freeze":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} freeze <slug|all>"); sys.exit(1)
        cmd_freeze(config, rest[0])
    elif cmd == "unfreeze":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} unfreeze <slug|all>"); sys.exit(1)
        cmd_unfreeze(config, rest[0])
    elif cmd == "unload":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} unload <slug|all>"); sys.exit(1)
        cmd_unload(config, rest[0])
    elif cmd == "load":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} load <slug|all>"); sys.exit(1)
        cmd_load(config, rest[0])
    elif cmd == "clear":
        if len(rest) < 1: print(f"Usage: python Mcmods.py {profile} clear <slug|all|mods|rp|sp|dp>"); sys.exit(1)
        cmd_clear(config, rest[0])

    # Shelf / unshelf
    elif cmd == "shelf":
        cmd_shelf(config)
    elif cmd == "unshelf":
        cmd_unshelf(config)

    else:
        print(f"Unknown command: '{cmd}'")
        print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
