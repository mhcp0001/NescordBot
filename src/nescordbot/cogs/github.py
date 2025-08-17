"""GitHub integration commands for NescordBot."""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from ..services.github import GitHubService

logger = logging.getLogger(__name__)


class GitHubCog(commands.Cog):
    """Cog for GitHub integration commands."""

    def __init__(self, bot: commands.Bot, github_service: Optional[GitHubService] = None):
        """Initialize GitHub cog.

        Args:
            bot: Discord bot instance
            github_service: GitHub service instance
        """
        self.bot = bot
        self.github_service = github_service

    @app_commands.command(name="gh-issue-create", description="Create a new GitHub issue")
    @app_commands.describe(
        title="Issue title",
        body="Issue description (optional)",
        labels="Comma-separated labels (optional)",
    )
    async def create_issue(
        self,
        interaction: discord.Interaction,
        title: str,
        body: Optional[str] = None,
        labels: Optional[str] = None,
    ) -> None:
        """Create a new GitHub issue.

        Args:
            interaction: Discord interaction
            title: Issue title
            body: Issue description
            labels: Comma-separated labels
        """
        if not self.github_service:
            await interaction.response.send_message(
                "❌ GitHub integration is not configured.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Parse labels if provided
            label_list = [label.strip() for label in labels.split(",")] if labels else None

            # Create issue
            issue_data = await self.github_service.create_issue(
                title=title, body=body or "", labels=label_list
            )

            # Create embed response
            embed = discord.Embed(
                title="✅ Issue Created",
                description=(
                    f"[#{issue_data['number']}: {issue_data['title']}]"
                    f"({issue_data['html_url']})"
                ),
                color=discord.Color.green(),
            )
            embed.add_field(name="Number", value=f"#{issue_data['number']}", inline=True)
            embed.add_field(name="State", value=issue_data["state"], inline=True)
            if issue_data.get("labels"):
                label_names = [label["name"] for label in issue_data["labels"]]
                embed.add_field(name="Labels", value=", ".join(label_names), inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Issue #{issue_data['number']} created by {interaction.user}")

        except Exception as e:
            logger.error(f"Failed to create issue: {e}")
            await interaction.followup.send(f"❌ Failed to create issue: {str(e)}", ephemeral=True)

    @app_commands.command(name="gh-issue-list", description="List GitHub issues")
    @app_commands.describe(
        state="Issue state (open/closed/all)",
        labels="Filter by comma-separated labels",
        limit="Maximum number of issues to show (1-10)",
    )
    @app_commands.choices(
        state=[
            app_commands.Choice(name="Open", value="open"),
            app_commands.Choice(name="Closed", value="closed"),
            app_commands.Choice(name="All", value="all"),
        ]
    )
    async def list_issues(
        self,
        interaction: discord.Interaction,
        state: str = "open",
        labels: Optional[str] = None,
        limit: int = 5,
    ) -> None:
        """List GitHub issues.

        Args:
            interaction: Discord interaction
            state: Issue state filter
            labels: Label filter
            limit: Maximum number of issues
        """
        if not self.github_service:
            await interaction.response.send_message(
                "❌ GitHub integration is not configured.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=False)

        try:
            # Validate limit
            limit = min(max(1, limit), 10)

            # Get issues
            issues = await self.github_service.list_issues(
                state=state, labels=labels, per_page=limit
            )

            if not issues:
                await interaction.followup.send(f"No {state} issues found.")
                return

            # Create embed
            embed = discord.Embed(
                title=f"📋 GitHub Issues ({state.capitalize()})",
                color=discord.Color.blue(),
            )

            for issue in issues[:limit]:
                labels_str = ""
                if issue.get("labels"):
                    label_names = [f"`{label['name']}`" for label in issue["labels"]]
                    labels_str = " " + " ".join(label_names)

                value = f"[View Issue]({issue['html_url']}){labels_str}"
                embed.add_field(
                    name=f"#{issue['number']}: {issue['title'][:50]}",
                    value=value,
                    inline=False,
                )

            embed.set_footer(text=f"Showing {len(issues[:limit])} of {len(issues)} issues")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Failed to list issues: {e}")
            await interaction.followup.send(f"❌ Failed to list issues: {str(e)}", ephemeral=True)

    @app_commands.command(name="gh-pr-list", description="List GitHub pull requests")
    @app_commands.describe(
        state="PR state (open/closed/all)",
        limit="Maximum number of PRs to show (1-10)",
    )
    @app_commands.choices(
        state=[
            app_commands.Choice(name="Open", value="open"),
            app_commands.Choice(name="Closed", value="closed"),
            app_commands.Choice(name="All", value="all"),
        ]
    )
    async def list_pull_requests(
        self,
        interaction: discord.Interaction,
        state: str = "open",
        limit: int = 5,
    ) -> None:
        """List GitHub pull requests.

        Args:
            interaction: Discord interaction
            state: PR state filter
            limit: Maximum number of PRs
        """
        if not self.github_service:
            await interaction.response.send_message(
                "❌ GitHub integration is not configured.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=False)

        try:
            # Validate limit
            limit = min(max(1, limit), 10)

            # Get PRs
            prs = await self.github_service.list_pull_requests(state=state, per_page=limit)

            if not prs:
                await interaction.followup.send(f"No {state} pull requests found.")
                return

            # Create embed
            embed = discord.Embed(
                title=f"🔀 GitHub Pull Requests ({state.capitalize()})",
                color=discord.Color.purple(),
            )

            for pr in prs[:limit]:
                # Status emoji
                if pr.get("draft"):
                    status = "📝 Draft"
                elif pr.get("merged"):
                    status = "✅ Merged"
                elif state == "closed":
                    status = "❌ Closed"
                else:
                    status = "🟢 Open"

                value = f"[View PR]({pr['html_url']}) | {status}"
                if pr.get("user"):
                    value += f" | By @{pr['user']['login']}"

                embed.add_field(
                    name=f"#{pr['number']}: {pr['title'][:50]}",
                    value=value,
                    inline=False,
                )

            embed.set_footer(text=f"Showing {len(prs[:limit])} of {len(prs)} PRs")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Failed to list PRs: {e}")
            await interaction.followup.send(f"❌ Failed to list PRs: {str(e)}", ephemeral=True)

    @app_commands.command(name="gh-rate-limit", description="Check GitHub API rate limit")
    async def check_rate_limit(self, interaction: discord.Interaction) -> None:
        """Check GitHub API rate limit status.

        Args:
            interaction: Discord interaction
        """
        if not self.github_service:
            await interaction.response.send_message(
                "❌ GitHub integration is not configured.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Get rate limit info
            rate_info = await self.github_service.get_rate_limit()

            # Create embed
            embed = discord.Embed(
                title="📊 GitHub API Rate Limit",
                color=discord.Color.green()
                if rate_info.remaining > 100
                else discord.Color.orange(),
            )

            # Calculate percentage
            percentage = (rate_info.remaining / rate_info.limit) * 100 if rate_info.limit > 0 else 0

            # Create progress bar
            bar_length = 20
            filled = int(bar_length * percentage / 100)
            bar = "█" * filled + "░" * (bar_length - filled)

            embed.add_field(name="Usage", value=f"{bar} {percentage:.1f}%", inline=False)
            embed.add_field(
                name="Remaining", value=f"{rate_info.remaining}/{rate_info.limit}", inline=True
            )
            embed.add_field(name="Used", value=str(rate_info.used), inline=True)
            embed.add_field(
                name="Reset Time",
                value=f"<t:{int(rate_info.reset.timestamp())}:R>",
                inline=True,
            )

            # Add warning if low
            if rate_info.remaining < 100:
                embed.set_footer(text="⚠️ Rate limit is low!")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Failed to check rate limit: {e}")
            await interaction.followup.send(
                f"❌ Failed to check rate limit: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="gh-repo-info", description="Get repository information")
    async def repo_info(self, interaction: discord.Interaction) -> None:
        """Get repository information.

        Args:
            interaction: Discord interaction
        """
        if not self.github_service:
            await interaction.response.send_message(
                "❌ GitHub integration is not configured.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=False)

        try:
            # Get repo info
            repo = await self.github_service.get_repository()

            # Create embed
            embed = discord.Embed(
                title=f"📁 {repo['full_name']}",
                description=repo.get("description", "No description"),
                url=repo["html_url"],
                color=discord.Color.blue(),
            )

            # Add fields
            embed.add_field(name="⭐ Stars", value=repo["stargazers_count"], inline=True)
            embed.add_field(name="🍴 Forks", value=repo["forks_count"], inline=True)
            embed.add_field(name="👁️ Watchers", value=repo["watchers_count"], inline=True)
            embed.add_field(name="🐛 Open Issues", value=repo["open_issues_count"], inline=True)
            embed.add_field(name="🌿 Default Branch", value=repo["default_branch"], inline=True)
            embed.add_field(name="🔒 Private", value="Yes" if repo["private"] else "No", inline=True)

            if repo.get("language"):
                embed.add_field(name="💻 Language", value=repo["language"], inline=True)

            if repo.get("license"):
                embed.add_field(name="📜 License", value=repo["license"]["name"], inline=True)

            # Set thumbnail
            if repo.get("owner", {}).get("avatar_url"):
                embed.set_thumbnail(url=repo["owner"]["avatar_url"])

            # Set footer
            created_at = discord.utils.parse_time(repo["created_at"])
            if created_at:
                embed.set_footer(text=f"Created on {created_at.strftime('%Y-%m-%d')}")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Failed to get repo info: {e}")
            await interaction.followup.send(f"❌ Failed to get repo info: {str(e)}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Set up the GitHub cog.

    Args:
        bot: Discord bot instance
    """
    # Try to get GitHub service from bot
    github_service = None
    if hasattr(bot, "github_service"):
        github_service = bot.github_service

    await bot.add_cog(GitHubCog(bot, github_service))
    logger.info("GitHub cog loaded")
