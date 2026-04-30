# personal-automation-suite# Personal Automation Suite

A collection of daily automation agents running on macOS.

## Projects

### 1. Job Agent (`job_agent_daily.py`)
Daily job scraper and scorer. Scrapes job boards, scores listings against my profile using Claude AI, and emails a digest every morning at 8 AM.

### 2. Gmail Cleanup Agent (coming soon)
Daily Gmail cleanup — deletes old promos, archives unread emails older than 90 days, purges spam.

### 3. Mac Hard Drive Cleanup Agent (coming soon)
Automated disk cleanup — removes junk files, old downloads, and frees up space daily.

## Setup
- macOS with launchd for scheduling
- Python 3.9
- Anthropic Claude API
