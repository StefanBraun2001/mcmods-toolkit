# Client Presets

Each `.json` file in this folder is a **preset** you can batch-apply to any `Mcmods.py` profile with:

```
python Mcmods.py <profile> config <preset>
```

`<preset>` is matched **case-insensitively** against the filenames here, so `config performance_full`, `config Performance_Full`, and `config PERFORMANCE_FULL` all resolve to `Performance_Full.json`.

Running `config` only **registers** the slugs listed in the preset — same as running `add` / `add_rp` / `add_sp` / `add_dp` once per entry. It never re-adds a slug that's already in the profile, and it never downloads anything itself. Run `upgrade` afterwards to actually fetch the files.

---

## File format

```json
{
  "mods":          ["sodium", "lithium", "..."],
  "resourcepacks": ["..."],
  "shaderpacks":   ["..."],
  "datapacks":     ["..."]
}
```

- Every key is optional — omit any category the preset doesn't touch, or leave it as an empty list.
- Values are **Modrinth slugs** (the last part of the project's Modrinth URL, e.g. `https://modrinth.com/mod/sodium` → `sodium`), same as you'd pass to `add <slug>`.
- Keys other than `mods` / `resourcepacks` / `shaderpacks` / `datapacks` are ignored, so feel free to add a `"_comment"` key for your own notes (JSON has no native comment syntax).

See `Example.json` in this folder for a minimal working preset.

## Creating a new preset

Just add a new `.json` file here (any name — that name, minus `.json`, is what you type after `config`). No registration step needed; the script scans this folder every time `config` runs.
