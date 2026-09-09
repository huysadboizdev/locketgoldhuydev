# ==============================================================================
# Script Khoi dong moi truong Development Locket Gold (Backend + Frontend)
# ==============================================================================
$ErrorActionPreference = "Stop"

# Duong dan tuong doi dong theo vi tri cua thu muc scripts
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$BackendLog = Join-Path $BackendDir "backend_dev.log"
$HealthUrl = "http://127.0.0.1:5001/api/site-settings"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  KHOI DONG MOI TRUONG DEVELOPMENT LOCKET GOLD HUY DEV    " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Project Root : $ProjectRoot" -ForegroundColor Gray
Write-Host "  Backend Dir  : $BackendDir" -ForegroundColor Gray
Write-Host "  Frontend Dir : $FrontendDir" -ForegroundColor Gray
Write-Host "----------------------------------------------------------" -ForegroundColor Gray

# 1. Kiem tra file ma nguon va moi truong
Write-Host "[1/4] Kiem tra file ma nguon va moi truong..." -ForegroundColor Yellow

if (-not (Test-Path (Join-Path $BackendDir "wsgi.py"))) {
    Write-Host "[LOI] Khong tim thay file backend\wsgi.py tai $BackendDir." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $FrontendDir "package.json"))) {
    Write-Host "[LOI] Khong tim thay file frontend\package.json tai $FrontendDir." -ForegroundColor Red
    exit 1
}

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "[LOI] Khong tim thay python trong PATH. Vui long cai dat Python >= 3.9." -ForegroundColor Red
    exit 1
}

$npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npmCmd) {
    Write-Host "[LOI] Khong tim thay npm.cmd trong PATH. Vui long cai dat Node.js." -ForegroundColor Red
    exit 1
}

# 2. Kiem tra port 5001
Write-Host "[2/4] Kiem tra trang thai cong 5001..." -ForegroundColor Yellow
$BackendManaged = $false
$BackendProc = $null
$BackendListenerProcessId = $null

$portOccupied = $false
try {
    $conns = Get-NetTCPConnection -LocalPort 5001 -State Listen -ErrorAction SilentlyContinue
    if ($conns) {
        $portOccupied = $true
        $BackendListenerProcessId = ($conns | Select-Object -First 1).OwningProcess
    }
} catch {
    # Some Windows sessions deny Get-NetTCPConnection even though netstat is
    # available. The fallback below handles both access-denied and empty output.
}

if (-not $portOccupied) {
    $netstatMatch = netstat -ano | Select-String ":5001\s+.*LISTENING"
    if ($netstatMatch) {
        $portOccupied = $true
        if ($netstatMatch[0].Line -match "LISTENING\s+(\d+)\s*$") {
            $BackendListenerProcessId = [int]$Matches[1]
        }
    }
}

if ($portOccupied) {
    try {
        $res = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 3 -ErrorAction Stop
        if ($res.success -ne $true) {
            throw "Phan hoi khong hop le"
        }

        # A healthy endpoint alone is not enough: an old Flask process can be
        # alive while missing routes from newly edited source code. Probe every
        # feature contract that the current admin UI requires. OPTIONS avoids
        # changing data and does not require an authenticated admin session.
        $requiredRouteProbeUrls = @(
            "http://127.0.0.1:5001/api/admin/payments/0/manual-confirm",
            "http://127.0.0.1:5001/api/admin/coupons",
            "http://127.0.0.1:5001/api/admin/site-settings"
        )
        foreach ($routeProbeUrl in $requiredRouteProbeUrls) {
            $routeProbe = Invoke-WebRequest -Uri $routeProbeUrl -Method Options -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
            if ($routeProbe.StatusCode -ne 200) {
                throw "Backend dang chay nhung thieu route: $routeProbeUrl"
            }
        }

        Write-Host "  -> Backend hop le va dung contract hien tai tai http://127.0.0.1:5001." -ForegroundColor Green
        $BackendManaged = $false
    } catch {
        if ($BackendListenerProcessId) {
            Write-Host "  -> Backend cu/khong hop le (PID $BackendListenerProcessId). Dang khoi dong lai..." -ForegroundColor Yellow
            try {
                Stop-Process -Id $BackendListenerProcessId -Force -ErrorAction Stop
                Start-Sleep -Milliseconds 500
                $portOccupied = $false
            } catch {
                Write-Host "  -> [LOI] Khong the dung backend cu PID $BackendListenerProcessId." -ForegroundColor Red
                Write-Host "  Hay mo PowerShell bang quyen phu hop, dung tien trinh nay va chay lai script." -ForegroundColor Red
                exit 1
            }
        } else {
            Write-Host "  -> [LOI] Cong 5001 dang bi chiem boi backend cu/khong hop le." -ForegroundColor Red
            exit 1
        }
    }
}

