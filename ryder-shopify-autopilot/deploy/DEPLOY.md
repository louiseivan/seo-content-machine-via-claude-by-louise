# Run the pipeline on a small cloud server

The scheduled tasks in the Claude desktop app only run while the Mac is on.
This kit runs the same three jobs on a small Linux server with cron and
headless Claude Code (`claude -p`), on Tokyo time.

| Job | When (Asia/Tokyo) | Prompt |
| --- | --- | --- |
| Drafter | Weekdays 06:45, 12:15, 18:15 | `prompts/drafter.md` |
| Publisher (Shopify autopilot) | Daily 07:45, 13:45, 19:45 | `prompts/autopilot.md` |
| Index watch | Daily 00:00 | `prompts/index-watch.md` |

A lock file stops two jobs from running at once, so a slow drafter run
makes the publisher wait rather than race it.

## What you need

- A server: on DigitalOcean, a Basic droplet with **2 GB RAM** (about
  12 USD/month) running Ubuntu 24.04. The 1 GB droplet (about 6 USD) also
  works because setup.sh adds swap, but runs are slower. Hetzner Cloud CX22
  (about 4-5 EUR/month) is the cheaper alternative. Any region; the clock is
  set to Tokyo.
- Your SSH key added when you create the server.
- A Claude login for the server: run `claude setup-token` on the Mac (uses
  your Claude subscription) or create an API key in the Anthropic Console.

## Steps

1. **Create the server** in the provider's dashboard: Ubuntu 24.04, CX22,
   add your SSH key. Note its IP address.

2. **Install everything** (2-3 minutes):
   ```bash
   ssh root@SERVER_IP 'curl -fsSL https://raw.githubusercontent.com/louiseivan/seo-content-machine-via-claude-by-louise/main/ryder-shopify-autopilot/deploy/setup.sh | bash'
   ```

3. **Copy secrets and the drafts archive** from the Mac (git never carries
   these):
   ```bash
   ~/CodingStudio/ryder-shopify-autopilot/deploy/push-from-mac.sh ryder@SERVER_IP
   ```

4. **Give the server its Claude login.** On the server as `ryder`, create
   `~/.ryder-claude.env` with one line, either
   `CLAUDE_CODE_OAUTH_TOKEN=...` (from `claude setup-token`) or
   `ANTHROPIC_API_KEY=...`, then `chmod 600 ~/.ryder-claude.env`.
   Type the value yourself; don't paste it into a chat.

5. **Dry run** (no Notion writes, no publishing):
   ```bash
   ssh ryder@SERVER_IP 'cd ~/CodingStudio/ryder-shopify-autopilot && python3 notion_topic_intake.py --dry-run --output /tmp/preview.json && echo NOTION_OK'
   ```
   Then one real drafter run, watched:
   ```bash
   ssh ryder@SERVER_IP '~/CodingStudio/ryder-shopify-autopilot/deploy/run-task.sh drafter; tail -40 ~/ryder-logs/drafter-*.log'
   ```

6. **Switch over.** Turn the three Mac tasks off first
   (`ryder-article-drafter`, `ryder-article-drafter-morning`,
   `ryder-shopify-autopilot` in the Claude app's Scheduled sidebar), then
   install cron on the server:
   ```bash
   ssh ryder@SERVER_IP 'crontab ~/CodingStudio/ryder-shopify-autopilot/deploy/crontab.txt && crontab -l'
   ```
   Running both at once would draft and publish twice.

## Day to day

- Logs: `~/ryder-logs/<job>-<date>.log` on the server, kept 30 days.
  Bring them, plus new drafts and review notes, back to the Mac with
  `deploy/pull-to-mac.sh ryder@SERVER_IP`.
- Changing a prompt: edit `deploy/prompts/*.md`, commit and push. Each run
  does `git pull --ff-only` first.
- Pausing: `ssh ryder@SERVER_IP 'crontab -r'`. Resume with step 6.

## Notes

- Claude runs with `--permission-mode acceptEdits` and an explicit tool
  list (Bash, file tools, web search/fetch, skills). It has shell access on
  this server, so keep only this pipeline on it.
- The `global-humanized-skill-louise` skill lives in your claude.ai account
  and isn't available on the server; the drafter falls back to
  `humanize-writing` plus the voice rules in `RYDER_CONTENT_SYSTEM_PROMPT.md`.
- Prompts in `prompts/` are copies of the desktop scheduled tasks with
  `{{ROOT}}` in place of the Mac path. Keep the two in step if you change
  either.
