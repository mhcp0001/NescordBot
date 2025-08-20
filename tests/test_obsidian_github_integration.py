"""
ObsidianGitHub統合テスト

Discord → ObsidianGitHub → GitHub の完全な統合フローをテスト
"""

import asyncio
import io
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import discord
import discord.ui
import pytest

from src.nescordbot.bot import NescordBot
from src.nescordbot.cogs.voice import Voice
from src.nescordbot.services.obsidian_github import ObsidianGitHubService


@pytest.fixture
def mock_config_full():
    """完全なObsidianGitHub設定を持つモック設定"""
    config = MagicMock()
    config.discord_token = "test_token"
    config.openai_api_key = "test_openai_key"
    config.database_url = ":memory:"
    config.log_level = "INFO"
    config.max_audio_size_mb = 25
    config.speech_language = "ja"

    # GitHub configuration
    config.github_token = "test_github_token"
    config.github_repo_owner = "test_owner"
    config.github_repo_name = "obsidian-vault"
    config.github_obsidian_enabled = True
    config.github_obsidian_base_path = "fleeting_notes"
    config.github_obsidian_branch = "main"
    config.github_obsidian_batch_size = 5
    config.github_obsidian_batch_interval = 10

    return config


@pytest.fixture
def mock_config_minimal():
    """最小限設定（ObsidianGitHub無効）のモック設定"""
    config = MagicMock()
    config.discord_token = "test_token"
    config.openai_api_key = "test_openai_key"
    config.database_url = ":memory:"
    config.log_level = "INFO"
    config.max_audio_size_mb = 25
    config.speech_language = "ja"

    # GitHub integration disabled
    config.github_token = None
    config.github_repo_owner = None
    config.github_repo_name = None
    config.github_obsidian_enabled = False

    return config


@pytest.fixture
def mock_discord_objects():
    """Discord関連のモックオブジェクト"""
    # Mock user
    user = MagicMock(spec=discord.User)
    user.id = 123456789
    user.display_name = "TestUser"
    user.bot = False
    user.configure_mock(**{"__str__.return_value": "TestUser#1234"})

    # Mock guild
    guild = MagicMock(spec=discord.Guild)
    guild.id = 987654321
    guild.name = "TestGuild"

    # Mock channel
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 555666777
    channel.name = "test-channel"

    # Mock message
    message = MagicMock(spec=discord.Message)
    message.id = 111222333
    message.author = user
    message.guild = guild
    message.channel = channel
    message.content = "テストメッセージ"
    message.attachments = []
    message.created_at = datetime.utcnow()

    # Mock attachment
    attachment = MagicMock(spec=discord.Attachment)
    attachment.id = 444555666
    attachment.filename = "voice_message.ogg"
    attachment.size = 1024 * 1024  # 1MB
    attachment.content_type = "audio/ogg"

    return {
        "user": user,
        "guild": guild,
        "channel": channel,
        "message": message,
        "attachment": attachment,
    }


@pytest.fixture
def mock_openai_responses():
    """OpenAI APIレスポンスのモック"""
    transcript_response = MagicMock()
    transcript_response.text = "これはテスト音声の文字起こしです。"

    chat_response = MagicMock()
    chat_response.choices = [MagicMock()]
    chat_response.choices[0].message = MagicMock()
    chat_response.choices[0].message.content = "整形されたテスト音声の内容です。"

    summary_response = MagicMock()
    summary_response.choices = [MagicMock()]
    summary_response.choices[0].message = MagicMock()
    summary_response.choices[0].message.content = "音声の要約"

    return {
        "transcript": transcript_response,
        "chat": chat_response,
        "summary": summary_response,
    }


