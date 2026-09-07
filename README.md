# Euroleague Boxscore Scraper (GitHub Actions)

## Setup

1. Create a new GitHub repo (public or private both work).
2. Add these files to it, preserving the folder structure:
   - `scrape_euroleague.py`
   - `requirements.txt`
   - `.github/workflows/scrape-euroleague.yml`
3. Commit and push to GitHub.
4. Go to the **Actions** tab of your repo → select **"Scrape Euroleague Boxscores"**
   → click **"Run workflow"**.

## What happens

- The workflow checks out your repo, installs dependencies, and runs the script.
- The script writes to `data/euroleague2026draft.db`, resuming from any games
  already scraped in a previous run (tracked in the `scraped_games` table).
- When it finishes, the workflow:
  - Uploads the DB as a downloadable **build artifact** (Actions run page →
    bottom of the page → Artifacts).
  - Commits the updated DB file back into the repo, so the next run can
    resume and you always have the latest copy in `data/` on the `main` branch.

## Getting the DB onto your laptop

Either:
- Download it from the workflow run's **Artifacts** section (zipped), or
- `git pull` your repo locally after a run, since the DB gets committed back.

## Re-running / scheduling

- Manual: just click "Run workflow" again anytime (e.g. after each round of games).
- Automatic: uncomment the `schedule:` block in the workflow file to run on
  a cron schedule instead of only manually.

## Notes

- GitHub-hosted runners have per-job time limits (`timeout-minutes: 60` set
  here); the full 380-game scrape should take a few minutes, well within that.
- If Cloudflare ever does rate-limit a run mid-way, just re-run the workflow —
  the `scraped_games` table means it picks up where it left off rather than
  starting over.
- Since GitHub Action runner IPs are shared/rotating cloud IPs, it's possible
  Cloudflare treats them more cautiously than your home IP. If you see more
  1015s than you did locally, try increasing `BASE_DELAY` in the script
  slightly (e.g. to 0.6-0.8s).
