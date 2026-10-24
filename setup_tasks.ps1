# Non-Cents scheduled task setup. Safe to re-run any time.
# Run from an ADMINISTRATOR PowerShell:
#   powershell -ExecutionPolicy Bypass -File C:\non-cents\setup_tasks.ps1
#
# Result:
#   NonCentsUpdate   - the normal 4:30 PM run (left as is; battery limits removed)
#   NonCentsCatchup  - runs 3 min after you log in, then every hour. It only does
#                      real work when the 4:30 PM update was missed, so turning
#                      the laptop on the next morning picks the update back up.

$ErrorActionPreference = 'Stop'
$repo = 'C:\non-cents'
$name = 'NonCentsCatchup'
$user = "$env:USERDOMAIN\$env:USERNAME"

# 1. Remove any older catch-up task created under a different name
Get-ScheduledTask | Where-Object {
    $_.TaskName -ne $name -and
    (($_.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join ' ') -match 'catchup_update'
} | ForEach-Object {
    Write-Host "Replacing old catch-up task: $($_.TaskPath)$($_.TaskName)"
    Unregister-ScheduledTask -TaskName $_.TaskName -TaskPath $_.TaskPath -Confirm:$false
}

# 2. Create the catch-up task
# conhost --headless runs the .bat with no visible window (Windows 10 1809+ / 11)
$action = New-ScheduledTaskAction -Execute "conhost.exe" -Argument "--headless `"$repo\catchup_update.bat`"" -WorkingDirectory $repo

$atLogon = New-ScheduledTaskTrigger -AtLogOn -User $user
$atLogon.Delay = 'PT3M'     # give Wi-Fi a few minutes to connect

$hourly = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Hours 1)

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $name -Action $action -Trigger $atLogon, $hourly `
    -Settings $settings -Principal $principal -Force | Out-Null
Write-Host "OK: $name created (at logon + every hour)"

# 3. Let the regular 4:30 PM task run on battery power too.
#    StartWhenAvailable stays OFF here on purpose: the catch-up task handles
#    missed runs, and having both fire at boot could start two updates at once.
$t = Get-ScheduledTask -TaskName 'NonCentsUpdate' -ErrorAction SilentlyContinue
if ($t) {
    $t.Settings.DisallowStartIfOnBatteries = $false
    $t.Settings.StopIfGoingOnBatteries = $false
    $t.Settings.StartWhenAvailable = $false
    try {
        Set-ScheduledTask -InputObject $t | Out-Null
        Write-Host "OK: NonCentsUpdate can now run on battery"
    } catch {
        Write-Host "WARNING: could not update NonCentsUpdate settings: $($_.Exception.Message)"
    }
} else {
    Write-Host "NOTE: no NonCentsUpdate task found on this laptop (catch-up will still cover it)"
}

# 4. Show the result
Write-Host ""
Get-ScheduledTask -TaskName 'NonCents*' | ForEach-Object {
    $i = $_ | Get-ScheduledTaskInfo
    [pscustomobject]@{
        Task       = $_.TaskName
        State      = $_.State
        LastRun    = $i.LastRunTime
        LastResult = $i.LastTaskResult
        NextRun    = $i.NextRunTime
    }
} | Format-Table -AutoSize
