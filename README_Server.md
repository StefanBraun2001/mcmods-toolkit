# Minecraft Server Mod Manager — README

**Script:** `Mcmods_server.py` — **Version:** R_1.2 (2026-07-10)

This is the **server** variant of the mod manager: it downloads the mods and datapacks you want to run on a Minecraft server from [Modrinth](https://modrinth.com) into a download folder of your choosing, ready to be copied onto the server (or symlinked into it). Unlike the game-profile manager (`Mcmods.py`, see [README.md](README.md)), it has no concept of resource packs or shader packs, and it doesn't touch your actual server installation directly — it's an intermediate staging folder that you move into place yourself.

---

## Requirements

- **Python 3.10 or newer** — download from [python.org](https://www.python.org/downloads/)
- No extra packages needed — the script uses only Python's built-in libraries.

---

## Optional: PowerShell Shortcuts

If you use PowerShell on Windows, `Install-PowerShellIntegration.ps1` (next to this script) adds a `Minecraft_server` function to your PowerShell profile — one installer covers both this script and `Mcmods.py`. Afterwards, `Minecraft_server <command> [args...]` (e.g. `Minecraft_server upgrade`) prompts you for which server profile to use, remembering your last choice as the default (`Minecraft_server setdefault <profile>` to set one explicitly). See [README.md](README.md#optional-powershell-shortcuts) for the full details, including where the remembered default is stored.

> **Requires PowerShell 7 or newer** (`pwsh`) — both to run the installer and to actually use `Minecraft_server` afterward. Windows PowerShell 5.1 (the one built into Windows) uses a different profile file and won't have the function available. See [README.md](README.md#optional-powershell-shortcuts) for how to install PowerShell 7+.

The same installer can also optionally add a `Minecraft_backup` function for world-save backups — unrelated to this server script, but installed the same way. See [README_Backup.md](README_Backup.md).

---

## Profiles

One script (`Mcmods_server.py`) manages any number of servers — "profiles" — each with its own mod/datapack set and its own download folder, so mods for different servers never mix. Every command takes the profile name as its first argument:

```
python Mcmods_server.py <profile> <command> [args...]
```

For example `python Mcmods_server.py survival upgrade` or `python Mcmods_server.py creative list`.

- Each profile's settings and tracked mods live in their own `Mcmods_server_<profile>.json` file next to the script.
- Each profile has its own download directory, chosen when you run `init` — give each profile a different folder to keep servers isolated.
- **Creating a profile:** run `python Mcmods_server.py <profile> init` — see [First-Time Setup](#first-time-setup) below.
- **Deleting a profile:** just delete its `Mcmods_server_<profile>.json` file (and its download folder, if you want the downloaded files gone too). There's no dedicated delete command.
- **Typos:** if you run a command against a profile whose config doesn't exist yet, the script tells you so and lists the profiles it did find, instead of failing with a cryptic error.

---

## First-Time Setup

Open a terminal (Command Prompt or PowerShell on Windows), navigate to the folder where you put the script, and run:

```
python Mcmods_server.py <profile> init
```

Replace `<profile>` with a short name for this server, e.g. `survival` or `creative`.

The script will ask you a few questions:

| Question | What to enter |
|---|---|
| Minecraft version | e.g. `1.21.4` |
| Mod loader | e.g. `fabric` or `forge` |
| Download directory | Full path to a folder where mods/datapacks for this server should be downloaded (e.g. `C:\MC_Server_Survival`) |

A config file (`Mcmods_server_<profile>.json`) is created next to the script, and the download directory is created if it doesn't already exist. **Don't delete the config file** — it tracks everything (and deleting it is also how you remove the profile, see [Profiles](#profiles)).

---

## Everyday Use

### Update everything
```
python Mcmods_server.py <profile> upgrade
```
Downloads the latest version of every mod and datapack you have registered for that profile. Already up-to-date items are skipped.

### Update just one mod or datapack
```
python Mcmods_server.py <profile> upgrade <slug>
```
Checks and upgrades only the given slug — everything else in the profile is left completely untouched. Works whether the slug is a mod or a datapack, and still respects that entry's FROZEN/CHOOSE flags.

### See what you have installed
```
python Mcmods_server.py <profile> list
```

### Get the mods onto your actual server

This script only fills the download directory you chose at `init` — it does not know where your server's actual `mods`/`world/datapacks` folders are. After `upgrade`, copy (or symlink) the downloaded files into your server install yourself.

---

## Adding and Removing Things

The script uses **Modrinth slugs** to identify mods and datapacks. The slug is the last part of the Modrinth URL.

> Example: `https://modrinth.com/mod/lithium` → slug is `lithium`

### Mods
```
python Mcmods_server.py <profile> add <slug>
python Mcmods_server.py <profile> remove <slug>
```

### Datapacks
```
python Mcmods_server.py <profile> add_dp <slug>
python Mcmods_server.py <profile> remove_dp <slug>
```

Datapacks are looked up on Modrinth using the `datapack` loader, independent of your mod loader. After adding anything, run `upgrade` to actually download it.

---

## Manually Downloaded Files

For mods/datapacks that aren't on Modrinth, register them so the script knows about them without touching them:

```
python Mcmods_server.py <profile> add-manual <filename>       # Mods
python Mcmods_server.py <profile> add_manual_dp <filename>    # Datapacks
```

Use `remove-manual` / `remove_manual_dp` to unregister them. The file itself is never deleted by these commands.

You can also attach a manually downloaded file to an already-managed entry so the script tracks it (e.g. so you can `freeze` it):

```
python Mcmods_server.py <profile> link <slug> <filename>
python Mcmods_server.py <profile> link_dp <slug> <filename>
```

---

## Switching Minecraft Version

```
python Mcmods_server.py <profile> set-version 1.21.5
```

Mods/datapacks without a release for the new version have their file **deleted** and are marked **PENDING**; they're retried automatically on the next `upgrade`. If you want one to fall back to an older working version instead, set up a legacy fallback first (see below).

---

## Freezing a Mod or Datapack

Freezing keeps the currently installed file and skips it during upgrades:

```
python Mcmods_server.py <profile> freeze <slug|all>
python Mcmods_server.py <profile> unfreeze <slug|all>
```

Frozen items show up with a ❄ in the upgrade summary and in `list`.

---

## Legacy Fallback

If a mod/datapack hasn't been updated for your current Minecraft version yet, tell the script to fall back to an older version automatically:

```
python Mcmods_server.py <profile> legacy_on <slug> 1.20.1
python Mcmods_server.py <profile> legacy_off <slug>

python Mcmods_server.py <profile> legacy_on_dp <slug> 1.20.1
python Mcmods_server.py <profile> legacy_off_dp <slug>
```

The entry shows as **LEGACY** until the mod/datapack author releases a version for your current Minecraft version, at which point the script switches back automatically.

---

## Manual Version Selection (Advanced)

Pick a specific version yourself instead of always getting the latest:

```
python Mcmods_server.py <profile> choose <slug>          # Mods
python Mcmods_server.py <profile> choose_dp <slug>        # Datapacks
```

Whenever `upgrade` finds a new version, it shows a numbered list and lets you pick or skip. Skipping remembers that version — no re-prompt until something newer appears.

```
python Mcmods_server.py <profile> unchoose <slug>
python Mcmods_server.py <profile> unchoose_dp <slug>
```

Re-show the picker for every choose-flagged entry, or for everything regardless of flag:

```
python Mcmods_server.py <profile> upgrade_chooseall
python Mcmods_server.py <profile> upgrade_masterchoose
```

---

## Clearing Files

```
python Mcmods_server.py <profile> clear <slug>          # Clear one entry
python Mcmods_server.py <profile> clear mods            # Clear all mods
python Mcmods_server.py <profile> clear dp              # Clear all datapacks
python Mcmods_server.py <profile> clear all             # Clear everything
```

Deletes the files locally (nothing is quarantined — there's no quarantine folder in the server variant). Run `upgrade` afterwards to re-download non-frozen entries.

---

## Status Icons in the Upgrade Summary

| Icon / Label | Meaning |
|---|---|
| (listed normally) | Up to date |
| ❄ FROZEN | Skipped — you pinned this version |
| ⚠ PENDING | Not available for your MC version yet — will retry next upgrade |
| ⚠ LEGACY | Running on an older MC version as a fallback |
| ✎ CHOOSE | You manually selected a version for this entry |
| ✗ | Something went wrong — error message shown next to it |

---

## Getting Help

```
python Mcmods_server.py help
```

---

## Tips

- Each config file (`Mcmods_server_<profile>.json`) is just a text file. You can open it with Notepad to see what's tracked, but avoid editing it by hand unless you know what you're doing.
- The script only uses Modrinth — mods/datapacks from CurseForge or other sites need to be added as manual entries.
- Resource packs and shader packs aren't a thing on the server side — this variant only handles mods and datapacks.
- This is a different tool from the game-profile manager (`Mcmods.py`) — see [README.md](README.md) for that one.
