<#
.SYNOPSIS
    Version: B_0.5 (2026-07-06) - beta.

    Adds 'Minecraft', 'Minecraft_server', and (optionally) 'Minecraft_backup' helper
    functions to your PowerShell profile.

.DESCRIPTION
    Adds wrapper functions to your PowerShell profile ($PROFILE):

        Minecraft <command> [args...]
        Minecraft_server <command> [args...]
        Minecraft_backup <command> [args...]     (optional, world-save backups)

    Each of Minecraft/Minecraft_server prompts you for which profile to use (remembering
    your last choice as the default, so pressing Enter repeats it), then runs the matching
    script with whatever command/args you gave. The remembered defaults live in a small
    "PowerShell_Automation.json" file created next to the scripts - separate from the
    Mcmods_<profile>.json / Mcmods_server_<profile>.json config files, and not needed at
    all if you'd rather call the scripts directly.

    Minecraft_backup is an optional world-save backup feature (see README_Backup.md). It
    is only installed if you opt in (interactively, or via -IncludeBackup). Its settings
    live in their own "Backup_Automation.json" file - no passwords are ever stored in it.

    This assumes Mcmods.py and Mcmods_server.py live in the same folder as this installer
    script - that folder path is detected automatically and baked into the added functions.

    IMPORTANT: If you move this Scripts folder to a new location later, re-run this
    installer with -Force from the new location - otherwise the added functions keep
    pointing at the old path.

    Safety: this script only ever APPENDS to your profile (creating one if you don't have
    one yet). It never touches anything else already in the file. Re-running it is safe -
    it recognizes the blocks it previously added (by marker comments) and leaves them alone
    unless you pass -Force, in which case only those marked blocks are refreshed. The
    PowerShell_Automation.json / Backup_Automation.json files, if they already exist, are
    never overwritten by a re-run.

.PARAMETER Force
    If the functions were already installed by a previous run, replace that block instead
    of leaving it untouched.

.PARAMETER IncludeBackup
    Also install the optional Minecraft_backup (world-save backup) feature without asking.

.PARAMETER SkipBackup
    Skip the optional Minecraft_backup feature without asking.

.EXAMPLE
    .\Install-PowerShellIntegration.ps1

.EXAMPLE
    .\Install-PowerShellIntegration.ps1 -Force -IncludeBackup
#>

param(
    [switch]$Force,
    [switch]$IncludeBackup,
    [switch]$SkipBackup
)

$InstallerVersion     = "B_0.5"
$InstallerVersionDate = "2026-07-06"

if ($PSVersionTable.PSVersion.Major -lt 7) {
    Write-Host "This installer requires PowerShell 7 or newer (you're running $($PSVersionTable.PSVersion))."
    Write-Host "Windows PowerShell 5.1 uses a different `$PROFILE file than PowerShell 7+, so the functions"
    Write-Host "this installs would end up in the wrong place."

    if (Get-Command winget -ErrorAction SilentlyContinue) {
        $installNow = Read-Host "Install PowerShell 7+ now via winget? [y/N]"
        if ($installNow -match '^(y|yes)$') {
            # "--source winget" matters here: it pins this to the GitHub-released MSI
            # package. Without it, winget may resolve to the Microsoft Store build
            # instead, which runs sandboxed (AppX/AppContainer) and can cause its own
            # set of file-access/PATH problems unrelated to this installer.
            winget install --id Microsoft.PowerShell --source winget
            Write-Host ""
            Write-Host "Once that finishes, close this window, open a new 'PowerShell 7' (pwsh) terminal, and re-run this installer."
            exit 1
        }
    }

    Write-Host "Install PowerShell 7+ via 'winget install --id Microsoft.PowerShell --source winget'"
    Write-Host "(or from https://aka.ms/powershell), then re-run this script using 'pwsh' instead of 'powershell'."
    exit 1
}

