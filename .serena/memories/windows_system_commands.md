# Windows システム用コマンド

## ファイル・ディレクトリ操作

### 基本ファイル操作
```cmd
# ディレクトリ一覧
dir
dir /a          # 隠しファイル含む
dir /s          # サブディレクトリ含む

# ファイル作成・編集
type nul > filename.txt     # 空ファイル作成
echo "content" > file.txt   # 内容付きファイル作成
echo "append" >> file.txt   # 追記

# ファイル表示
type filename.txt           # ファイル内容表示
more filename.txt           # ページ送り表示

# ファイル削除・移動
del filename.txt            # ファイル削除
rmdir /s dirname            # ディレクトリ削除（再帰）
move file.txt newname.txt   # ファイル移動・リネーム
copy file.txt backup.txt    # ファイルコピー
```

### PowerShell操作
```powershell
# ディレクトリ一覧
Get-ChildItem               # ls 相当
Get-ChildItem -Force        # 隠しファイル含む
Get-ChildItem -Recurse      # 再帰的

# ファイル操作
New-Item -ItemType File filename.txt
Remove-Item filename.txt
Move-Item file.txt newname.txt
Copy-Item file.txt backup.txt

# ファイル内容
Get-Content filename.txt
Get-Content filename.txt -Tail 10      # 末尾10行
Get-Content filename.txt -Wait          # リアルタイム監視

# 文字列検索
Select-String "pattern" filename.txt    # grep 相当
Get-ChildItem -Recurse | Select-String "pattern"
```

## プロセス・サービス管理

### プロセス操作
```cmd
# プロセス一覧
tasklist
tasklist /fi "imagename eq python.exe"   # Python プロセスのみ

# プロセス終了
taskkill /f /im python.exe                # プロセス名で終了
taskkill /f /pid 1234                     # PID で終了
```

```powershell
# PowerShell プロセス管理
Get-Process                               # プロセス一覧
Get-Process python                        # Python プロセスのみ
Stop-Process -Name python                 # プロセス終了
Stop-Process -Id 1234                     # PID で終了
```

### サービス管理（管理者権限必要）
```powershell
# サービス一覧・操作
Get-Service
Start-Service ServiceName
Stop-Service ServiceName
Restart-Service ServiceName
```

## ネットワーク・システム情報

### ネットワーク
```cmd
# 接続確認
ping google.com
nslookup google.com
ipconfig                    # IP設定表示
ipconfig /all               # 詳細情報
netstat -an                 # ネットワーク接続一覧
```

### システム情報
```cmd
# システム情報
systeminfo                  # システム詳細情報
wmic os get caption,version # OS情報
echo %USERNAME%             # ユーザー名
echo %COMPUTERNAME%         # コンピューター名
```

```powershell
# PowerShell システム情報
Get-ComputerInfo
$env:USERNAME               # ユーザー名
$env:COMPUTERNAME           # コンピューター名
Get-WmiObject Win32_OperatingSystem
```

## 環境変数・パス

### 環境変数操作
```cmd
# 環境変数表示
set                         # 全環境変数
echo %PATH%                 # PATH変数
echo %USERPROFILE%          # ユーザーディレクトリ

# 環境変数設定（一時的）
set MYVAR=value
```

```powershell
# PowerShell 環境変数
Get-ChildItem Env:          # 全環境変数
$env:PATH                   # PATH変数
$env:USERPROFILE            # ユーザーディレクトリ

# 環境変数設定
$env:MYVAR = "value"        # 一時的
[Environment]::SetEnvironmentVariable("MYVAR", "value", "User")  # 永続的
```

### パス・ディレクトリ
```cmd
# 現在ディレクトリ
cd                          # 現在位置表示
pwd                         # PowerShell
cd /d D:\workspace          # ドライブ変更付き移動
pushd path && popd          # ディレクトリスタック
```

## ソフトウェア管理

### Package Manager
```powershell
# Chocolatey
choco list --local-only     # インストール済み一覧
choco install package-name
choco upgrade package-name
choco uninstall package-name

# Scoop
scoop list                  # インストール済み一覧
scoop install package-name
scoop update package-name
scoop uninstall package-name

# winget（Windows 10/11）
winget list                 # インストール済み一覧
winget install package-name
winget upgrade package-name
winget uninstall package-name
```

### Python・Poetry固有
```cmd
# Python実行ファイル検索
where python
where python3
where poetry

# PowerShell版
Get-Command python
Get-Command poetry
```

```powershell
# Poetry環境
poetry --version
poetry env info             # 仮想環境情報
poetry env list             # 環境一覧
poetry shell                # シェル起動

# Python環境
python --version
python -m pip list          # インストール済みパッケージ
```

## 検索・テキスト処理

### ファイル検索
```cmd
# ファイル名検索
dir /s filename.txt         # 再帰的ファイル検索
where /r . *.py             # 拡張子でファイル検索

# 文字列検索
findstr "pattern" *.txt     # grep 相当
findstr /s /i "pattern" *   # 大小文字無視・再帰検索
```

```powershell
# PowerShell検索
Get-ChildItem -Recurse -Name "*.py"           # ファイル名検索
Select-String "pattern" *.txt                 # 文字列検索
Get-ChildItem -Recurse | Select-String "pattern"  # 再帰的文字列検索
```

## Git・開発関連

### Git操作（Windows特有）
```cmd
# Git Bash使用推奨
git config --global core.autocrlf true    # Windows改行コード自動変換
git config --global core.filemode false   # ファイル権限無視

# Windows パス問題対処
git config --global core.longpaths true   # 長いパス名対応
```

###開発環境
```cmd
# VS Code起動
code .                      # 現在ディレクトリで起動
code filename.txt           # ファイル編集

# Node.js・npm（必要時）
npm --version
npm list -g                 # グローバルパッケージ一覧
```

## ログ・監視

### ログファイル監視
```powershell
# リアルタイムログ監視
Get-Content bot.log -Wait -Tail 10

# ログローテーション確認
Get-ChildItem *.log | Sort-Object LastWriteTime
```

### システム監視
```cmd
# CPU・メモリ使用量
wmic cpu get loadpercentage /value
wmic OS get TotalVisibleMemorySize,FreePhysicalMemory /value

# ディスク使用量
wmic logicaldisk get size,freespace,caption
```

```powershell
# PowerShell システム監視
Get-Counter "\Processor(_Total)\% Processor Time"
Get-WmiObject -Class Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory
Get-WmiObject -Class Win32_LogicalDisk | Select-Object DeviceID,Size,FreeSpace
```

## トラブルシューティング

### 権限・アクセス問題
```powershell
# 管理者権限確認
([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")

# ファイル権限確認
Get-Acl filename.txt

# 実行ポリシー（PowerShell）
Get-ExecutionPolicy
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### パフォーマンス・診断
```cmd
# システム診断
sfc /scannow                # システムファイルチェック
dism /online /cleanup-image /checkhealth  # イメージヘルス確認

# イベントログ確認
eventvwr.msc                # イベントビューアー起動
```
