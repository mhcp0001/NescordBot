#!/bin/bash

# Enhanced deny-check script with development-safe process management
# JSON 入力を読み取り、コマンドとツール名を抽出
input=$(cat)
command=$(echo "$input" | jq -r '.tool_input.command' 2>/dev/null || echo "")
tool_name=$(echo "$input" | jq -r '.tool_name' 2>/dev/null || echo "")

# Bash コマンドのみをチェック
if [ "$tool_name" != "Bash" ]; then
  exit 0
fi

# settings.json から拒否パターンを読み取り
settings_file="$HOME/.claude/settings.json"

# Bash コマンドの全拒否パターンを取得
deny_patterns=$(jq -r '.permissions.deny[] | select(startswith("Bash(")) | gsub("^Bash\\("; "") | gsub("\\)$"; "")' "$settings_file" 2>/dev/null)

# 開発用プロセス管理の安全なパターン定義
declare -A SAFE_DEV_PROCESSES=(
    ["node"]="Node.js development servers"
    ["npm"]="npm processes"
    ["jest"]="Jest test runner"
    ["webpack"]="Webpack bundler"
    ["ts-node"]="TypeScript Node.js"
    ["nodemon"]="Node.js monitor"
    ["express"]="Express.js server"
    ["vite"]="Vite development server"
    ["rollup"]="Rollup bundler"
    ["esbuild"]="ESBuild bundler"
    ["mocha"]="Mocha test runner"
    ["cypress"]="Cypress testing"
    ["playwright"]="Playwright testing"
)

declare -A DANGEROUS_SYSTEM_PROCESSES=(
    ["init"]="System init process"
    ["systemd"]="Systemd processes"
    ["ssh"]="SSH daemon"
    ["sshd"]="SSH daemon"
    ["docker"]="Docker daemon"
    ["nginx"]="Nginx web server"
    ["apache"]="Apache web server"
    ["mysql"]="MySQL database"
    ["postgres"]="PostgreSQL database"
    ["redis"]="Redis database"
    ["mongod"]="MongoDB database"
    ["kernel"]="Kernel processes"
)

# コマンドが拒否パターンにマッチするかチェックする関数
matches_deny_pattern() {
  local cmd="$1"
  local pattern="$2"

  # 先頭・末尾の空白を削除
  cmd="${cmd#"${cmd%%[![:space:]]*}"}" # 先頭の空白を削除
  cmd="${cmd%"${cmd##*[![:space:]]}"}" # 末尾の空白を削除

  # glob パターンマッチング（ワイルドカード対応）
  [[ "$cmd" == $pattern ]]
}

# kill コマンドの安全性チェック
check_kill_safety() {
  local kill_cmd="$1"
  
  # PID 1 (init) の強制終了を特別にブロック
  if [[ "$kill_cmd" =~ kill[[:space:]]+-?9?[[:space:]]*1([[:space:]]|$) ]]; then
    echo "Error: init プロセス (PID 1) の終了は禁止されています" >&2
    return 1
  fi
  
  return 0
}

# pkill コマンドの安全性チェック (Windows環境では動作しない可能性あり)
check_pkill_safety() {
  local pkill_cmd="$1"
  
  # プロセス名を抽出
  local process_name=$(echo "$pkill_cmd" | sed -n 's/.*pkill[[:space:]]\+\([^[:space:]]*\).*/\1/p')
  
  # 危険なシステムプロセスかチェック
  for dangerous_proc in "${!DANGEROUS_SYSTEM_PROCESSES[@]}"; do
    if [[ "$process_name" == "$dangerous_proc"* ]]; then
      echo "Error: システムプロセス '$process_name' の終了は禁止されています (${DANGEROUS_SYSTEM_PROCESSES[$dangerous_proc]})" >&2
      return 1
    fi
  done
  
  # 安全な開発プロセスかチェック
  for safe_proc in "${!SAFE_DEV_PROCESSES[@]}"; do
    if [[ "$process_name" == "$safe_proc"* ]]; then
      echo "Info: 開発プロセス '$process_name' の終了を許可 (${SAFE_DEV_PROCESSES[$safe_proc]})"
      return 0
    fi
  done
  
  # 許可されていないプロセス名
  echo "Error: プロセス '$process_name' の終了は許可されていません" >&2
  return 1
}

# systemctl コマンドの安全性チェック
check_systemctl_safety() {
  local systemctl_cmd="$1"
  
  # --user フラグがあるかチェック
  if [[ "$systemctl_cmd" =~ --user ]]; then
    echo "Info: ユーザースコープの systemctl 操作を許可"
    return 0
  fi
  
  # システム全体への操作はブロック
  echo "Error: システム全体の systemctl 操作は禁止されています。--user フラグを使用してください" >&2
  return 1
}

# 特別な安全性チェック
perform_special_safety_checks() {
  local cmd="$1"
  
  # kill コマンドのチェック
  if [[ "$cmd" =~ ^kill[[:space:]] ]]; then
    check_kill_safety "$cmd"
    return $?
  fi
  
  # pkill コマンドのチェック
  if [[ "$cmd" =~ ^pkill[[:space:]] ]]; then
    check_pkill_safety "$cmd"
    return $?
  fi
  
  # systemctl コマンドのチェック
  if [[ "$cmd" =~ ^systemctl[[:space:]] ]]; then
    check_systemctl_safety "$cmd"
    return $?
  fi
  
  return 0
}

# まず特別な安全性チェックを実行
if ! perform_special_safety_checks "$command"; then
  exit 2
fi

# まずコマンド全体をチェック
while IFS= read -r pattern; do
  # 空行をスキップ
  [ -z "$pattern" ] && continue

  # コマンド全体がパターンにマッチするかチェック
  if matches_deny_pattern "$command" "$pattern"; then
    echo "Error: コマンドが拒否されました: '$command' (パターン: '$pattern')" >&2
    exit 2
  fi
done <<<"$deny_patterns"

# コマンドを論理演算子で分割し、各部分もチェック
# セミコロン、&& と || で分割（パイプ | と単一 & は分割しない）
temp_command="${command//;/$'\n'}"
temp_command="${temp_command//&&/$'\n'}"
temp_command="${temp_command//\|\|/$'\n'}"

IFS=$'\n'
for cmd_part in $temp_command; do
  # 空の部分をスキップ
  [ -z "$(echo "$cmd_part" | tr -d '[:space:]')" ] && continue

  # 特別な安全性チェック
  if ! perform_special_safety_checks "$cmd_part"; then
    exit 2
  fi

  # 各拒否パターンに対してチェック
  while IFS= read -r pattern; do
    # 空行をスキップ
    [ -z "$pattern" ] && continue

    # このコマンド部分がパターンにマッチするかチェック
    if matches_deny_pattern "$cmd_part" "$pattern"; then
      echo "Error: コマンドが拒否されました: '$cmd_part' (パターン: '$pattern')" >&2
      exit 2
    fi
  done <<<"$deny_patterns"
done

# コマンドを許可
echo "Info: コマンドが許可されました: '$command'" >&2
exit 0
