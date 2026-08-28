# PictureWeb watchdog · 30s 一次,死了拉起
# 跟 start_forever.bat 一起用
# 双击停止:taskkill /F /IM powershell.exe /FI "WINDOWTITLE eq PictureWeb-Watchdog*"

$ErrorActionPreference = 'SilentlyContinue'
$port = 9004
$logDir = "D:\Mac\Mac\Mac\workteam\05_space\03_architect\Mobile\_ArchitectMobileLib\PictureWeb\logs"
$logFile = "$logDir\watchdog.log"
$py = "C:\Users\yongzhang\AppData\Local\Programs\Python\Python312\python.exe"
$workDir = "D:\Mac\Mac\Mac\workteam\05_space\03_architect\Mobile\_ArchitectMobileLib\PictureWeb"

function Log($msg) {
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    "$ts  $msg" | Out-File -Append -FilePath $logFile -Encoding utf8
}

function IsAlive {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $conn
}

function StartServer {
    Log 'server DOWN, restarting...'
    Set-Location $workDir
    $env:PICTUREWEB_TEST_PORT = "$port"
    $env:PYTHONIOENCODING = "utf-8"
    Start-Process -FilePath $py `
        -ArgumentList "-X","utf8","server.py" `
        -WorkingDirectory $workDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput "$logDir\server.out.log" `
        -RedirectStandardError "$logDir\server.err.log"
    Start-Sleep -Seconds 3
    if (IsAlive) { Log 'server UP after restart' } else { Log 'server STILL DOWN after restart' }
}

# 主循环
Log 'watchdog started, monitoring port 9004'
$failStreak = 0
while ($true) {
    if (IsAlive) {
        if ($failStreak -gt 0) { Log "recovered (was down $failStreak checks)" }
        $failStreak = 0
    } else {
        $failStreak++
        Log "port $port NOT listening (fail #$failStreak)"
        if ($failStreak -ge 2) {
            StartServer
            $failStreak = 0
        }
    }
    Start-Sleep -Seconds 30
}