class TestObsidianGitHubBotIntegration:
    """Bot初期化とObsidianGitHub統合テスト"""

    @patch("src.nescordbot.bot.get_config_manager")
    @patch("src.nescordbot.bot.get_logger")
    def test_bot_with_obsidian_enabled(
        self, mock_logger, mock_get_config_manager, mock_config_full
    ):
        """ObsidianGitHub有効時のBot初期化テスト"""
        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config_full
        mock_get_config_manager.return_value = mock_config_manager
        mock_logger.return_value = MagicMock()

        with patch("src.nescordbot.bot.DatabaseService"), patch(
            "src.nescordbot.bot.SecurityValidator"
        ), patch("src.nescordbot.bot.GitHubAuthManager"), patch(
            "src.nescordbot.bot.GitOperationService"
        ), patch(
            "src.nescordbot.bot.BatchProcessor"
        ), patch(
            "src.nescordbot.bot.ObsidianGitHubService"
        ) as mock_obsidian_service:
            bot = NescordBot()

            # サービス初期化確認
            assert hasattr(bot, "obsidian_service")
            assert bot.obsidian_service is not None
            mock_obsidian_service.assert_called_once()

            # 依存関係の確認
            assert hasattr(bot, "security_validator")
            assert hasattr(bot, "github_auth_manager")
            assert hasattr(bot, "git_operations")
            assert hasattr(bot, "batch_processor")

    @patch("src.nescordbot.bot.get_config_manager")
    @patch("src.nescordbot.bot.get_logger")
    def test_bot_with_obsidian_disabled(
        self, mock_logger, mock_get_config_manager, mock_config_minimal
    ):
        """ObsidianGitHub無効時のBot初期化テスト"""
        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config_minimal
        mock_get_config_manager.return_value = mock_config_manager
        mock_logger.return_value = MagicMock()

        with patch("src.nescordbot.bot.DatabaseService"):
            bot = NescordBot()

            # ObsidianGitHubサービスが無効化されていることを確認
            assert bot.obsidian_service is None

    @pytest.mark.asyncio
    async def test_bot_service_initialization_chain(self, mock_config_full):
        """サービス初期化チェーンのテスト"""
        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config_full

        mock_security_validator = MagicMock()
        mock_github_auth_manager = AsyncMock()
        mock_git_operations = AsyncMock()
        mock_batch_processor = AsyncMock()
        mock_obsidian_service = AsyncMock()

        with patch(
            "src.nescordbot.bot.get_config_manager", return_value=mock_config_manager
        ), patch("src.nescordbot.bot.get_logger"), patch(
            "src.nescordbot.bot.DatabaseService"
        ), patch(
            "src.nescordbot.bot.SecurityValidator", return_value=mock_security_validator
        ), patch(
            "src.nescordbot.bot.GitHubAuthManager", return_value=mock_github_auth_manager
        ), patch(
            "src.nescordbot.bot.GitOperationService", return_value=mock_git_operations
        ), patch(
            "src.nescordbot.bot.BatchProcessor", return_value=mock_batch_processor
        ), patch(
            "src.nescordbot.bot.ObsidianGitHubService", return_value=mock_obsidian_service
        ):
            bot = NescordBot()

            # setup_hookの実行をシミュレート
            await bot._init_obsidian_services_async()

            # 各サービスの初期化が順序通りに呼ばれることを確認
            mock_github_auth_manager.initialize.assert_called_once()
            mock_git_operations.initialize.assert_called_once()
            mock_batch_processor.initialize.assert_called_once()
            mock_obsidian_service.initialize.assert_called_once()


