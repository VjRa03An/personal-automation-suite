# Job Agent — Daily Job Digest

## What it does
Runs every morning at 8 AM, scrapes job boards, scores listings against my TPM profile using Claude AI, and emails a digest with the best matches.

## Stats
- Scrapes ~130+ jobs daily
- Scores each job 1-10 against profile
- Emails matches scoring 6+

## Setup
- Python 3.9
- Anthropic Claude API (`ANTHROPIC_API_KEY`)
- Gmail SMTP for email delivery
- macOS launchd for scheduling (`com.jobagent.daily`)

## Lessons Learned
- launchd requires absolute file paths — relative paths fail silently
- Environment variables must be explicitly set in the plist `EnvironmentVariables` block
- Mac must be sleeping (not shut down) for launchd wake schedule to work