$ScriptsFolder = $PSScriptRoot
if (-not $ScriptsFolder) {
    Write-Host "Could not determine the folder this installer lives in. Run it as a .ps1 file, not pasted/piped."
    exit 1
}

Write-Host "Install-PowerShellIntegration.ps1 - version $InstallerVersion ($InstallerVersionDate, beta)"
Write-Host "Scripts folder detected as: $ScriptsFolder"
Write-Host "Note: if you move this Scripts folder later, re-run this installer with -Force from the new location."

foreach ($name in "Mcmods.py", "Mcmods_server.py") {
    if (-not (Test-Path (Join-Path $ScriptsFolder $name))) {
        Write-Host "Warning: $name not found next to this installer ($ScriptsFolder). The wrapper functions will still be added, but won't work until it's there."
    }
}

$AutomationFile = Join-Path $ScriptsFolder "PowerShell_Automation.json"
if (-not (Test-Path $AutomationFile)) {
    @{ DefaultProfile = $null; DefaultServerProfile = $null } | ConvertTo-Json | Set-Content $AutomationFile -Encoding UTF8
    Write-Host "Created $AutomationFile"
} else {
    Write-Host "Found existing $AutomationFile - leaving it as-is."
}

if ($IncludeBackup -and $SkipBackup) {
    Write-Host "Both -IncludeBackup and -SkipBackup were given; ignoring both and asking interactively."
    $IncludeBackup = $false
    $SkipBackup = $false
}

$installBackup = $false
if ($IncludeBackup) {
    $installBackup = $true
} elseif ($SkipBackup) {
    $installBackup = $false
} else {
    $answer = Read-Host "Also install the optional world-save backup feature, Minecraft_backup? [y/N]"
    $installBackup = $answer -match '^(y|yes)$'
}

function Install-MCBlock {
    param(
        [string]$MarkerBegin,
        [string]$MarkerEnd,
        [string]$Block,
        [string]$Label
    )

    if (-not (Test-Path $PROFILE)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $PROFILE) | Out-Null
        New-Item -ItemType File -Path $PROFILE | Out-Null
        Write-Host "Created a new PowerShell profile at: $PROFILE"
    }

    $existing = Get-Content $PROFILE -Raw -ErrorAction SilentlyContinue
    if ($null -eq $existing) { $existing = "" }

    if ($existing -match [regex]::Escape($MarkerBegin)) {
        if (-not $Force) {
            Write-Host "$Label functions are already installed in: $PROFILE"
            Write-Host "Re-run with -Force to refresh them (e.g. after moving the scripts to a new folder)."
            return
        }
        $pattern = "(?s)" + [regex]::Escape($MarkerBegin) + ".*?" + [regex]::Escape($MarkerEnd)
        # NOTE: must use a MatchEvaluator (scriptblock), not a plain replacement string -
        # .NET regex treats "$_", "$1", "$$" etc. in a literal replacement string as special
        # tokens, and $Block is full of literal "$_"/"$something" text that would otherwise
        # get corrupted/substituted instead of inserted verbatim.
        $evaluator = [System.Text.RegularExpressions.MatchEvaluator] { $Block.Trim() }
        $updated = [regex]::Replace($existing, $pattern, $evaluator)
        Set-Content -Path $PROFILE -Value $updated -Encoding UTF8
        Write-Host "Updated the $Label functions already in: $PROFILE"
    } else {
        Add-Content -Path $PROFILE -Value "`n$($Block.Trim())`n"
        Write-Host "Added $Label functions to: $PROFILE"
    }
}

$MarkerBegin = "# >>> Mcmods PowerShell functions (added by Install-PowerShellIntegration.ps1) >>>"
$MarkerEnd   = "# <<< Mcmods PowerShell functions <<<"

