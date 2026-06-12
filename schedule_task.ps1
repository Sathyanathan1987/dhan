# Register Task Scheduler entries for trading strategies
# Run this script once: Right-click > Run with PowerShell
# Or open PowerShell as Admin and run: .\schedule_task.ps1

$python  = "C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe"
$workdir = "d:\kiro_algo\ALGO DHAN"
$user    = $env:USERNAME

# Trigger: Mon-Fri at 09:00 AM
$trigger = New-ScheduledTaskTrigger -Weekly `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
    -At "09:00AM"

# Run for up to 8 hours, start if missed (e.g. PC was off)
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 8) `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

# ── NIFTY 50 Strategy ──────────────────────────────────────
$action1 = New-ScheduledTaskAction `
    -Execute  $python `
    -Argument "-m nifty50_tracker.strategy.strategy_runner" `
    -WorkingDirectory $workdir

Register-ScheduledTask `
    -TaskName "AlgoTrading_NIFTY50" `
    -Action   $action1 `
    -Trigger  $trigger `
    -Settings $settings `
    -RunLevel Limited `
    -Force

Write-Host "NIFTY50 task registered." -ForegroundColor Green

# ── MCX Strategy ───────────────────────────────────────────
$action2 = New-ScheduledTaskAction `
    -Execute  $python `
    -Argument "-m nifty50_tracker.strategy.mcx_runner" `
    -WorkingDirectory $workdir

Register-ScheduledTask `
    -TaskName "AlgoTrading_MCX" `
    -Action   $action2 `
    -Trigger  $trigger `
    -Settings $settings `
    -RunLevel Limited `
    -Force

Write-Host "MCX task registered." -ForegroundColor Green
Write-Host ""
Write-Host "Both tasks will auto-start at 09:00 AM Mon-Fri." -ForegroundColor Cyan
Write-Host "View in: Task Scheduler > Task Scheduler Library"