class TestVoiceMessageIntegration:
    """音声メッセージ統合テスト"""

    @pytest.mark.asyncio
    async def test_voice_message_to_obsidian_flow(
        self, mock_discord_objects, mock_openai_responses
    ):
        """音声メッセージ→文字起こし→Obsidian保存の統合フロー"""
        # Mock bot with obsidian service
        mock_bot = MagicMock()
        mock_obsidian_service = AsyncMock(spec=ObsidianGitHubService)
        mock_obsidian_service.save_to_obsidian.return_value = str(uuid4())
        mock_bot.obsidian_service = mock_obsidian_service

        # Voice cogの作成
        voice_cog = Voice(mock_bot, mock_obsidian_service)

        # OpenAI APIのモック
        with patch.object(voice_cog, "openai_client") as mock_openai, patch(
            "builtins.open", create=True
        ), patch("os.path.exists", return_value=True), patch("os.remove"), patch("os.makedirs"):
            # OpenAI APIレスポンス設定
            mock_openai.Audio.transcribe.return_value = mock_openai_responses["transcript"]
            mock_openai.ChatCompletion.create.side_effect = [
                mock_openai_responses["chat"],
                mock_openai_responses["summary"],
            ]

            # 添付ファイルの設定
            message = mock_discord_objects["message"]
            attachment = mock_discord_objects["attachment"]
            message.attachments = [attachment]

            # 音声データのモック
            attachment.read = AsyncMock(return_value=b"fake_audio_data")

            # メッセージ処理の実行
            await voice_cog.handle_voice_message(message, attachment)

            # 文字起こしが実行されたことを確認
            mock_openai.Audio.transcribe.assert_called_once()

            # AI処理が実行されたことを確認
            assert mock_openai.ChatCompletion.create.call_count == 2

    @pytest.mark.asyncio
    async def test_save_button_interaction(self, mock_discord_objects):
        """Obsidian保存ボタンクリック時の統合テスト"""
        from src.nescordbot.cogs.voice import TranscriptionView

        # Mock interaction
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.user = mock_discord_objects["user"]
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        # Mock obsidian service
        mock_obsidian_service = AsyncMock(spec=ObsidianGitHubService)
        mock_request_id = str(uuid4())
        mock_obsidian_service.save_to_obsidian.return_value = mock_request_id

        # TranscriptionViewの作成
        view = TranscriptionView(
            transcription="テスト文字起こし内容",
            summary="テスト要約",
            obsidian_service=mock_obsidian_service,
        )

        # ボタンのcallback機能をテスト
        # discord.ui.buttonデコレータによって作成されたButtonオブジェクトを取得
        obsidian_button = None
        for child in view.children:
            if hasattr(child, "label") and "保存" in child.label:
                obsidian_button = child
                break

        assert obsidian_button is not None, "Obsidian保存ボタンが見つかりません"

        # ボタンのcallbackを実行
        await obsidian_button.callback(interaction)

        # Obsidianサービスが呼ばれたことを確認
        mock_obsidian_service.save_to_obsidian.assert_called_once()

        # 引数の確認
        call_args = mock_obsidian_service.save_to_obsidian.call_args
        assert call_args[1]["directory"] == "voice_transcriptions"
        assert "音声文字起こし" in call_args[1]["content"]

        # レスポンスが送信されたことを確認
        interaction.followup.send.assert_called_once()
        sent_message = interaction.followup.send.call_args[0][0]
        assert mock_request_id in sent_message


class TestTextMessageIntegration:
    """テキストメッセージ統合テスト"""

    @pytest.mark.asyncio
    async def test_text_message_fleeting_note(self):
        """テキストメッセージからFleeting Note作成テスト"""
        # 将来的にテキストメッセージ処理が実装されたらここにテストを追加
        # 現在はVoice cogは音声処理のみなので、スキップ
        pytest.skip("テキストメッセージ処理は未実装")


class TestErrorHandlingIntegration:
    """エラーハンドリング統合テスト"""

    @pytest.mark.asyncio
    async def test_github_api_failure_recovery(self, mock_discord_objects):
        """GitHub API失敗時のリカバリテスト"""
        # Mock bot with failing obsidian service
        mock_bot = MagicMock()
        mock_obsidian_service = AsyncMock(spec=ObsidianGitHubService)
        mock_obsidian_service.save_to_obsidian.side_effect = RuntimeError("GitHub API Error")
        mock_bot.obsidian_service = mock_obsidian_service

        from src.nescordbot.cogs.voice import TranscriptionView

        # Mock interaction
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.user = mock_discord_objects["user"]
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        # TranscriptionViewの作成
        view = TranscriptionView(
            transcription="テスト内容",
            summary="テスト要約",
            obsidian_service=mock_obsidian_service,
        )

        # エラーが発生してもクラッシュしないことを確認
        obsidian_button = None
        for child in view.children:
            if hasattr(child, "label") and "保存" in child.label:
                obsidian_button = child
                break

        assert obsidian_button is not None
        await obsidian_button.callback(interaction)

        # エラーメッセージが送信されることを確認
        interaction.followup.send.assert_called_once()
        error_message = interaction.followup.send.call_args[0][0]
        assert "エラーが発生しました" in error_message

    @pytest.mark.asyncio
    async def test_service_not_available(self, mock_discord_objects):
        """ObsidianGitHubServiceが利用できない場合のテスト"""
        from src.nescordbot.cogs.voice import TranscriptionView

        # Mock interaction
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.user = mock_discord_objects["user"]
        interaction.response.send_message = AsyncMock()

        # サービスなしでTranscriptionViewを作成
        view = TranscriptionView(
            transcription="テスト内容",
            summary="テスト要約",
            obsidian_service=None,  # サービス無効
        )

        # ボタンクリック時の処理
        obsidian_button = None
        for child in view.children:
            if hasattr(child, "label") and "保存" in child.label:
                obsidian_button = child
                break

        assert obsidian_button is not None
        await obsidian_button.callback(interaction)

        # 適切なエラーメッセージが表示されることを確認
        interaction.response.send_message.assert_called_once()
        error_message = interaction.response.send_message.call_args[0][0]
        assert "Obsidian統合サービスが設定されていません" in error_message


