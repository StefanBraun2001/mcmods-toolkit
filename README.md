# Minecraft Mod Manager — README

**Script:** `Mcmods.py` — **Version:** R_1.3 (2026-07-16)

This script automatically downloads and updates your Minecraft mods, resource packs, shader packs, and datapacks from [Modrinth](https://modrinth.com). Instead of hunting down updates manually, you just run one command and everything gets updated at once.

This covers the **game-profile** manager (`Mcmods.py`). If you're looking for the dedicated **server** mod/datapack manager, see [README_Server.md](README_Server.md) instead — it's a separate, simpler script.

---

## Requirements

- **Python 3.10 or newer** — download from [python.org](https://www.python.org/downloads/)
- No extra packages needed — the script uses only Python's built-in libraries.

---

## Optional: PowerShell Shortcuts

If you use PowerShell on Windows, `Install-PowerShellIntegration.ps1` (next to this script) adds `Minecraft` and `Minecraft_server` functions to your PowerShell profile.

> **Requires PowerShell 7 or newer** (`pwsh`), not the older Windows PowerShell 5.1 that ships built into Windows. This applies both when *running the installer* and every time afterward when *using* `Minecraft`/`Minecraft_server`/`Minecraft_backup` — they're added to the PowerShell 7 profile file specifically, so running them from a Windows PowerShell 5.1 window won't find them at all (Windows PowerShell 5.1 uses a different, unrelated profile file). If you don't have PowerShell 7+ yet: `winget install --id Microsoft.PowerShell --source winget` (the `--source winget` matters — it avoids installing the sandboxed Microsoft Store build, which is known to cause its own file-access problems), or download it from [aka.ms/powershell](https://aka.ms/powershell). The installer itself checks this and will tell you if it's missing.

Run the installer once, from a PowerShell 7 (`pwsh`) terminal:

```
.\Install-PowerShellIntegration.ps1
```

Afterwards, `Minecraft <command> [args...]` prompts you for which profile to use (e.g. `Minecraft upgrade` asks "Which profile?"), instead of you typing `python "...\Mcmods.py" <profile> <command>` every time. Your last answer is remembered as the default — press Enter to reuse it, or set one explicitly:

```
Minecraft setdefault main
```

`Minecraft help` and `Minecraft readme` work without prompting for a profile. The remembered default lives in a small `PowerShell_Automation.json` file created next to the scripts — separate from your `Mcmods_<profile>.json` configs, and not needed at all if you'd rather call the scripts directly.

The installer also asks whether you want to install an optional third function, `Minecraft_backup`, for world-save backups — see [README_Backup.md](README_Backup.md) for what it does. Answer the prompt, or skip it with `-IncludeBackup` / `-SkipBackup`.

The installer only ever appends to your profile (creating one if you don't have one) and never touches anything else already there. Safe to re-run; pass `-Force` to refresh it after moving the scripts to a new folder (existing `PowerShell_Automation.json`/`Backup_Automation.json` are left untouched either way).

> **Important:** if you move the Scripts folder to a new location, re-run the installer with `-Force` from the new location — otherwise the functions keep pointing at the old path.

---

## Profiles

One script (`Mcmods.py`) manages any number of installs — "profiles" — such as your main install, a second install, or a test install. Every command takes the profile name as its first argument:

```
python Mcmods.py <profile> <command> [args...]
```

For example `python Mcmods.py main upgrade` or `python Mcmods.py side list`. Each profile's settings and tracked mods live in their own `Mcmods_<profile>.json` file next to the script (e.g. `Mcmods_main.json`).

- **Creating a profile:** run `python Mcmods.py <profile> init` — see [First-Time Setup](#first-time-setup) below.
- **Deleting a profile:** just delete its `Mcmods_<profile>.json` file. There's no dedicated delete command — the config file *is* the profile.
- **Typos:** if you run a command against a profile whose config doesn't exist yet, the script tells you so and lists the profiles it did find, instead of failing with a cryptic error.

---

## First-Time Setup

Open a terminal (Command Prompt or PowerShell on Windows), navigate to the folder where you put the script, and run:

```
python Mcmods.py <profile> init
```

Replace `<profile>` with a short name for this install, e.g. `main` or `side`.

The script will ask you a few questions:

| Question | What to enter |
|---|---|
| Minecraft version | e.g. `1.21.4` |
| Mod loader | e.g. `fabric` or `forge` |
| Mods directory | Full path to your `.minecraft/mods` folder |
| Resourcepacks directory | Full path to your `.minecraft/resourcepacks` folder |
| Shaderpacks directory | Full path to your `.minecraft/shaderpacks` folder |
| Quarantine directory | A folder where removed/old packs are backed up (e.g. `C:\MC_Backup`) |
| Depot directory | A separate folder used for temporarily **unloaded** mods/packs and for datapacks (e.g. `C:\MC_Depot`) |
| Shader loader | `iris` or `optifine` (press Enter to use `iris` as default) |

A config file (`Mcmods_<profile>.json`) will be created in the same folder as the script. **Don't delete it** — it tracks everything (and deleting it is also how you remove the profile, see [Profiles](#profiles)).

There's no separate question for a datapacks folder — datapacks are per-**world**, not per-install, so the script never places them in a live game folder. See [Datapacks](#datapacks) below.

---

## Starting with an Existing Mods Folder

If you already have mods, resource packs, or shader packs installed before using this script for the first time, here's what you need to know:

**The script only knows about what you register.** It has no awareness of files already sitting in your folders, so nothing gets touched or deleted just by running `init` or `upgrade`.

Here's how to handle your existing files:

- **Mods that are on Modrinth** — add them with `add <slug>` and run `upgrade`. The script will download the latest version. Your old file won't be deleted automatically if it has a different filename (which it usually will, since filenames include version numbers), so you may need to clean up the old file manually afterwards.
- **Mods you downloaded manually** (not from Modrinth) — register them with `add-manual <filename>` so the script knows about them and they show up in `list`. The file itself is never touched by this command.
- **Anything you don't register at all** — the script ignores it completely. The file stays in the folder and Minecraft will still load it, but it won't appear in `list` and won't be managed.

---

## Everyday Use

### Update everything
```
python Mcmods.py <profile> upgrade
```
Downloads the latest version of every mod, resource pack, shader pack, and datapack you have registered. Already up-to-date items are skipped — but only if the file is actually still there. If a tracked file goes missing (e.g. you deleted it, or moved it instead of copying it), `upgrade` notices it's gone even though the config still points at the latest version, and re-downloads it. This is reported as **🔁 Redownloaded**, separate from **Updated** — it's the same version as before, just fetched again, not a new release.

### Update just one mod or pack
```
python Mcmods.py <profile> upgrade sodium
```
Checks and upgrades only the given slug — everything else in the profile is left completely untouched. Works for mods, resource packs, shader packs, and datapacks alike (whichever category the slug belongs to), and still respects that entry's FROZEN/UNLOADED/CHOOSE flags. Handy when you only want to grab an update for one thing without triggering a full run.

### See what you have installed
```
python Mcmods.py <profile> list
```

---

## Adding and Removing Things

The script uses **Modrinth slugs** to identify mods and packs. The slug is the last part of the Modrinth URL.

> Example: `https://modrinth.com/mod/sodium` → slug is `sodium`

### Mods
```
python Mcmods.py <profile> add <slug>           # Add a mod
python Mcmods.py <profile> add <slug1> <slug2> <slug3>   # Add several at once
python Mcmods.py <profile> remove <slug>        # Remove a mod (also deletes the file)
```

### Resource Packs
```
python Mcmods.py <profile> add_rp <slug> [slug2 ...]
python Mcmods.py <profile> remove_rp <slug>
```

### Shader Packs
```
python Mcmods.py <profile> add_sp <slug> [slug2 ...]
python Mcmods.py <profile> remove_sp <slug>
```

### Datapacks
```
python Mcmods.py <profile> add_dp <slug> [slug2 ...]
python Mcmods.py <profile> remove_dp <slug>
```
See [Datapacks](#datapacks) below for why these behave a bit differently from the other three categories.

`add` / `add_rp` / `add_sp` / `add_dp` all accept **more than one slug** — just list them separated by spaces, the normal way command-line arguments work (Modrinth slugs never contain spaces themselves, so there's no ambiguity). Each command prints a summary of what was added vs. already registered, then asks:

```
Upgrade now? [Y/n]:
```

Press Enter (or `y`) to download everything you just added right away, or `n` to just register it and run `upgrade` yourself later.

---

## Batch-Adding via Presets

If you regularly set up the same bundle of mods/packs on new profiles (e.g. a "performance" bundle or a full modpack list), you can save that bundle as a **preset** and apply it in one command instead of running `add` over and over:

```
python Mcmods.py <profile> config Performance_full
```

This looks for `Performance_full.json` in the `Presets\Clients` folder next to the script — the match is **case-insensitive**, so `config performance_full` finds the same file. Every slug listed in it gets registered (same as running `add` / `add_rp` / `add_sp` / `add_dp` once per entry); nothing already registered is touched twice, and nothing is downloaded yet.

Once the preset's entries are registered, `config` asks once per category:

```
Add anything else by hand before downloading? (space-separated slugs, Enter to skip each)
  Extra mods:
  Extra resource packs:
  Extra shader packs:
  Extra datapacks:
```

so you can top up the bundle — with any of the four types, not just mods — without separate `add`/`add_rp`/`add_sp`/`add_dp` calls. Press Enter on any line to skip that category. It then prints a summary of everything added/skipped and asks:

```
Upgrade now? [Y/n]:
```

Press Enter (or `y`) to download everything right away, or `n` to run `upgrade` yourself whenever you're ready.

A preset file looks like this:

```json
{
  "mods":          ["sodium", "lithium"],
  "resourcepacks": ["faithful-64x"],
  "shaderpacks":   ["complementary-reimagined"],
  "datapacks":     ["terralith"]
}
```

Any category can be omitted or left empty. See `Presets\Clients\README.md` (and the included `Example.json`) for the full format and how to create your own.

---

## Manually Downloaded Files

Some mods or packs aren't on Modrinth (e.g. you downloaded them from a website). You can register them so the script knows about them and won't touch them:

```
python Mcmods.py <profile> add-manual <filename>       # Mods
python Mcmods.py <profile> add_manual_rp <filename>    # Resource packs
python Mcmods.py <profile> add_manual_sp <filename>    # Shader packs
python Mcmods.py <profile> add_manual_dp <filename>     # Datapacks
```

Use `remove-manual` / `remove_manual_rp` / `remove_manual_sp` / `remove_manual_dp` to unregister them. The file itself is never deleted by these commands.

---

## Datapacks

Datapacks are different from mods, resource packs, and shader packs in one important way: they belong to a **world**, not to your Minecraft install. There's no single "datapacks folder" the script could drop them into and expect Minecraft to load them — every world has its own.

So instead of a live game folder, datapacks are tracked and downloaded straight into the **depot's `Datapacks` subfolder** (a sibling of the `Shelf` subfolder described in [Unloading](#unloading-a-mod-or-pack-temporary-removal)). Adding and updating a datapack otherwise works exactly like a resource pack — Modrinth slug, `add_dp`, `upgrade`, `freeze`, `clear dp`, `link_dp` all behave the same way.

```
python Mcmods.py <profile> add_dp terralith
python Mcmods.py <profile> upgrade
```

The download lands in `<depot_dir>\Datapacks\...`. From there, **you copy the file into the `datapacks` folder of whichever world(s) you want it in** — the script has no way to know which worlds you care about, so this step is manual.

> If you grab the file with a *move* instead of a *copy* (or otherwise delete it from the depot), don't worry about it — the next `upgrade` notices the depot copy is gone and re-downloads it, even if the version you had was still the latest. This is **not** reported as a new update: it shows up as **🔁 REDOWNLOADED** instead of 🔔 UPDATED, and it's left out of the "copy into your world" reminder banner, since the script can't tell whether you moved it there on purpose — it just puts the depot back in sync.

Because that copy step is manual and easy to forget, `upgrade` calls out *genuine* datapack updates loudly instead of quietly listing them like everything else:

- Each updated datapack gets a 🔔 line of its own in the summary.
- A final reminder banner repeats the list of updated datapacks at the very bottom of the `upgrade` output.
- A missing-file re-fetch (same version, just gone from the depot) gets its own quieter 🔁 line and closing note instead, so you don't confuse "the depot healed itself" with "there's a new release to go grab."

`unload` / `load` don't apply to datapacks (there's no "active" location to move them out of — they already live in the depot). Use `freeze` to pin a version, or `clear dp` / `clear all` to quarantine the depot copy.

---

## Switching Minecraft Version

```
python Mcmods.py <profile> set-version 1.21.5
```

This updates your config and immediately runs `upgrade` to download versions for the new version.

> **Important:** Mods that don't have a release for the new version yet will have their JAR file **deleted** and be marked **PENDING**. They will be re-downloaded automatically on the next `upgrade` once the mod author releases a compatible version. Resource packs and shader packs are treated differently — their files are kept and marked **OUTDATED** instead of being deleted.
>
> If you want a mod to fall back to an older working version instead of being deleted, set up a legacy fallback before switching (see [Legacy Fallback](#legacy-fallback-for-mods) below).

---

## Freezing a Mod or Pack

Freezing keeps the currently installed file and skips it during upgrades — useful if a new version is broken.

```
python Mcmods.py <profile> freeze sodium        # Freeze one mod
python Mcmods.py <profile> freeze all           # Freeze everything

python Mcmods.py <profile> unfreeze sodium      # Resume updating
python Mcmods.py <profile> unfreeze all
```

Frozen items show up with a ❄ in the upgrade summary as a reminder.

---

## Unloading a Mod or Pack (Temporary Removal)

Unloading moves a mod/pack's file out of your active mods/resourcepacks/shaderpacks folder and into the depot's **`Shelf`** subfolder, without removing it from the config. Unlike `clear`, it's meant to be temporary and doesn't lose track of the entry.

> The depot folder (`depot_dir`) has two subfolders managed automatically: `Shelf` for unloaded mod/pack files, and `Datapacks` for datapack depot copies (see [Datapacks](#datapacks)). Both are created the first time you run any command, and any files left over from an older, flat depot layout are swept into `Shelf` automatically.

```
python Mcmods.py <profile> unload sodium        # Unload one entry
python Mcmods.py <profile> unload all           # Unload everything

python Mcmods.py <profile> load sodium          # Move it back
python Mcmods.py <profile> load all
```

Key points:

- **Everything else still works on an unloaded entry.** You can still `freeze` it, `choose` a specific version for it, and `upgrade` will still check Modrinth for it — it just downloads into the depot instead of your active folder. This is different from `freeze`, which skips the entry entirely.
- Unloaded entries show up with a 📦 in both the upgrade summary and `list`, so you don't forget they're parked.
- `load` only moves the file back — it does **not** check for updates. If you want the latest version after loading it back, run `upgrade` afterwards.
- `freeze` and `unload` are independent — an entry can be frozen, unloaded, both, or neither.
- Shader pack `.txt` config files move to the depot along with the pack, and move back together with `load`.
- Datapacks don't support `unload`/`load` — they already live in the depot's `Datapacks` subfolder permanently (see [Datapacks](#datapacks)).

---

## Shelving a Whole Profile (Parking an Unused Install)

If you have a profile (a separate config file, e.g. for a second Minecraft install) that you're not using for a while, `shelf` marks the **entire profile** as parked. Unlike `freeze`/`unload`, this isn't per-entry — it's a single flag for the whole config.

```
python Mcmods.py <profile> clear all            # (optional) empty the profile out first
python Mcmods.py <profile> shelf                # Mark the whole profile as shelved

python Mcmods.py <profile> unshelf              # Resume normal operation
```

While a profile is shelved:

- **`upgrade` (and `set-version`, `upgrade_chooseall`, `upgrade_masterchoose`) is blocked outright** with an error message — there's no way to skip this short of unshelving.
- **Every other command** (`add`, `remove`, `freeze`, `unload`, `clear`, `choose`, `link`, etc.) prints a warning and asks you to type `continue` to proceed. Pressing Enter (or anything else) aborts the command. This is meant to catch accidental changes to a profile you'd parked on purpose — you can still push through if you really mean it.
- `list` and `help` always work normally, and `list` prints a banner reminding you the profile is shelved.
- Shelving doesn't touch any files by itself. If you want a fully empty profile while shelved, run `clear all` first (mods are deleted, resource/shader packs go to quarantine).

---

## Manual Version Selection (Advanced)

If you want to pick a specific version of a mod instead of always getting the latest:

```
python Mcmods.py <profile> choose sodium
```

From now on, whenever `upgrade` finds a new version of that mod, it will show you a numbered list and let you pick — or skip it. Pressing Enter skips without installing, and the script won't ask again until something even newer is uploaded.

```
python Mcmods.py <profile> unchoose sodium      # Go back to auto-updating
```

To re-show the version picker for all choose-flagged mods at once (useful if you want to switch to an alpha or beta):
```
python Mcmods.py <profile> upgrade_chooseall
```

---

## Linking a Manual File to a Managed Entry

Sometimes a mod is on Modrinth but you already downloaded it by hand. You can attach that file to the managed entry so the script tracks it:

```
python Mcmods.py <profile> link <slug> <filename>
python Mcmods.py <profile> link_rp <slug> <filename>
python Mcmods.py <profile> link_sp <slug> <filename>
python Mcmods.py <profile> link_dp <slug> <filename>
```

After linking, you can `freeze` the entry if you want to keep that exact file.

---

## Clearing Files

The `clear` command removes files locally (mods are deleted; resource/shader packs are moved to your quarantine folder as a backup):

```
python Mcmods.py <profile> clear sodium         # Clear one entry
python Mcmods.py <profile> clear mods           # Clear all mods
python Mcmods.py <profile> clear rp             # Clear all resource packs
python Mcmods.py <profile> clear sp             # Clear all shader packs
python Mcmods.py <profile> clear dp             # Clear all datapacks (depot copies)
python Mcmods.py <profile> clear all            # Clear everything
```

After clearing, run `upgrade` to re-download everything.

> Shader pack `.txt` config files (which store your in-game settings) are always moved to quarantine, never deleted, so you don't lose your shader settings.

---

## Legacy Fallback for Mods

If a mod hasn't been updated for your current Minecraft version, you can tell the script to fall back to an older version automatically:

```
python Mcmods.py <profile> legacy_on modslug 1.20.1
python Mcmods.py <profile> legacy_off modslug
```

The mod will show as **LEGACY** in the upgrade summary. Once the mod gets updated for your current version, the script switches automatically.

Running `legacy_off` will **delete the legacy JAR** if it was already downloaded and active, then mark the mod as PENDING so it retries the current version on the next `upgrade`. If the legacy version was never actually downloaded (e.g. you set it but never ran `upgrade`), no file is deleted.

---

## Status Icons in the Upgrade Summary

| Icon / Label | Meaning |
|---|---|
| (listed normally) | Up to date |
| ❄ FROZEN | Skipped — you pinned this version |
| 📦 UNLOADED | File lives in the depot, not the active folder — still gets checked/updated there |
| ⚠ PENDING | Not available for your MC version yet — will retry next upgrade |
| ⚠ LEGACY | Running on an older MC version as a fallback |
| ⚠ OUTDATED | Resource/shader/data pack not available for your version — kept as-is |
| ✎ CHOOSE | You manually selected a version for this mod |
| 🔔 UPDATED | Datapack changed in the depot — copy it into your world(s) manually |
| 🔁 REDOWNLOADED | Same version as before, but the file was missing and got silently re-fetched — not a new release |
| ✗ | Something went wrong — error message shown next to it |

A profile-wide banner also appears in `list` (and `upgrade` is blocked outright) when the whole profile is **SHELVED** — see [Shelving a Whole Profile](#shelving-a-whole-profile-parking-an-unused-install).

---

## Getting Help

```
python Mcmods.py help
```

---

## Tips

- Each config file (`Mcmods_<profile>.json`) is just a text file. You can open it with Notepad to see what's tracked, but avoid editing it by hand unless you know what you're doing.
- If you share this script with friends, each person runs `init` with a profile name of their choice to set up their own config pointing to their own Minecraft folders.
- The script only uses Modrinth — mods from CurseForge or other sites need to be added as manual entries.
