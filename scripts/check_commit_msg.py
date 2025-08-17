#!/usr/bin/env python3
"""
コミットメッセージ形式検証スクリプト

要求形式: type(scope): description (refs #issue-number)
例: feat(github): GitHub API統合 (refs #51)

使用方法:
- pre-commitフックから自動実行
- 手動実行: python scripts/check_commit_msg.py .git/COMMIT_EDITMSG
"""

import re
import sys
from pathlib import Path


def check_commit_message(msg: str) -> tuple[bool, str]:
    """
    コミットメッセージの形式をチェックします。

    Args:
        msg: コミットメッセージ

    Returns:
        (is_valid, error_message)
    """
    lines = msg.strip().split("\n")
    if not lines:
        return False, "コミットメッセージが空です"

    first_line = lines[0].strip()

    # 基本パターン: type(scope): description (refs #number)
    # scopeはオプション
    pattern = r"^(feat|fix|docs|style|refactor|test|chore)(\(\w+\))?: .+ \(refs #\d+\)$"

    if not re.match(pattern, first_line):
        return False, _get_error_message(first_line)

    # 長さチェック（50文字まで推奨）
    if len(first_line) > 72:
        return False, f"コミットメッセージが長すぎます ({len(first_line)}/72文字)"

    return True, ""


def _get_error_message(msg: str) -> str:
    """エラーメッセージを生成します。"""

    error_msg = [
        "ERROR: コミットメッセージ形式エラー",
        "",
        "正しい形式:",
        "  type(scope): description (refs #issue-number)",
        "",
        "例:",
        "  feat(github): GitHub API統合を実装 (refs #51)",
        "  fix(voice): 音声処理のタイムアウト問題を修正 (refs #52)",
        "  docs: README.mdを更新 (refs #53)",
        "",
        "必須要素:",
        "  - type: feat, fix, docs, style, refactor, test, chore",
        "  - scope: オプション（モジュール名など）",
        "  - description: 日本語での説明",
        "  - (refs #number): Issue参照（必須）",
        "",
        f"入力されたメッセージ: '{msg}'",
    ]

    # 具体的な問題を特定
    if not re.match(r"^(feat|fix|docs|style|refactor|test|chore)", msg):
        error_msg.append(
            "\n問題: typeが正しくありません（feat, fix, docs, style, refactor, test, chore のいずれかを使用）"
        )
    elif "(refs #" not in msg:
        error_msg.append("\n問題: Issue参照 '(refs #数字)' が含まれていません")
    elif not re.search(r"\(refs #\d+\)$", msg):
        error_msg.append("\n問題: Issue参照の形式が正しくありません（末尾に '(refs #数字)' が必要）")

    return "\n".join(error_msg)


def main():
    """メイン処理"""
    if len(sys.argv) != 2:
        print("使用方法: python check_commit_msg.py <commit_msg_file>")
        sys.exit(1)

    commit_msg_file = Path(sys.argv[1])

    if not commit_msg_file.exists():
        print(f"エラー: ファイルが見つかりません: {commit_msg_file}")
        sys.exit(1)

    try:
        with open(commit_msg_file, "r", encoding="utf-8") as f:
            commit_msg = f.read()
    except UnicodeDecodeError:
        try:
            with open(commit_msg_file, "r", encoding="cp932") as f:
                commit_msg = f.read()
        except UnicodeDecodeError:
            print("エラー: ファイルの文字エンコーディングを判定できません")
            sys.exit(1)

    # コメント行（#で始まる行）を除去
    lines = commit_msg.split("\n")
    filtered_lines = [line for line in lines if not line.strip().startswith("#")]
    filtered_msg = "\n".join(filtered_lines).strip()

    if not filtered_msg:
        print("エラー: コミットメッセージが空です")
        sys.exit(1)

    is_valid, error_msg = check_commit_message(filtered_msg)

    if not is_valid:
        print(error_msg)
        sys.exit(1)

    print("OK: コミットメッセージ形式チェック: OK")


if __name__ == "__main__":
    main()
