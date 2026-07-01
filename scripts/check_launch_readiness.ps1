# Launch readiness check
$backend = "http://127.0.0.1:8000"
$frontend = "http://localhost:4101"
$results = @()

function Check($name, $url, $expectAuth) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
        $results += "[PASS] $name : HTTP $($r.StatusCode)"
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        if ($expectAuth -and $code -eq 401) {
            $results += "[PASS] $name : HTTP 401 (auth required as expected)"
        } elseif ($code -eq 401) {
            $results += "[WARN] $name : HTTP 401 (needs auth token)"
        } else {
            $results += "[FAIL] $name : $($_.Exception.Message)"
        }
    }
}

Check "Backend /api/health" "$backend/api/health" $false
Check "Frontend /dashboard" "$frontend/dashboard" $false
Check "Backend /api/stocks/002415" "$backend/api/stocks/002415" $true
Check "Backend /api/stocks/600519" "$backend/api/stocks/600519" $true
Check "Backend /api/backtest/meta" "$backend/api/backtest/meta?market=A_SHARE" $true

$results | ForEach-Object { Write-Host $_ }
$pass = ($results | Where-Object { $_ -match "PASS" }).Count
$fail = ($results | Where-Object { $_ -match "FAIL" }).Count
Write-Host "`nTotal: PASS=$pass FAIL=$fail"
if ($fail -gt 0) { exit 1 } else { exit 0 }