$block = @"
$MarkerBegin
# Folder containing Mcmods.py / Mcmods_server.py, and PowerShell_Automation.json.
# Detected automatically when this was installed ($ScriptsFolder) - edit this line by hand
# if you move the scripts afterwards, or re-run Install-PowerShellIntegration.ps1 -Force
# from their new location.
`$MCScriptFolder    = "$ScriptsFolder"
`$MCAutomationFile  = Join-Path `$MCScriptFolder "PowerShell_Automation.json"

function Get-MCAutomationConfig {
    if (-not (Test-Path `$MCAutomationFile)) {
        return [pscustomobject]@{ DefaultProfile = `$null; DefaultServerProfile = `$null }
    }
    `$content = Get-Content `$MCAutomationFile -Raw
    if ([string]::IsNullOrWhiteSpace(`$content)) {
        return [pscustomobject]@{ DefaultProfile = `$null; DefaultServerProfile = `$null }
    }
    return `$content | ConvertFrom-Json
}

function Set-MCAutomationValue {
    param([string]`$Key, [string]`$Value)
    `$raw = Get-MCAutomationConfig
    if (`$raw.PSObject.Properties.Name -contains `$Key) {
        `$raw.`$Key = `$Value
    } else {
        `$raw | Add-Member -NotePropertyName `$Key -NotePropertyValue `$Value -Force
    }
    `$raw | ConvertTo-Json -Depth 5 | Set-Content `$MCAutomationFile -Encoding UTF8
}

function Get-MCAvailableProfiles {
    param([string]`$Prefix)
    # Mcmods_server_*.json also matches the "Mcmods_" game-profile prefix, so exclude
    # it explicitly unless server profiles are what we're actually listing.
    Get-ChildItem -Path `$MCScriptFolder -Filter "`$Prefix*.json" -ErrorAction SilentlyContinue |
        Where-Object {
            `$_.Name -ne "PowerShell_Automation.json" -and
            (`$Prefix -eq "Mcmods_server_" -or -not `$_.Name.StartsWith("Mcmods_server_"))
        } |
        ForEach-Object { `$_.BaseName.Substring(`$Prefix.Length) } |
        Sort-Object
}

function Minecraft {
    param(
        [Parameter(Position = 0)]
        [string]`$Command,

        [Parameter(Position = 1, ValueFromRemainingArguments = `$true)]
        [string[]]`$Rest
    )

    `$cfg     = Get-MCAutomationConfig
    `$default = `$cfg.DefaultProfile

    if (-not `$Command) {
        Write-Host "Usage: Minecraft <command> [args...]"
        Write-Host "Examples: Minecraft upgrade | Minecraft add sodium | Minecraft list"
        Write-Host "Default profile: `$(if (`$default) { `$default } else { '(none)' })  (change with: Minecraft setdefault <profile>)"
        Write-Host "Run 'Minecraft help' to see the full command list from the script itself."
        return
    }

    if (`$Command -eq "setdefault") {
        if (-not `$Rest) { Write-Host "Usage: Minecraft setdefault <profile>"; return }
        `$profileName   = `$Rest[0]
        `$profileConfig = Join-Path `$MCScriptFolder "Mcmods_`$profileName.json"
        if (-not (Test-Path `$profileConfig)) {
            Write-Host "No profile config found for '`$profileName' (expected `$profileConfig)."
            return
        }
        Set-MCAutomationValue -Key "DefaultProfile" -Value `$profileName
        Write-Host "Default profile set to `$profileName"
        return
    }

    if (`$Command -eq "readme") {
        Invoke-Item (Join-Path `$MCScriptFolder "README.md")
        return
    }

    if (`$Command -in "help", "--help", "-h") {
        python (Join-Path `$MCScriptFolder "Mcmods.py") help
        return
    }

    `$promptText = if (`$default) { "Which profile? [default: `$default]" } else { "Which profile?" }
    `$choice = Read-Host `$promptText
    if (-not `$choice -and `$default) { `$choice = `$default }

    if (-not `$choice) {
        Write-Host "No profile given."
        return
    }

    `$script        = Join-Path `$MCScriptFolder "Mcmods.py"
    `$profileConfig = Join-Path `$MCScriptFolder "Mcmods_`$choice.json"
    if (-not (Test-Path `$profileConfig) -and `$Command -ne "init") {
        Write-Host "No profile config found for '`$choice' (expected `$profileConfig)."
        `$available = Get-MCAvailableProfiles -Prefix "Mcmods_"
        if (`$available) { Write-Host "Available profiles: `$(`$available -join ', ')" }
        Write-Host "Run 'python ``"`$script``" `$choice init' to create it, or check for typos."
        return
    }

    python `$script `$choice `$Command @Rest
}

function Minecraft_server {
    param(
        [Parameter(Position = 0)]
        [string]`$Command,

        [Parameter(Position = 1, ValueFromRemainingArguments = `$true)]
        [string[]]`$Rest
    )

    `$cfg     = Get-MCAutomationConfig
    `$default = `$cfg.DefaultServerProfile

    if (-not `$Command) {
        Write-Host "Usage: Minecraft_server <command> [args...]"
        Write-Host "Examples: Minecraft_server upgrade | Minecraft_server add lithium | Minecraft_server list"
        Write-Host "Default server profile: `$(if (`$default) { `$default } else { '(none)' })  (change with: Minecraft_server setdefault <profile>)"
        Write-Host "Run 'Minecraft_server help' to see the full command list from the script itself."
        return
    }

    if (`$Command -eq "setdefault") {
        if (-not `$Rest) { Write-Host "Usage: Minecraft_server setdefault <profile>"; return }
        `$profileName   = `$Rest[0]
        `$profileConfig = Join-Path `$MCScriptFolder "Mcmods_server_`$profileName.json"
        if (-not (Test-Path `$profileConfig)) {
            Write-Host "No server profile config found for '`$profileName' (expected `$profileConfig)."
            return
        }
        Set-MCAutomationValue -Key "DefaultServerProfile" -Value `$profileName
        Write-Host "Default server profile set to `$profileName"
        return
    }

    if (`$Command -eq "readme") {
        Invoke-Item (Join-Path `$MCScriptFolder "README_Server.md")
        return
    }

    if (`$Command -in "help", "--help", "-h") {
        python (Join-Path `$MCScriptFolder "Mcmods_server.py") help
        return
    }

    `$promptText = if (`$default) { "Which server profile? [default: `$default]" } else { "Which server profile?" }
    `$choice = Read-Host `$promptText
    if (-not `$choice -and `$default) { `$choice = `$default }

    if (-not `$choice) {
        Write-Host "No server profile given."
        return
    }

    `$script        = Join-Path `$MCScriptFolder "Mcmods_server.py"
    `$profileConfig = Join-Path `$MCScriptFolder "Mcmods_server_`$choice.json"
    if (-not (Test-Path `$profileConfig) -and `$Command -ne "init") {
        Write-Host "No server profile config found for '`$choice' (expected `$profileConfig)."
        `$available = Get-MCAvailableProfiles -Prefix "Mcmods_server_"
        if (`$available) { Write-Host "Available profiles: `$(`$available -join ', ')" }
        Write-Host "Run 'python ``"`$script``" `$choice init' to create it, or check for typos."
        return
    }

    python `$script `$choice `$Command @Rest
}
$MarkerEnd
"@

Install-MCBlock -MarkerBegin $MarkerBegin -MarkerEnd $MarkerEnd -Block $block -Label "Minecraft/Minecraft_server"

if ($installBackup) {
    $BackupMarkerBegin = "# >>> Mcmods Backup PowerShell functions (added by Install-PowerShellIntegration.ps1) >>>"
    $BackupMarkerEnd   = "# <<< Mcmods Backup PowerShell functions <<<"

    $backupBlock = @"
$BackupMarkerBegin
# Folder containing Backup_Automation.json. Detected automatically when this was
# installed ($ScriptsFolder) - re-run Install-PowerShellIntegration.ps1 -Force from the
# new location if you move the scripts folder later.
`$MCBackupScriptFolder = "$ScriptsFolder"
`$MCBackupFile         = Join-Path `$MCBackupScriptFolder "Backup_Automation.json"

`$MCZipPresets = [ordered]@{
    "1" = @{ Name = "Windows default (fast, standard compression)"; Args = "-mx5" }
    "2" = @{ Name = "High efficiency (max compression, high resource usage)"; Args = "-mx9 -m0=LZMA2 -md=256m -mfb=64 -ms=16g -mmt=20 -mmemuse=80%" }
    "3" = @{ Name = "High efficiency, lower resource usage (default)"; Args = "-mx9 -m0=LZMA2 -md=64m -mfb=32 -ms=2g -mmt=4 -mmemuse=50%" }
}

function Get-MCBackupConfig {
    if (-not (Test-Path `$MCBackupFile)) { return [pscustomobject]@{ BackupJobs = @() } }
    `$content = Get-Content `$MCBackupFile -Raw
    if ([string]::IsNullOrWhiteSpace(`$content)) { return [pscustomobject]@{ BackupJobs = @() } }
    `$cfg = `$content | ConvertFrom-Json
    if (-not (`$cfg.PSObject.Properties.Name -contains "BackupJobs")) {
        `$cfg | Add-Member -NotePropertyName BackupJobs -NotePropertyValue @() -Force
    }
    return `$cfg
}

