# World-Save Backups (Optional Add-On) — README

**Feature:** `Minecraft_backup` — installed by `Install-PowerShellIntegration.ps1`.

**Installer script version:** R_1.3 (2026-07-16).

This is an optional PowerShell-only feature (there's no standalone `.py` script for it) that zips up — or plain-copies — the world folders inside a Minecraft `saves` directory into a destination folder of your choice, using 7-Zip. It supports any number of independent backup "jobs" (e.g. one per install/profile), each with its own saves folder, destination folder, and settings.

It has nothing to do with `Mcmods.py`/`Mcmods_server.py` other than sharing the same installer and the same Scripts folder — see [README.md](README.md) and [README_Server.md](README_Server.md) for the mod managers themselves.

---

## Requirements

- **PowerShell 7 or newer** (`pwsh`) — both to run the installer and to actually use `Minecraft_backup` afterward. Windows PowerShell 5.1 (the one built into Windows) uses a different profile file and won't have the function available. See [README.md](README.md#optional-powershell-shortcuts) for how to install PowerShell 7+.
- **7-Zip**, with `7z` available on your PATH (installing 7-Zip normally does this, or add its folder to PATH yourself). Only needed if you use `zip` mode — `copy` mode doesn't need it.

---

## Installing

This feature is opt-in and is not installed by default. When you run:

```
.\Install-PowerShellIntegration.ps1
```

it asks: `Also install the optional world-save backup feature, Minecraft_backup? [y/N]`. Answer `y`, or pass a switch to skip the prompt:

```
.\Install-PowerShellIntegration.ps1 -IncludeBackup
.\Install-PowerShellIntegration.ps1 -SkipBackup
```

This creates a `Backup_Automation.json` file next to the scripts (only if one doesn't already exist) and adds the `Minecraft_backup` function to your PowerShell profile.

> **Important:** if you move the Scripts folder to a new location later, re-run the installer with `-Force` from the new location — otherwise `Minecraft_backup` (and `Minecraft`/`Minecraft_server`) keep pointing at the old path.

---

## No Passwords Are Ever Stored

`Backup_Automation.json` only remembers *whether* a job is encrypted — never the password itself. If a job has encryption turned on, `Minecraft_backup run` prompts you for the password fresh, every single time, and only holds it in memory for that one run.

Entry is **masked** (typed characters aren't echoed to the screen at all), then it asks `Show password to confirm it's correct? Y/N` — an explicit opt-in reveal if you want to double-check what you typed. If you reveal it and it's wrong, answering `N` to the follow-up `Is this correct?` re-prompts from scratch instead of proceeding with a bad password.

Two caveats worth knowing, inherent to any script that has to hand 7-Zip a password:
- If you use the reveal, the plaintext is printed once — it'll sit in your terminal's scrollback for the rest of that session, and permanently if you're running inside a transcript (`Start-Transcript`). Avoid revealing it in a recorded/shared terminal session if that matters to you.
- 7-Zip's CLI only accepts the password as a plain command-line argument, so it briefly exists in the `7z` child process's command line — visible to other processes on the same machine with sufficient privilege (e.g. Task Manager's "Command line" column) for as long as that process runs. There's no way around this short of 7-Zip supporting a non-argv way to receive a password, which it doesn't.

---

## Everyday Use

### List configured jobs
```
Minecraft_backup list
```

### Add a job
```
Minecraft_backup add
```
Prompts for:

| Question | What to enter |
|---|---|
| Label | A short name for this job, e.g. `main` or `side1` |
| Saves directory | The folder containing world folders (e.g. `...\saves`) |
| Destination directory | Where backups get written |
| Mode | `zip` (7-Zip archive) or `copy` (plain folder copy) |
| Encrypt? | Only relevant for `zip` mode — see [password handling](#no-passwords-are-ever-stored) above |
| Compression preset | Only relevant for `zip` mode — see [below](#compression-presets) |

### Edit a job
```
Minecraft_backup edit <job>
```
Re-prompts each setting showing its current value — press Enter on any prompt to keep it as-is.

### Remove a job
```
Minecraft_backup remove <job>
```
Only forgets the job — nothing on disk is touched or deleted.

### Run a job
```
Minecraft_backup run <job>
Minecraft_backup run all
Minecraft_backup run <job> <filter>
```
`<job>` matches against job labels — an exact label always wins, but you can also type a partial label. `all` runs every configured job. An optional `<filter>` narrows which world folders inside the saves directory are included (matches anywhere in the folder name), same as before.

---

## When a Job Name Matches More Than One Job

`<job>` in `edit`, `remove`, and `run` is matched as a substring against every job's label — if more than one job matches, you'll get a numbered picker instead of an error:

```
Multiple backup jobs match 'side':
  1) side1  (C:\...\saves -> C:\...\Backup_side1)
  2) side2  (C:\...\saves -> C:\...\Backup_side2)
Choice:
```

For `run`, you can also type `a` at this picker to run every matching job instead of just one.

---

## Compression Presets

Chosen when you `add` a job (zip mode only), and changeable later via `edit`:

| Preset | Behavior |
|---|---|
| 1 — Windows default | Fast, standard compression (`-mx5`) — closest to what Windows' own "Compress to zip" does |
| 2 — High efficiency | Maximum compression, high memory/CPU/thread usage — best ratio, slowest, heaviest on your machine |
| 3 — High efficiency, lower usage (**default**) | Same compression method as #2, but with a smaller dictionary, fewer threads, and less memory — a good middle ground for machines you don't want pegged at 100% during a backup |

You can also type `c` to enter fully custom 7-Zip arguments instead of picking a preset.

---

## `copy` Mode

Instead of zipping, `copy` mode plain-copies each matching world folder into the destination directory as-is (overwriting anything already there with the same name). No compression, no encryption, no 7-Zip dependency — just a straight folder copy, useful if you want quick, browsable backups rather than compact archives.

---

## Getting Help

```
Minecraft_backup help
Minecraft_backup readme
```

`help` prints the command list; `readme` opens this file.
