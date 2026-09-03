<#
.SYNOPSIS
    Script hẹn giờ tự động kích hoạt và tiếp tục session Claude Code (hoặc tiếp tục prompt).

.EXAMPLE
    # Chờ đến đúng 04:00 sáng rồi tự resume Claude
    .\scripts\auto_resume_claude.ps1 -At "04:00"

    # Chờ 90 phút rồi tự resume
    .\scripts\auto_resume_claude.ps1 -Minutes 90

    # Chờ đến 03:30 và tự động gửi prompt tiếp tục làm việc
    .\scripts\auto_resume_claude.ps1 -At "03:30" -Prompt "Tiếp tục thực hiện task tiếp theo theo plan"
#>

param(
    [string]$At = "",          # Giờ mốc chạy (VD: "04:00", "04:30:00")
    [int]$Minutes = 0,         # Số phút đếm ngược
    [int]$Hours = 0,           # Số giờ đếm ngược
    [string]$Prompt = ""       # Prompt tùy chọn gửi cho Claude (nếu để trống sẽ mở claude --resume interactive)
)

$now = Get-Date

if ($At -ne "") {
    try {
        $target = [DateTime]::Parse($At)
        # Nếu giờ truyền vào đã qua so với hiện tại, tính là của ngày mai
        if ($target -le $now) {
            $target = $target.AddDays(1)
        }
        $totalSeconds = ($target - $now).TotalSeconds
    } catch {
        Write-Host "Lỗi: Định dạng giờ không hợp lệ (-At 'HH:mm'). Ví dụ: -At '04:00'" -ForegroundColor Red
        exit 1
    }
} elseif ($Hours -gt 0 -or $Minutes -gt 0) {
    $totalSeconds = ($Hours * 3600) + ($Minutes * 60)
    $target = $now.AddSeconds($totalSeconds)
} else {
    Write-Host "Vui lòng chỉ định thời gian hẹn giờ:" -ForegroundColor Yellow
    Write-Host "  1. Hẹn đúng giờ mốc : .\scripts\auto_resume_claude.ps1 -At '04:00'" -ForegroundColor Cyan
    Write-Host "  2. Đếm ngược số phút : .\scripts\auto_resume_claude.ps1 -Minutes 120" -ForegroundColor Cyan
    Write-Host "  3. Kèm prompt tự động: .\scripts\auto_resume_claude.ps1 -At '04:00' -Prompt 'Tiếp tục task'" -ForegroundColor Cyan
    exit 0
}

Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "     HẸN GIỜ TỰ ĐỘNG RESUME SESSION CLAUDE       " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "Thời gian hiện tại : $($now.ToString('HH:mm:ss dd/MM/yyyy'))"
Write-Host "Thời điểm kích hoạt: $($target.ToString('HH:mm:ss dd/MM/yyyy'))"
Write-Host "Thời gian chờ      : $([math]::Round($totalSeconds / 60, 1)) phút ($([math]::Round($totalSeconds / 3600, 2)) giờ)"
if ($Prompt) {
    Write-Host "Prompt gửi tự động : `"$Prompt`"" -ForegroundColor Yellow
} else {
    Write-Host "Chế độ             : Interactive resume (claude --resume)" -ForegroundColor Green
}
Write-Host "-------------------------------------------------"
Write-Host "Nhấn Ctrl+C bất cứ lúc nào nếu muốn hủy hẹn giờ." -ForegroundColor DarkGray
Write-Host ""

while ((Get-Date) -lt $target) {
    $remaining = ($target - (Get-Date)).TotalSeconds
    if ($remaining -le 0) { break }
    
    $remHours = [math]::Floor($remaining / 3600)
    $remMinutes = [math]::Floor(($remaining % 3600) / 60)
    $remSecs = [math]::Floor($remaining % 60)
    
    $timeStr = "{0:D2}:{1:D2}:{2:D2}" -f [int]$remHours, [int]$remMinutes, [int]$remSecs
    $percent = [math]::Max(0, [math]::Min(100, 100 - ($remaining / $totalSeconds * 100)))
    
    Write-Progress -Activity "Đang chờ đến giờ reset..." -Status "Thời gian còn lại: $timeStr" -PercentComplete $percent
    Start-Sleep -Seconds 1
}

Write-Progress -Activity "Đang chờ đến giờ reset..." -Completed
Write-Host "`nĐÃ ĐẾN GIỜ! Bắt đầu kích hoạt Claude Code..." -ForegroundColor Green
Write-Host ""

# Chạy claude
if ($Prompt -ne "") {
    # Chạy non-interactive print hoặc resume với prompt
    claude -p "$Prompt" --resume
} else {
    # Chạy interactive resume
    claude --resume
}