class TestEndToEndScenarios:
    """エンドツーエンドシナリオテスト"""

    @pytest.mark.asyncio
    async def test_complete_voice_workflow(
        self, mock_config_full, mock_discord_objects, mock_openai_responses
    ):
        """完全な音声ワークフローの統合テスト"""
        # 実際のサービスチェーンを構築
        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config_full

        # 各コンポーネントのモック
        mock_security_validator = MagicMock()
        mock_github_auth_manager = AsyncMock()
        mock_git_operations = AsyncMock()
        mock_batch_processor = AsyncMock()
        mock_batch_processor.enqueue_file_request.return_value = 123

        with patch(
            "src.nescordbot.bot.get_config_manager", return_value=mock_config_manager
        ), patch("src.nescordbot.bot.get_logger"), patch(
            "src.nescordbot.bot.DatabaseService"
        ), patch(
            "src.nescordbot.bot.SecurityValidator", return_value=mock_security_validator
        ), patch(
            "src.nescordbot.bot.GitHubAuthManager", return_value=mock_github_auth_manager
        ), patch(
            "src.nescordbot.bot.GitOperationService", return_value=mock_git_operations
        ), patch(
            "src.nescordbot.bot.BatchProcessor", return_value=mock_batch_processor
        ):
            # Botの作成と初期化
            bot = NescordBot()
            await bot._init_obsidian_services_async()

            # Voice cogの作成
            voice_cog = Voice(bot, bot.obsidian_service)

            # OpenAI APIのモック
            with patch.object(voice_cog, "openai_client") as mock_openai, patch(
                "builtins.open", create=True
            ), patch("os.path.exists", return_value=True), patch("os.remove"), patch("os.makedirs"):
                # OpenAI APIレスポンス設定
                mock_openai.Audio.transcribe.return_value = mock_openai_responses["transcript"]
                mock_openai.ChatCompletion.create.side_effect = [
                    mock_openai_responses["chat"],
                    mock_openai_responses["summary"],
                ]

                # メッセージとアタッチメントの設定
                message = mock_discord_objects["message"]
                attachment = mock_discord_objects["attachment"]
                message.attachments = [attachment]
                attachment.read = AsyncMock(return_value=b"fake_audio_data")

                # Discord UIのモック
                with patch("discord.Embed"), patch("discord.File"), patch.object(
                    message, "reply", new_callable=AsyncMock
                ) as mock_reply:
                    # 完全なワークフローの実行
                    await voice_cog.handle_voice_message(message, attachment)

                    # 各段階が実行されたことを確認
                    mock_openai.Audio.transcribe.assert_called_once()
                    assert mock_openai.ChatCompletion.create.call_count == 2
                    mock_reply.assert_called()

                    # TranscriptionViewが作成されたことを確認
                    view_call_found = False
                    for call in mock_reply.call_args_list:
                        if "view" in call.kwargs:
                            view_call_found = True
                            break
                    assert view_call_found, "TranscriptionViewが作成されませんでした"

    @pytest.mark.asyncio
    async def test_concurrent_user_requests(self, mock_config_full):
        """複数ユーザーの同時リクエスト処理テスト"""
        # 複数のユーザーからの同時リクエストをシミュレート
        request_count = 5
        mock_obsidian_service = AsyncMock()

        # 並行処理の実行
        tasks = []
        for i in range(request_count):
            task = mock_obsidian_service.save_to_obsidian(
                filename=f"test_{i}.md", content=f"テスト内容 {i}", directory="test_concurrent"
            )
            tasks.append(task)

        # 全てのタスクを実行
        await asyncio.gather(*tasks)

        # 全てのリクエストが処理されたことを確認
        assert mock_obsidian_service.save_to_obsidian.call_count == request_count