if (-not $portOccupied) {
    # 3. Khoi dong Backend
    Write-Host "[3/4] Khoi dong Backend Flask tai 127.0.0.1:5001..." -ForegroundColor Yellow
    if (Test-Path $BackendLog) {
        Remove-Item $BackendLog -Force -ErrorAction SilentlyContinue
    }

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = "python"
    $startInfo.Arguments = "wsgi.py"
    $startInfo.WorkingDirectory = $BackendDir
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true

    $BackendProc = [System.Diagnostics.Process]::Start($startInfo)
    $BackendManaged = $true

    # Ghi log ra file
    $outJob = Register-ObjectEvent -InputObject $BackendProc -EventName OutputDataReceived -Action {
        if ($EventArgs.Data) { Add-Content -Path $using:BackendLog -Value $EventArgs.Data }
    }
    $errJob = Register-ObjectEvent -InputObject $BackendProc -EventName ErrorDataReceived -Action {
        if ($EventArgs.Data) { Add-Content -Path $using:BackendLog -Value $EventArgs.Data }
    }
    $BackendProc.BeginOutputReadLine()
    $BackendProc.BeginErrorReadLine()

    # Cho Health Check
    Write-Host "  -> Dang cho Backend san sang" -NoNewline
    $ready = $false
    $elapsed = 0
    while ($elapsed -lt 15) {
        Start-Sleep -Milliseconds 500
        $elapsed += 0.5

        if ($BackendProc.HasExited) {
            Write-Host "`n[LOI] Tien trinh Backend da thoat dot ngot (ExitCode: $($BackendProc.ExitCode))." -ForegroundColor Red
            if (Test-Path $BackendLog) {
                Write-Host "--- LOG BACKEND ---" -ForegroundColor Red
                Get-Content $BackendLog | ForEach-Object { Write-Host $_ -ForegroundColor Red }
                Write-Host "-------------------" -ForegroundColor Red
            }
            exit 1
        }

        try {
            $check = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 2 -ErrorAction Stop
            if ($check.success -eq $true) {
                $ready = $true
                break
            }
        } catch {
            Write-Host "." -NoNewline
        }
    }

    if (-not $ready) {
        Write-Host "`n[LOI] Het thoi gian cho (15s) nhung Backend chua phan hoi tai $HealthUrl." -ForegroundColor Red
        if (Test-Path $BackendLog) {
            Write-Host "--- LOG BACKEND ---" -ForegroundColor Red
            Get-Content $BackendLog | ForEach-Object { Write-Host $_ -ForegroundColor Red }
        }
        if ($BackendProc -and -not $BackendProc.HasExited) {
            $BackendProc.Kill()
        }
        exit 1
    }

    Write-Host "`n  -> [OK] Backend da khoi dong thanh cong va san sang phuc vu API!" -ForegroundColor Green
}

# 4. Khoi dong Frontend
Write-Host "[4/4] Khoi dong Frontend Vite tai http://localhost:3000..." -ForegroundColor Cyan
Write-Host "  -> Nhan [Ctrl+C] de dung an toan ca 2 tien trinh." -ForegroundColor Gray

try {
    Push-Location $FrontendDir
    & npm.cmd run dev
} finally {
    Pop-Location
    Write-Host "`n[DON DEP] Dang dung moi truong development..." -ForegroundColor Yellow

    if ($BackendManaged -and $BackendProc -and -not $BackendProc.HasExited) {
        Write-Host "  -> Dang tat tien trinh Backend Flask (PID: $($BackendProc.Id))..." -ForegroundColor Gray
        try {
            cmd.exe /c "taskkill /F /T /PID $($BackendProc.Id)" 2>$null | Out-Null
            $BackendProc.WaitForExit(3000)
        } catch {
            $BackendProc.Kill()
        }
    }

    if ($outJob) { Unregister-Event -SourceIdentifier $outJob.Name -ErrorAction SilentlyContinue }
    if ($errJob) { Unregister-Event -SourceIdentifier $errJob.Name -ErrorAction SilentlyContinue }

    Write-Host "  -> [HOAN TAT] Moi truong development da dung sach se." -ForegroundColor Green
}
