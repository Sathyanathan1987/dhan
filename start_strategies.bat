@echo off
REM Start both NIFTY 50 and MCX strategies
REM Run this file at 9:00 AM every trading day
REM Or add it to Windows Task Scheduler manually (Task Scheduler > Create Task > Actions > start_strategies.bat)

cd /d "d:\kiro_algo\ALGO DHAN"

echo Starting NIFTY 50 strategy...
start "NIFTY50 Strategy" "C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe" -m nifty50_tracker.strategy.strategy_runner

echo Starting MCX strategy...
start "MCX Strategy" "C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe" -m nifty50_tracker.strategy.mcx_runner

echo Both strategies started. Check the console windows.
