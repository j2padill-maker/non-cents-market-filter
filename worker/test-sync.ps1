# Diagnoses the watchlist sync Worker end to end and prints a plain verdict.
# Run with:  powershell -ExecutionPolicy Bypass -File C:\non-cents\worker\test-sync.ps1

$ErrorActionPreference = 'Stop'
$base = 'https://noncents-sync.j2padill.workers.dev'

function Line { Write-Host ('-' * 62) }

Write-Host ''
Write-Host 'NON-CENTS SYNC DIAGNOSTIC'
Line

# ---------------------------------------------------------------- 1. /health
Write-Host '1. Checking the Worker is up (/health)...'
$healthRaw = $null
try {
    $healthRaw = Invoke-RestMethod -Uri "$base/health" -TimeoutSec 20
    Write-Host '   Worker responded.'
    Write-Host "   Raw: $($healthRaw | ConvertTo-Json -Compress)"
} catch {
    Write-Host '   FAILED - could not reach the Worker at all.' -ForegroundColor Red
    Write-Host "   $($_.Exception.Message)"
    Write-Host ''
    Write-Host 'VERDICT: The Worker URL is wrong or the Worker is not deployed.'
    exit 1
}

# The updated Worker reports its own wiring. The old one only says ok:true.
$hasDiag = $healthRaw.PSObject.Properties.Name -contains 'kvBound'
if ($hasDiag) {
    Write-Host ''
    Write-Host "   KV binding present : $($healthRaw.kvBound)"
    Write-Host "   SYNC_KEY secret set: $($healthRaw.secretSet)"
    if (-not $healthRaw.kvBound) {
        Write-Host ''
        Write-Host 'VERDICT: The KV namespace is NOT bound.' -ForegroundColor Yellow
        Write-Host '  Fix: Cloudflare -> your Worker -> Bindings tab -> Add binding'
        Write-Host '       -> KV namespace -> Variable name: WATCHLIST_KV'
        Write-Host '       -> KV namespace: NONCENTS_WATCHLIST -> Deploy'
        exit 1
    }
} else {
    Write-Host '   (Older Worker code - it cannot self-report its bindings.)'
}

# ------------------------------------------------------------- 2. /watchlist
Line
Write-Host '2. Now testing with your sync key.'
Write-Host '   Paste the key and press Enter (it will not be echoed).'
Write-Host ''
$secure = Read-Host -AsSecureString '   Sync key'
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
$key = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

if ([string]::IsNullOrWhiteSpace($key)) {
    Write-Host ''
    Write-Host 'No key entered - stopping.' -ForegroundColor Yellow
    exit 1
}
Write-Host ''
Write-Host "   Key length received: $($key.Length) characters"

try {
    $r = Invoke-RestMethod -Uri "$base/watchlist" -Headers @{ 'X-Sync-Key' = $key } -TimeoutSec 20
    Line
    Write-Host 'SUCCESS - the Worker is fully working.' -ForegroundColor Green
    Write-Host ''
    Write-Host "  Revision : $($r.rev)"
    Write-Host "  Updated  : $($r.updated)"
    Write-Host "  Lists    : $($r.lists.Count)"
    foreach ($l in $r.lists) {
        Write-Host "    - $($l.name): $($l.tickers -join ', ')"
    }
    Write-Host ''
    Write-Host 'VERDICT: Worker and key are both correct.'
    Write-Host '  If the website still shows a sync error, the problem is in the'
    Write-Host '  browser - most likely a cached old version of the app.'
    Write-Host '  Fix: open the site and press Ctrl+Shift+R to hard-refresh.'
    exit 0
} catch {
    $code = $null
    if ($_.Exception.Response) { $code = $_.Exception.Response.StatusCode.value__ }
    Line
    Write-Host "FAILED - HTTP $code" -ForegroundColor Red
    if ($_.ErrorDetails.Message) { Write-Host "  Body: $($_.ErrorDetails.Message)" }
    Write-Host ''
    switch ($code) {
        401 {
            Write-Host 'VERDICT: The key you just typed does not match the SYNC_KEY'
            Write-Host '  secret stored in Cloudflare.'
            Write-Host '  Fix: Cloudflare -> Worker -> Settings -> Runtime variables'
            Write-Host '       and secrets -> delete SYNC_KEY, add it again with a key'
            Write-Host '       you have saved, then Deploy. Watch for stray spaces.'
        }
        500 {
            Write-Host 'VERDICT: The Worker threw an exception. Two likely causes:'
            Write-Host ''
            Write-Host '  a) The KV namespace is not bound. Check Cloudflare ->'
            Write-Host '     Worker -> Bindings tab. You should see WATCHLIST_KV'
            Write-Host '     connected to a KV namespace.'
            Write-Host ''
            Write-Host '  b) The deployed code is out of date. Re-paste'
            Write-Host '     C:\non-cents\worker\watchlist-worker.js into the'
            Write-Host '     Cloudflare editor and Deploy.'
            Write-Host ''
            Write-Host '  If the binding IS present, it is (b) - redeploy first.'
            Write-Host '  Cloudflare -> Worker -> Logs will show the real exception.'
        }
        404 {
            Write-Host 'VERDICT: Route not found - the deployed code is not the'
            Write-Host '  watchlist Worker. Re-paste watchlist-worker.js and Deploy.'
        }
        default {
            Write-Host 'VERDICT: Unexpected response. Send this whole output over.'
        }
    }
    exit 1
}