function Save-MCBackupConfig {
    param(`$Config)
    `$Config | ConvertTo-Json -Depth 6 | Set-Content `$MCBackupFile -Encoding UTF8
}

function Read-MCBackupPassword {
    param([string]`$Message)
    # Masked entry (no screen echo while typing), with an opt-in reveal afterward so you
    # can actually check what you typed before it's used - and a chance to re-enter if
    # the reveal shows a typo, rather than only finding out when 7-Zip fails later.
    while (`$true) {
        `$secure = Read-Host `$Message -AsSecureString
        `$bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR(`$secure)
        try {
            `$plain = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR(`$bstr)
        } finally {
            [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR(`$bstr)
        }

        `$reveal = Read-Host "Show password to confirm it's correct? Y/N"
        if (`$reveal -match '^[Yy]') {
            Write-Host "Password entered: `$plain" -ForegroundColor Yellow
            `$confirm = Read-Host "Is this correct? Y/N (N = re-enter)"
            if (`$confirm -match '^[Nn]') { continue }
        }

        return `$plain
    }
}

function Select-MCZipPreset {
    param([string]`$CurrentArgs)
    Write-Host "Compression preset:"
    foreach (`$key in `$MCZipPresets.Keys) {
        Write-Host "  `$key) `$(`$MCZipPresets[`$key].Name)"
    }
    Write-Host "  c) Custom 7-Zip arguments"
    `$sel = Read-Host "Choice [3]"
    if (-not `$sel) { `$sel = "3" }
    if (`$sel -eq "c") {
        `$suffix = if (`$CurrentArgs) { " [current: `$CurrentArgs]" } else { "" }
        `$custom = Read-Host "Custom 7-Zip arguments`$suffix"
        if (-not `$custom -and `$CurrentArgs) { `$custom = `$CurrentArgs }
        return [pscustomobject]@{ Preset = "custom"; Args = `$custom }
    }
    if (`$MCZipPresets.Contains(`$sel)) {
        return [pscustomobject]@{ Preset = `$sel; Args = `$MCZipPresets[`$sel].Args }
    }
    Write-Host "Unrecognized choice, using default (3)."
    return [pscustomobject]@{ Preset = "3"; Args = `$MCZipPresets["3"].Args }
}

function Select-MCBackupJobs {
    param([string]`$Query, [switch]`$Multiple)
    `$cfg     = Get-MCBackupConfig
    `$allJobs = @(`$cfg.BackupJobs)
    if (`$Query -eq "all") { return `$allJobs }
    `$found = @(`$allJobs | Where-Object { `$_.label -like "*`$Query*" })
    if (`$found.Count -eq 0) {
        Write-Host "No backup job label matches '`$Query'."
        if (`$allJobs) { Write-Host "Configured jobs: `$((`$allJobs | ForEach-Object { `$_.label }) -join ', ')" }
        return @()
    }
    if (`$found.Count -eq 1) { return `$found }
    Write-Host "Multiple backup jobs match '`$Query':"
    for (`$i = 0; `$i -lt `$found.Count; `$i++) {
        Write-Host "  `$(`$i + 1)) `$(`$found[`$i].label)  (`$(`$found[`$i].savesDir) -> `$(`$found[`$i].destDir))"
    }
    if (`$Multiple) { Write-Host "  a) All of the above" }
    `$sel = Read-Host "Choice"
    if (`$Multiple -and `$sel -eq "a") { return `$found }
    if (`$sel -match '^\d+`$' -and [int]`$sel -ge 1 -and [int]`$sel -le `$found.Count) {
        return @(`$found[[int]`$sel - 1])
    }
    Write-Host "Invalid choice, cancelled."
    return @()
}

function Minecraft_backup {
    param(
        [Parameter(Position = 0)]
        [string]`$Command,

        [Parameter(Position = 1, ValueFromRemainingArguments = `$true)]
        [string[]]`$Rest
    )

    if (-not `$Command) {
        Write-Host "Usage: Minecraft_backup <command> [args...]"
        Write-Host "Commands: list | add | edit <job> | remove <job> | run <job|all> [filter] | readme | help"
        return
    }

    if (`$Command -eq "readme") {
        Invoke-Item (Join-Path `$MCBackupScriptFolder "README_Backup.md")
        return
    }

    if (`$Command -in "help", "--help", "-h") {
        Write-Host "Minecraft_backup list                     - show configured backup jobs"
        Write-Host "Minecraft_backup add                      - set up a new backup job"
        Write-Host "Minecraft_backup edit <job>                - change an existing job"
        Write-Host "Minecraft_backup remove <job>               - delete a job (files on disk untouched)"
        Write-Host "Minecraft_backup run <job|all> [filter]   - run one/matching/all jobs; filter narrows which world folders are included"
        Write-Host "Minecraft_backup readme                   - open README_Backup.md"
        return
    }

    if (`$Command -eq "list") {
        `$cfg = Get-MCBackupConfig
        if (-not `$cfg.BackupJobs -or `$cfg.BackupJobs.Count -eq 0) {
            Write-Host "No backup jobs configured yet. Run 'Minecraft_backup add' to create one."
            return
        }
        foreach (`$job in `$cfg.BackupJobs) {
            `$encTag = if (`$job.encrypt) { "encrypted" } else { "not encrypted" }
            Write-Host "`$(`$job.label): `$(`$job.savesDir) -> `$(`$job.destDir) [`$(`$job.mode), `$encTag, preset `$(`$job.zipPreset)]"
        }
        return
    }

    if (`$Command -eq "add") {
        `$cfg = Get-MCBackupConfig
        `$label = Read-Host "Label for this backup job (short name, e.g. 'main')"
        if (-not `$label) { Write-Host "Cancelled - no label given."; return }
        if (@(`$cfg.BackupJobs) | Where-Object { `$_.label -eq `$label }) {
            Write-Host "A job named '`$label' already exists - use 'edit `$label' instead."
            return
        }
        `$savesDir = Read-Host "Saves directory to back up (folder containing world folders)"
        if (-not (Test-Path `$savesDir)) {
            Write-Host "That folder doesn't exist: `$savesDir"
            return
        }
        `$destDir = Read-Host "Destination directory for backups"
        `$mode = Read-Host "Mode: zip or copy [zip]"
        if (-not `$mode) { `$mode = "zip" }
        `$encryptAnswer = Read-Host "Encrypt zip backups with a password? [y/N]"
        `$encrypt = `$encryptAnswer -match '^(y|yes)`$'
        if (`$mode -eq "zip") {
            `$zipChoice = Select-MCZipPreset
        } else {
            `$zipChoice = [pscustomobject]@{ Preset = "3"; Args = `$MCZipPresets["3"].Args }
        }
        `$job = [pscustomobject]@{
            label     = `$label
            savesDir  = `$savesDir
            destDir   = `$destDir
            mode      = `$mode
            encrypt   = [bool]`$encrypt
            zipPreset = `$zipChoice.Preset
            zipArgs   = `$zipChoice.Args
        }
        `$cfg.BackupJobs = @(`$cfg.BackupJobs) + `$job
        Save-MCBackupConfig `$cfg
        Write-Host "Added backup job '`$label'."
        return
    }

    if (`$Command -eq "edit") {
        if (-not `$Rest) { Write-Host "Usage: Minecraft_backup edit <job>"; return }
        `$found = Select-MCBackupJobs -Query `$Rest[0]
        if (-not `$found) { return }
        `$job = `$found[0]
        `$cfg = Get-MCBackupConfig
        `$newSaves = Read-Host "Saves directory [current: `$(`$job.savesDir)]"
        if (`$newSaves) { `$job.savesDir = `$newSaves }
        `$newDest = Read-Host "Destination directory [current: `$(`$job.destDir)]"
        if (`$newDest) { `$job.destDir = `$newDest }
        `$newMode = Read-Host "Mode: zip or copy [current: `$(`$job.mode)]"
        if (`$newMode) { `$job.mode = `$newMode }
        `$curEnc = if (`$job.encrypt) { 'y' } else { 'n' }
        `$newEncrypt = Read-Host "Encrypt with a password? y/n [current: `$curEnc]"
        if (`$newEncrypt) { `$job.encrypt = `$newEncrypt -match '^(y|yes)`$' }
        if (`$job.mode -eq "zip") {
            `$changePreset = Read-Host "Change compression preset? [current: `$(`$job.zipPreset)] y/N"
            if (`$changePreset -match '^(y|yes)`$') {
                `$zipChoice = Select-MCZipPreset -CurrentArgs `$job.zipArgs
                `$job.zipPreset = `$zipChoice.Preset
                `$job.zipArgs   = `$zipChoice.Args
            }
        }
        `$label = `$job.label
        `$cfg.BackupJobs = @(`$cfg.BackupJobs | ForEach-Object { if (`$_.label -eq `$label) { `$job } else { `$_ } })
        Save-MCBackupConfig `$cfg
        Write-Host "Updated backup job '`$label'."
        return
    }

    if (`$Command -eq "remove") {
        if (-not `$Rest) { Write-Host "Usage: Minecraft_backup remove <job>"; return }
        `$found = Select-MCBackupJobs -Query `$Rest[0]
        if (-not `$found) { return }
        `$job = `$found[0]
        `$confirm = Read-Host "Remove backup job '`$(`$job.label)'? This only forgets the job, files on disk are untouched. [y/N]"
        if (`$confirm -notmatch '^(y|yes)`$') { Write-Host "Cancelled."; return }
        `$cfg = Get-MCBackupConfig
        `$cfg.BackupJobs = @(`$cfg.BackupJobs | Where-Object { `$_.label -ne `$job.label })
        Save-MCBackupConfig `$cfg
        Write-Host "Removed backup job '`$(`$job.label)'."
        return
    }

    if (`$Command -eq "run") {
        if (-not `$Rest) { Write-Host "Usage: Minecraft_backup run <job|all> [filter]"; return }
        `$query  = `$Rest[0]
        `$filter = if (`$Rest.Count -gt 1) { `$Rest[1] } else { `$null }
        `$jobs = Select-MCBackupJobs -Query `$query -Multiple
        if (-not `$jobs) { return }
        if (-not (Get-Command 7z -ErrorAction SilentlyContinue)) {
            Write-Host "7z was not found on PATH - install 7-Zip and make sure '7z' is available in a new terminal."
            return
        }
        foreach (`$job in `$jobs) {
            Write-Host "--- Backing up '`$(`$job.label)' ---"
            if (-not (Test-Path `$job.savesDir)) {
                Write-Host "Saves folder not found: `$(`$job.savesDir) - skipping."
                continue
            }
            `$worlds = Get-ChildItem -Path `$job.savesDir -Directory
            if (`$filter) { `$worlds = `$worlds | Where-Object { `$_.Name -like "*`$filter*" } }
            if (-not `$worlds) {
                Write-Host `$(if (`$filter) { "No worlds matching '`$filter' found." } else { "No world folders found in: `$(`$job.savesDir)" })
                continue
            }
            Write-Host "Found `$(`$worlds.Count) world(s): `$(`$worlds.Name -join ', ')"
            New-Item -ItemType Directory -Force -Path `$job.destDir | Out-Null

            if (`$job.mode -eq "zip") {
                `$stamp    = Get-Date -Format "dd.MM.yyyy HHmm"
                `$tag      = if (`$filter) { " (`$filter)" } else { "" }
                `$archive  = Join-Path `$job.destDir "`$(`$job.label)_Backup`$tag (`$stamp Uhr).7z"
                Write-Host "Creating archive: `$archive ..."
                `$paths   = `$worlds | ForEach-Object { `$_.FullName }
                `$argList = (`$job.zipArgs -split ' ') + @("a", `$archive) + `$paths
                `$pwd = `$null
                if (`$job.encrypt) {
                    `$pwd = Read-MCBackupPassword "Password for '`$(`$job.label)' backup"
                    `$argList += @("-p`$pwd", "-mhe=on")
                }
                & 7z @argList
                `$zipExit = `$LASTEXITCODE
                if (`$zipExit -ne 0) {
                    Write-Host "7-Zip failed with exit code `$zipExit"
                    `$pwd = `$null
                    continue
                }
                Write-Host "Testing archive ..."
                `$testArgs = @("t", `$archive)
                if (`$job.encrypt) { `$testArgs += "-p`$pwd" }
                & 7z @testArgs
                if (`$LASTEXITCODE -eq 0) { Write-Host "Done. Archive verified." } else { Write-Host "Verification failed with exit code `$LASTEXITCODE" }
                `$pwd = `$null
            } else {
                `$failed = @()
                foreach (`$world in `$worlds) {
                    `$dest = Join-Path `$job.destDir `$world.Name
                    Write-Host "Copying `$(`$world.Name) ..." -NoNewline
                    try {
                        Copy-Item -Path `$world.FullName -Destination `$dest -Recurse -Force -ErrorAction Stop
                        Write-Host "  OK"
                    } catch {
                        Write-Host "  FAILED: `$(`$_.Exception.Message)"
                        `$failed += `$world.Name
                    }
                }
                if (`$failed) {
                    Write-Host "Finished with errors. Failed: `$(`$failed -join ', ')"
                } else {
                    Write-Host "Done. `$(`$worlds.Count) world(s) copied to `$(`$job.destDir)"
                }
            }
        }
        return
    }

    Write-Host "Unknown command '`$Command'. Run 'Minecraft_backup help' for the list."
}
$BackupMarkerEnd
"@

    $BackupAutomationFile = Join-Path $ScriptsFolder "Backup_Automation.json"
    if (-not (Test-Path $BackupAutomationFile)) {
        @{ BackupJobs = @() } | ConvertTo-Json | Set-Content $BackupAutomationFile -Encoding UTF8
        Write-Host "Created $BackupAutomationFile"
    } else {
        Write-Host "Found existing $BackupAutomationFile - leaving it as-is."
    }

    Install-MCBlock -MarkerBegin $BackupMarkerBegin -MarkerEnd $BackupMarkerEnd -Block $backupBlock -Label "Minecraft_backup"
} else {
    Write-Host "Skipping the optional Minecraft_backup feature (re-run this installer with -IncludeBackup to add it later)."
}

Write-Host "Restart PowerShell, or run '. `$PROFILE', to start using them."
