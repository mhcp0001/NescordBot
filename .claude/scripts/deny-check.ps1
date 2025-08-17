# Enhanced deny-check PowerShell script for Windows
# Development-safe process management with comprehensive security

# JSON入力を読み取り
$input = [Console]::In.ReadToEnd()

try {
    $jsonInput = $input | ConvertFrom-Json
    $command = $jsonInput.tool_input.command
    $toolName = $jsonInput.tool_name
} catch {
    # JSON解析エラーの場合は許可
    exit 0
}

# Bashコマンドのみをチェック
if ($toolName -ne "Bash") {
    exit 0
}

# 設定ファイルから拒否パターンを読み込み
$settingsPath = ".\.claude\settings.local.json"
if (Test-Path $settingsPath) {
    try {
        $settings = Get-Content $settingsPath | ConvertFrom-Json
        $denyPatterns = $settings.permissions.deny | Where-Object { $_ -like "Bash(*" } | ForEach-Object {
            $_ -replace "^Bash\(", "" -replace "\)$", ""
        }
    } catch {
        $denyPatterns = @()
    }
} else {
    $denyPatterns = @()
}

# 開発用プロセス管理の安全なパターン
$safeDevelopmentProcesses = @(
    "node", "npm", "jest", "webpack", "ts-node", "nodemon", "express",
    "vite", "rollup", "esbuild", "mocha", "cypress", "playwright"
)

$dangerousSystemProcesses = @(
    "init", "systemd", "ssh", "sshd", "docker", "nginx", "apache",
    "mysql", "postgres", "redis", "mongod", "kernel"
)

# 特別な安全性チェック関数
function Test-KillSafety {
    param([string]$killCmd)

    # PID 1の終了を特別にブロック
    if ($killCmd -match "kill\s+-?9?\s*1(\s|$)") {
        Write-Host "Info: initプロセス (PID 1) の終了は禁止されています - ブロックしました"
        return $false
    }

    return $true
}

function Test-PkillSafety {
    param([string]$pkillCmd)

    # プロセス名を抽出
    if ($pkillCmd -match "pkill\s+(\S+)") {
        $processName = $Matches[1]

        # 危険なシステムプロセスかチェック
        foreach ($dangerousProc in $dangerousSystemProcesses) {
            if ($processName -like "$dangerousProc*") {
                Write-Host "Info: システムプロセス '$processName' の終了は禁止されています - ブロックしました"
                return $false
            }
        }

        # 安全な開発プロセスかチェック
        foreach ($safeProc in $safeDevelopmentProcesses) {
            if ($processName -like "$safeProc*") {
                return $true
            }
        }

        Write-Host "Info: プロセス '$processName' の終了は許可されていません - ブロックしました"
        return $false
    }

    return $true
}

function Test-SystemctlSafety {
    param([string]$systemctlCmd)

    # --userフラグがあるかチェック
    if ($systemctlCmd -match "--user") {
        return $true
    }

    Write-Host "Info: システム全体のsystemctl操作は禁止されています - ブロックしました"
    return $false
}

# 特別な安全性チェック
function Test-SpecialSafety {
    param([string]$cmd)

    if ($cmd -match "^kill\s") {
        return Test-KillSafety $cmd
    }

    if ($cmd -match "^pkill\s") {
        return Test-PkillSafety $cmd
    }

    if ($cmd -match "^systemctl\s") {
        return Test-SystemctlSafety $cmd
    }

    return $true
}

# パターンマッチング関数
function Test-DenyPattern {
    param([string]$cmd, [string]$pattern)

    $cmd = $cmd.Trim()
    return $cmd -like $pattern
}

# メイン処理
if (-not $command) {
    exit 0
}

# 特別な安全性チェック
if (-not (Test-SpecialSafety $command)) {
    exit 2
}

# 拒否パターンチェック
foreach ($pattern in $denyPatterns) {
    if (-not $pattern) { continue }

    if (Test-DenyPattern $command $pattern) {
        Write-Host "Info: コマンドが拒否されました: '$command' (パターン: '$pattern') - ブロックしました"
        exit 2
    }
}

# コマンドを論理演算子で分割してチェック
$commandParts = $command -split '[;&]|&&|\|\|' | ForEach-Object { $_.Trim() } | Where-Object { $_ }

foreach ($cmdPart in $commandParts) {
    if (-not (Test-SpecialSafety $cmdPart)) {
        exit 2
    }

    foreach ($pattern in $denyPatterns) {
        if (-not $pattern) { continue }

        if (Test-DenyPattern $cmdPart $pattern) {
            Write-Host "Info: コマンドが拒否されました: '$cmdPart' (パターン: '$pattern') - ブロックしました"
            exit 2
        }
    }
}

# コマンドを許可（サイレント）
exit 0
