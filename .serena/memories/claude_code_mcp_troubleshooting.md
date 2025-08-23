# Claude Code MCP接続トラブルシューティング

## 概要
Claude CodeでMCPサーバー接続失敗時の診断・修正手順についての知見

## 問題パターンと解決方法

### 1. GitHub MCP接続失敗の典型的原因

#### 症状
- `claude mcp list`で`✗ Failed to connect`表示
- ユーザーレベルでMCP設定済みなのに接続できない

#### 原因1: GitHubトークンの問題
**問題**: 古いトークンや権限不足
**解決方法**:
```bash
# 1. 認証リフレッシュ（必要な権限付与）
gh auth refresh --hostname github.com --scopes repo,read:org,workflow

# 2. 新しいトークンを取得
gh auth token

# 3. .claude.json内のGITHUB_TOKENを更新
```

**重要**: `ghp_`で始まる古いトークンは期限切れの可能性が高い

#### 原因2: Windowsでのコマンド形式問題
**問題**: `cmd /c`形式がstdio通信を阻害
**修正前**:
```json
{
  "command": "cmd /c npx -y @modelcontextprotocol/server-github",
  "args": []
}
```

**修正後**:
```json
{
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-github"]
}
```

### 2. MCP設定継承メカニズム

#### 基本ルール
- **ユーザーレベル設定**: `~/.claude.json`の`mcpServers`
- **プロジェクトレベル設定**: `プロジェクト/.claude.json`の`projects[path].mcpServers`
- **継承**: プロジェクトレベルが空の場合、ユーザーレベル設定を継承
- **上書き**: プロジェクトレベルに設定がある場合、ユーザーレベルを完全に上書き

#### 誤解されやすいポイント
- 空の`"mcpServers": {}`があってもユーザーレベル設定は継承される
- プロジェクト固有の設定は不要（むしろ避けるべき）

### 3. 診断手順

#### ステップ1: 基本確認
```bash
# MCPサーバー状態確認
claude mcp list

# GitHub CLI認証確認
gh auth status
```

#### ステップ2: トークン更新
```bash
# 認証リフレッシュ
gh auth refresh --hostname github.com --scopes repo,read:org,workflow

# 新トークン確認
gh auth token
```

#### ステップ3: 設定修正
1. `.claude.json`内のGITHUB_TOKENを新しいトークンに更新
2. Windowsの場合、コマンド形式を`npx`+`args`形式に修正

#### ステップ4: 接続テスト
```bash
# MCPサーバー再確認
claude mcp list
```

## ベストプラクティス

### 設定管理
1. **トークンの定期更新**: 期限切れ前の定期的な認証リフレッシュ
2. **シンプルな設定**: プロジェクトレベルでの個別設定は避ける
3. **コマンド形式統一**: Windows環境でも`npx`+`args`形式を使用

### トラブルシューティング
1. **段階的診断**: 設定継承 → トークン → コマンド形式の順で確認
2. **Claude-Gemini協力**: 複雑な問題はGeminiに技術的助言を求める
3. **証拠ベース修正**: ログとテスト結果に基づく確実な判断

## 関連コマンド
```bash
# MCP管理
claude mcp list                    # サーバー状態確認
claude mcp add <server>           # サーバー追加

# GitHub認証
gh auth status                    # 認証状態確認
gh auth token                     # トークン取得
gh auth refresh --hostname github.com --scopes repo,read:org,workflow

# 設定確認
cat ~/.claude.json | jq '.mcpServers'  # ユーザーレベル設定確認
```
