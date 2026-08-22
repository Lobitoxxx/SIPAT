<#>
.SYNOPSIS
    Arranca los 3 servicios SIPAT: OSRM (Docker), API FastAPI, Streamlit Dashboard.
.DESCRIPTION
    Verifica puertos, levanta lo que falte. Espera health checks.
#>
param(
    [switch]$SoloVerificar
)

$ROOT = "D:\Proyects\2. Analítica con Big Data\SIPAT"
$LOG_DIR = "$ROOT\data\processed\dashboard"
$ErrorActionPreference = "Continue"

function Test-Port($port) {
    try { $tcp = [System.Net.Sockets.TcpClient]::new(); $tcp.Connect("localhost", $port); $tcp.Close(); return $true }
    catch { return $false }
}

function Start-OSRM {
    Write-Host "[OSRM] Verificando Docker Desktop..."
    $dock = Start-Process -FilePath "docker" -ArgumentList "info" -NoNewWindow -RedirectStandardOutput "$LOG_DIR\docker_info.log" -RedirectStandardError "$LOG_DIR\docker_info.err.log" -PassThru -Wait
    if ($dock.ExitCode -ne 0) {
        Write-Host "[OSRM] Iniciando Docker Desktop..."
        Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" -WindowStyle Minimized
        for ($i=0; $i -lt 24; $i++) {
            Start-Sleep 5
            $dock = Start-Process -FilePath "docker" -ArgumentList "info" -NoNewWindow -RedirectStandardOutput "$LOG_DIR\docker_info.log" -RedirectStandardError "$LOG_DIR\docker_info.err.log" -PassThru -Wait
            if ($dock.ExitCode -eq 0) { Write-Host "[OSRM] Docker listo"; break }
        }
        if ($dock.ExitCode -ne 0) { Write-Error "[OSRM] Docker no arrancó"; return $false }
    }
    Write-Host "[OSRM] Arrancando osrm-routed via osrm_build.py --serve en :5000..."
    $osrm = Start-Process -FilePath "python" -ArgumentList "osrm_build.py","--serve" -WorkingDirectory "$ROOT\scripts" -WindowStyle Hidden -RedirectStandardOutput "$LOG_DIR\osrm_stdout.log" -RedirectStandardError "$LOG_DIR\osrm_stderr.log" -PassThru
    for ($i=0; $i -lt 30; $i++) {
        Start-Sleep 2
        if (Test-Port 5000) { Write-Host "[OSRM] UP en :5000"; return $true }
    }
    Write-Error "[OSRM] Timeout esperando puerto 5000"
    return $false
}

function Start-API {
    Write-Host "[API] Arrancando FastAPI en :8000..."
    $api = Start-Process -FilePath "python" -ArgumentList "-m","uvicorn","api.app:app","--host","0.0.0.0","--port","8000" -WorkingDirectory "$ROOT" -WindowStyle Hidden -RedirectStandardOutput "$LOG_DIR\api_stdout.log" -RedirectStandardError "$LOG_DIR\api_stderr.log" -PassThru
    for ($i=0; $i -lt 30; $i++) {
        Start-Sleep 1
        if (Test-Port 8000) {
            try {
                $h = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
                Write-Host "[API] UP en :8000 (puntos=$($h.puntos_riesgo) uptime=$($h.uptime_s)s)"
                return $true
            } catch { }
        }
    }
    Write-Error "[API] Timeout o health check falló"
    Get-Content "$LOG_DIR\api_stderr.log" -Tail 10 -ErrorAction SilentlyContinue
    return $false
}

function Start-Streamlit {
    Write-Host "[DASH] Arrancando Streamlit en :8501..."
    $dash = Start-Process -FilePath "python" -ArgumentList "-m","streamlit","run","dashboard/app.py","--server.port","8501","--server.headless","true" -WorkingDirectory "$ROOT" -WindowStyle Hidden -RedirectStandardOutput "$LOG_DIR\dash_stdout.log" -RedirectStandardError "$LOG_DIR\dash_stderr.log" -PassThru
    for ($i=0; $i -lt 30; $i++) {
        Start-Sleep 2
        if (Test-Port 8501) {
            Write-Host "[DASH] UP en :8501"
            return $true
        }
    }
    Write-Error "[DASH] Timeout esperando puerto 8501"
    return $false
}

# MAIN
$all_ok = $true
$ports = @{5000="OSRM"; 8000="API"; 8501="Streamlit"}
foreach ($port in $ports.Keys) {
    $name = $ports[$port]
    if (Test-Port $port) { Write-Host "[$name] Ya UP en :$port" }
    else {
        if ($SoloVerificar) { Write-Host "[$name] DOWN (solo verificar)"; $all_ok = $false }
        else {
            switch ($port) {
                5000 { $all_ok = $all_ok -and (Start-OSRM) }
                8000 { $all_ok = $all_ok -and (Start-API) }
                8501 { $all_ok = $all_ok -and (Start-Streamlit) }
            }
        }
    }
}

if ($all_ok) { Write-Host "`n[OK] Todos los servicios UP"; exit 0 }
else { Write-Error "`n[FAIL] Algunos servicios no arrancaron"; exit 1 }