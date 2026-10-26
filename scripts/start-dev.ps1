# 蜀道安全助手 - 开发环境启动器
# 说明：后端固定 8001（8000 已被另一个项目占用），前端 5173
#       每次双击都会重启本项目自己的旧进程，避免"复用了旧配置"导致页面报网络异常

$ErrorActionPreference = 'Stop'

$root     = Split-Path -Parent $PSScriptRoot          # D:\实习\shudao\test
$backend  = Join-Path $root 'project-root\backend'
$frontend = Join-Path $root 'project-root\frontend'
$py       = 'D:\Anaconda\envs\shixi\python.exe'
$backendPort  = 8001
$frontendPort = 5173

function Get-ListenerPid([int]$port) {
    $conn = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    if ($conn) { return ($conn | Select-Object -First 1).OwningProcess }
    return $null
}

function Get-ProcCmdLine([int]$procId) {
    $p = Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue
    if ($p) { return $p.CommandLine }
    return ''
}

# 端口若被本项目自己的旧进程占用，先结束再重启；被别的程序占用则报错退出
function Reset-Port([int]$port, [string]$marker, [string]$label) {
    $procId = Get-ListenerPid $port
    if (-not $procId) { return }
    $cmd = Get-ProcCmdLine $procId
    if ($cmd -like "*$marker*") {
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        Write-Host "  · $label 端口 $port 上有上次遗留的进程（PID $procId），已结束并重新启动"
        Start-Sleep -Milliseconds 800
    } else {
        Write-Host ""
        Write-Host "[错误] $label 端口 $port 被其他程序占用（PID $procId）"
        Write-Host "        $cmd"
        Write-Host "        请先关闭该程序，或修改本脚本顶部的端口配置"
        Read-Host "按回车退出"
        exit 1
    }
}

Write-Host "=========================================================="
Write-Host "  蜀道安全助手 - 一键启动"
Write-Host "  后端：http://127.0.0.1:$backendPort/docs"
Write-Host "  前端：http://localhost:$frontendPort"
Write-Host "=========================================================="
Write-Host ""

if (-not (Test-Path $py)) {
    Write-Host "[错误] 找不到 Python 解释器：$py"
    Read-Host "按回车退出"
    exit 1
}
if (-not (Test-Path (Join-Path $backend 'app\run.py'))) {
    Write-Host "[错误] 找不到后端入口：$backend\app\run.py"
    Read-Host "按回车退出"
    exit 1
}
if (-not (Test-Path (Join-Path $frontend 'package.json'))) {
    Write-Host "[错误] 找不到前端目录：$frontend"
    Read-Host "按回车退出"
    exit 1
}

$pg = Get-Service -Name 'postgresql-x64-16' -ErrorAction SilentlyContinue
if (-not $pg -or $pg.Status -ne 'Running') {
    Write-Host "[提示] PostgreSQL 服务未运行，后端可能连不上数据库，可先执行：net start postgresql-x64-16"
    Write-Host ""
}

Write-Host "[1/3] 检查并启动后端 FastAPI ..."
Reset-Port $backendPort 'app\run.py' '后端'
$backendCmd = "title 蜀道-后端 :$backendPort && `"$py`" app\run.py 127.0.0.1 $backendPort"
Start-Process -FilePath 'cmd.exe' -ArgumentList '/k', $backendCmd -WorkingDirectory $backend | Out-Null

Write-Host "[2/3] 检查并启动前端 Vite ..."
Reset-Port $frontendPort 'vite' '前端'
if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
    Write-Host "  · 未检测到 node_modules，首次启动先安装依赖，耗时较长"
    $frontCmd = "title 蜀道-前端 :$frontendPort && npm install && npm run dev"
} else {
    $frontCmd = "title 蜀道-前端 :$frontendPort && npm run dev"
}
Start-Process -FilePath 'cmd.exe' -ArgumentList '/k', $frontCmd -WorkingDirectory $frontend | Out-Null

Write-Host "[3/3] 等待服务就绪（最多 90 秒）..."
$deadline = (Get-Date).AddSeconds(90)
$ready = $false
while ((Get-Date) -lt $deadline) {
    if ((Get-ListenerPid $backendPort) -and (Get-ListenerPid $frontendPort)) { $ready = $true; break }
    Start-Sleep -Milliseconds 500
}

if (-not $ready) {
    Write-Host ""
    Write-Host "[提示] 90 秒内服务未全部就绪，请查看「蜀道-后端」「蜀道-前端」两个窗口里的报错"
    Read-Host "按回车退出"
    exit 1
}

# 自检：经前端代理请求后端，确认拿到蜀道自己的统一响应（code=40100 表示链路正常）
$status = 0
$body = ''
try {
    $r = Invoke-WebRequest "http://localhost:$frontendPort/api/v1/auth/me" -UseBasicParsing -TimeoutSec 15
    $status = [int]$r.StatusCode
    $body = $r.Content
} catch {
    $body = $_.ErrorDetails.Message
    $resp = $_.Exception.Response
    if ($resp) { $status = [int]$resp.StatusCode }
    if (-not $body -and $resp) {
        try { $sr = New-Object System.IO.StreamReader($resp.GetResponseStream()); $body = $sr.ReadToEnd() } catch { }
    }
    if (-not $body) { $body = $_.Exception.Message }
}

# 再确认后端身份（openapi 标题），避免把别的服务当成蜀道后端
$title = ''
try { $title = (Invoke-RestMethod "http://127.0.0.1:$backendPort/openapi.json" -TimeoutSec 10).info.title } catch { }

if ($body -like '*"code":40100*' -or ($status -eq 401 -and $title -like '*蜀道安全助手*')) {
    Write-Host "  · 自检通过：前端代理已连通蜀道后端（HTTP $status，$title）"
} else {
    Write-Host ""
    Write-Host "[警告] 自检未拿到预期响应（HTTP $status，$title）：$body"
    Write-Host "        前端可能仍指向了别的服务，请把上面这段内容发给我"
    Write-Host ""
}

Write-Host ""
Write-Host "正在打开浏览器 http://localhost:$frontendPort ..."
Start-Process "http://localhost:$frontendPort"
Write-Host ""
Write-Host "提示：关闭「蜀道-后端」「蜀道-前端」两个窗口即可停止服务。"
Start-Sleep -Seconds 4
exit 0
