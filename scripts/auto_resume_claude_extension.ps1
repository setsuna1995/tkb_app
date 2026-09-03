<#
.SYNOPSIS
    Script hen gio tu dong focus vao Antigravity IDE / VS Code va gui prompt tiep tuc.
#>

param(
    [string]$At = "",
    [int]$Hours = 0,
    [int]$Minutes = 0,
    [int]$Seconds = 0,
    [string]$Prompt = "Tiep tuc cong viec dang lam do"
)

Add-Type -AssemblyName System.Windows.Forms

$now = Get-Date

if ($At -ne "") {
    try {
        $target = [DateTime]::Parse($At)
        if ($target -le $now) {
            $target = $target.AddDays(1)
        }
        $totalSeconds = ($target - $now).TotalSeconds
    } catch {
        Write-Host "Loi dinh dang gio (-At 'HH:mm'). Vi du: -At '04:00'" -ForegroundColor Red
        exit 1
    }
} elseif ($Hours -gt 0 -or $Minutes -gt 0 -or $Seconds -gt 0) {
    $totalSeconds = ($Hours * 3600) + ($Minutes * 60) + $Seconds
    $target = $now.AddSeconds($totalSeconds)
} else {
    Write-Host "Vui long chi dinh thoi gian hen gio:" -ForegroundColor Yellow
    Write-Host "  1. Hen gio moc       : .\scripts\auto_resume_claude_extension.ps1 -At '04:00'" -ForegroundColor Cyan
    Write-Host "  2. Dem nguoc giay    : .\scripts\auto_resume_claude_extension.ps1 -Seconds 10" -ForegroundColor Cyan
    Write-Host "  3. Dem nguoc phut    : .\scripts\auto_resume_claude_extension.ps1 -Minutes 90 -Prompt 'Tiep tuc task'" -ForegroundColor Cyan
    exit 0
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   HEN GIO TU DONG GUI PROMPT CLAUDE TRONG IDE/EXTENSION  " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Thoi gian hien tai : $($now.ToString('HH:mm:ss dd/MM/yyyy'))"
Write-Host "Thoi diem kich hoat: $($target.ToString('HH:mm:ss dd/MM/yyyy'))"
Write-Host "Thoi gian cho      : $([math]::Round($totalSeconds, 1)) giay ($([math]::Round($totalSeconds / 60, 1)) phut)"
Write-Host "Prompt se gui      : `"$Prompt`"" -ForegroundColor Yellow
Write-Host "----------------------------------------------------------"
Write-Host "[Luu y] Hay de con tro chuot o o chat truoc khi dem nguoc ket thuc." -ForegroundColor Gray
Write-Host "Nhan Ctrl+C de huy hen gio bat cu luc nao." -ForegroundColor DarkGray
Write-Host ""

while ((Get-Date) -lt $target) {
    $remaining = ($target - (Get-Date)).TotalSeconds
    if ($remaining -le 0) { break }
    
    $remHours = [math]::Floor($remaining / 3600)
    $remMinutes = [math]::Floor(($remaining % 3600) / 60)
    $remSecs = [math]::Floor($remaining % 60)
    
    $timeStr = "{0:D2}:{1:D2}:{2:D2}" -f [int]$remHours, [int]$remMinutes, [int]$remSecs
    $percent = [math]::Max(0, [math]::Min(100, 100 - ($remaining / $totalSeconds * 100)))
    
    Write-Progress -Activity "Dang cho den gio kich hoat..." -Status "Con lai: $timeStr" -PercentComplete $percent
    Start-Sleep -Seconds 1
}

Write-Progress -Activity "Dang cho den gio kich hoat..." -Completed
Write-Host "`nDA DEN GIO! Dang kich hoat cua so IDE..." -ForegroundColor Green

$wshell = New-Object -ComObject WScript.Shell

# Thu cac ten cua so pho bien: Antigravity, VS Code, Cursor, Code, tkb_app
$appNames = @("Antigravity", "Visual Studio Code", "Code", "Cursor", "tkb_app")
$activated = $false

foreach ($appName in $appNames) {
    if ($wshell.AppActivate($appName)) {
        $activated = $true
        Write-Host "Da focus cua so: $appName" -ForegroundColor Green
        break
    }
}

Start-Sleep -Milliseconds 800

Write-Host "Dang dan prompt va gui tin nhan..." -ForegroundColor Cyan

# Copy prompt vao clipboard va dan vao khung chat
Set-Clipboard -Value $Prompt
Start-Sleep -Milliseconds 300

# Gui Ctrl+V de paste
$wshell.SendKeys("^v")
Start-Sleep -Milliseconds 500

# Gui Enter de gui
$wshell.SendKeys("{ENTER}")

Write-Host "`nDA GUI LENH THANH CONG VAO KHUNG CHAT!" -ForegroundColor Green
