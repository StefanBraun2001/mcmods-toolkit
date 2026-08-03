// ============================================================================
// Streamer.bot "Execute C# Code" action - triggers a Minecraft_backup run.
//
// REQUIRES: PowerShell 7+ (pwsh.exe) installed and on PATH - the "$PROFILE"
// this relies on is the PowerShell 7+ one (Documents\PowerShell\...), not the
// older Windows PowerShell 5.1 one, so this must run via pwsh.exe specifically.
//
// HOW TO USE:
//   1. In Streamer.bot: Actions -> New Action -> add sub-action "Execute C# Code".
//   2. In the code editor, SELECT ALL of whatever is already there (including
//      Streamer.bot's own default template) and DELETE it first.
//   3. Paste this ENTIRE file (including the "public class CPHInline" part)
//      into the now-empty editor, as a full replacement - not alongside or
//      inside any leftover default text.
//   4. Click the "Find refs" button in the code editor and add a reference
//      for System.Diagnostics.Process - without this, ProcessStartInfo/Process
//      fail to resolve even though the "using System.Diagnostics;" is there,
//      since a using directive alone doesn't add the assembly reference.
//   5. Edit the two constants below for what this particular button/action
//      should back up.
//   6. Map the action to your Stream Deck button / Streamer.bot trigger.
//
// TO DUPLICATE FOR ANOTHER JOB/WORLD:
//   Create another "Execute C# Code" action, clear its editor the same way,
//   paste this same file again, click "Find refs" there too, and just change
//   WorldName / JobQuery for that one. Nothing else needs editing.
//
// EXIT CODE CONTRACT:
//   "Minecraft_backup run" sets $LASTEXITCODE itself (0 on success, 1 if any job
//   failed or nothing matched anywhere) - it never calls PowerShell's "exit", since
//   it's also used interactively and that would close the caller's terminal. The
//   command string below appends "; exit $LASTEXITCODE" so THIS disposable pwsh.exe
//   process (and only this one - see README_Backup.md) exits with that code, which
//   Process.ExitCode below then reads. Failure detection is just exitCode != 0.
// ============================================================================

using System;
using System.Diagnostics;

public class CPHInline
{
    // ==================== EDIT THESE FOR EACH DUPLICATE ====================

    // The world/save folder name to back up (matched as a substring, same as
    // typing it manually: Minecraft_backup run <JobQuery> "<WorldName>").
    const string WorldName = "UHC for Stream";

    // Which backup job(s) to run against: "all", or one job label (e.g. "Main").
    const string JobQuery = "all";

    // =========================================================================

    public bool Execute()
    {
        // Verify PowerShell 7+ (pwsh.exe) is actually available before attempting
        // anything - this whole feature relies on it (see REQUIRES note at top).
        if (!TryGetPwshMajorVersion(out int psMajorVersion))
        {
            CPH.LogError("[Minecraft_backup] PowerShell 7+ (pwsh.exe) was not found on PATH. Install it with: winget install --id Microsoft.PowerShell --source winget");
            return false;
        }
        if (psMajorVersion < 7)
        {
            CPH.LogError($"[Minecraft_backup] Found pwsh.exe, but it reports PowerShell {psMajorVersion} - PowerShell 7 or newer is required.");
            return false;
        }

        string escapedWorld = WorldName.Replace("'", "''");
        string escapedJob   = JobQuery.Replace("'", "''");

        // The trailing "; exit $LASTEXITCODE" only terminates this one disposable pwsh.exe
        // process that Process.Start() below launches - it has no effect on any other
        // PowerShell window or script, interactive or not (see EXIT CODE CONTRACT above).
        string command = $". $PROFILE; Minecraft_backup run '{escapedJob}' '{escapedWorld}'; exit $LASTEXITCODE";

        var psi = new ProcessStartInfo
        {
            // Must be "pwsh.exe" (PowerShell 7+), not "powershell.exe" (Windows
            // PowerShell 5.1) - $PROFILE resolves to a different, unrelated file
            // under 5.1, so Minecraft_backup wouldn't be defined there even
            // though the profile line below looks correct. Requires PowerShell 7+
            // to be installed and "pwsh" on PATH.
            FileName               = "pwsh.exe",
            Arguments              = $"-NoProfile -ExecutionPolicy Bypass -Command \"{command}\"",
            UseShellExecute        = false,
            RedirectStandardOutput = true,
            RedirectStandardError  = true,
            CreateNoWindow         = true
        };

        string output = "";
        string errOut = "";
        int exitCode = -1;

        try
        {
            using (var proc = Process.Start(psi))
            {
                output = proc.StandardOutput.ReadToEnd();
                errOut = proc.StandardError.ReadToEnd();
                proc.WaitForExit();
                exitCode = proc.ExitCode;
            }
        }
        catch (Exception ex)
        {
            CPH.LogError($"[Minecraft_backup] Failed to launch pwsh.exe (is PowerShell 7+ installed and on PATH?): {ex.Message}");
            // TODO: hook up your failure action here too, e.g. CPH.PlaySound(@"C:\path\to\error.wav");
            return false;
        }

        // Minecraft_backup run's exit code already accounts for per-job failures (bad
        // saves folder, 7-Zip creation/verification errors, copy errors) AND the "nothing
        // backed up anywhere" case (e.g. a WorldName typo matching zero worlds in every
        // job) - see EXIT CODE CONTRACT at the top of this file. A single job having no
        // matching worlds while others succeed is NOT treated as a failure by the
        // PowerShell side, same as before. Non-empty stderr is kept as a cheap second
        // signal in case something writes there without going through $LASTEXITCODE
        // (e.g. an unrelated PowerShell warning/error unrelated to the backup itself).
        bool looksFailed = exitCode != 0 || !string.IsNullOrWhiteSpace(errOut);

        if (looksFailed)
        {
            CPH.LogError($"[Minecraft_backup] Backup FAILED for '{WorldName}' (job: {JobQuery}). Exit code: {exitCode}\n--- output ---\n{output}\n--- stderr ---\n{errOut}");

            // TODO: trigger your failure feedback here, e.g.:
            // CPH.PlaySound(@"C:\path\to\error.wav");
            // CPH.TriggerCodeEvent("MinecraftBackupFailed");
        }
        else
        {
            CPH.LogInfo($"[Minecraft_backup] Backup OK for '{WorldName}' (job: {JobQuery}).");

            // Optional: hook up a success sound/event the same way if you want one.
            // CPH.PlaySound(@"C:\path\to\success.wav");
        }

        return true;
    }

    private bool TryGetPwshMajorVersion(out int majorVersion)
    {
        majorVersion = 0;
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName               = "pwsh.exe",
                Arguments              = "-NoProfile -Command \"$PSVersionTable.PSVersion.Major\"",
                UseShellExecute        = false,
                RedirectStandardOutput = true,
                CreateNoWindow         = true
            };
            using (var proc = Process.Start(psi))
            {
                string result = proc.StandardOutput.ReadToEnd().Trim();
                proc.WaitForExit();
                return proc.ExitCode == 0 && int.TryParse(result, out majorVersion);
            }
        }
        catch
        {
            return false;
        }
    }
}
