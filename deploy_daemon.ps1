# Windows Task Scheduler 守护进程部署脚本
# 运行此脚本将创建一个名为 "Antigravity_AI_Trend_Watcher" 的计划任务，
# 每天 09:30 自动静默运行 F:\message\agent.py。

$TaskName = "Antigravity_AI_Trend_Watcher"
$ScriptPath = "F:\message\agent.py"
$PythonWPath = (Get-Command pythonw.exe).Source # 使用 pythonw.exe 实现完全无黑窗后台静默运行

if (-Not $PythonWPath) {
    Write-Host "错误: 找不到 pythonw.exe。请确保 Python 已加入系统环境变量。" -ForegroundColor Red
    exit
}

# 1. 触发器：每天 09:30
$Trigger = New-ScheduledTaskTrigger -Daily -At "09:30AM"

# 2. 也是为了灵活性，可以额外加上系统启动时运行 (可选，当前只用定时)
# $Trigger2 = New-ScheduledTaskTrigger -AtStartup

# 3. 操作：执行 pythonw
$Action = New-ScheduledTaskAction -Execute $PythonWPath -Argument $ScriptPath -WorkingDirectory "F:\message"

# 4. 设置：允许在需要时按需运行，如果运行时间过长不停止
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Days 0)

# 5. 注册任务
try {
    # 先尝试删除已有的同名任务
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    
    # 注册新任务
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "自动获取 AI 趋势并推送企业微信" | Out-Null
    Write-Host "✅ 成功创建并注册 Windows 守护进程任务: $TaskName" -ForegroundColor Green
    Write-Host "配置为: 每天早上 09:30 静默执行 (无黑窗)。" -ForegroundColor Cyan
    Write-Host "后台执行日志将输出至: F:\message\logs\app.log" -ForegroundColor Cyan
    Write-Host "如需手动触发测试，可在 PowerShell 运行: Start-ScheduledTask -TaskName $TaskName" -ForegroundColor Yellow
} catch {
    Write-Host "❌ 注册计划任务失败，请尝试以 [管理员身份] 运行此 PowerShell 窗口后再试。" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}
