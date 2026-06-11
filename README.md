# 🤖 Personal Automation Suite

> *A collection of AI-powered agents built to solve real operational problems — not demos, not tutorials. Each agent here was built to automate something I was actually doing manually.*

---

## About This Repo

I'm a Technical Program Director with 18+ years leading large-scale engineering delivery. This repo is where I build.

Over the past year I've been applying AI tooling to the same operational problems I've managed by hand for years — status reporting, job search tracking, financial monitoring, inbox management, and system organisation. These agents run on real data, solve real problems, and reflect how I think about AI: as a productivity tool in service of outcomes, not an end in itself.

**Stack:** Python · HTML · GitHub Actions · Claude API · GitHub Actions automation

---

## Agents & Projects

### 🏗️ [`agentic-sdlc-framework`](./agentic-sdlc-framework)
**AI-assisted SDLC governance framework with executive reporting**

Built for CTO and CPO audiences. Automates the generation of executive-level delivery decks, synthesising programme status, risk posture, and roadmap health into structured briefing documents. Reflects the same governance work I've done at scale — just automated.

- Generates executive deck outputs for CTO / CPO review cycles
- Structures delivery signals into decision-ready formats
- Built on Python + Claude API

---

### 💱 [`forex-agent`](./forex-agent)
**Automated forex monitoring with daily digest**

Monitors foreign exchange rates and delivers a structured daily digest. Built to replace a manual daily check — now runs on a schedule and sends a summary automatically.

- Tracks configurable currency pairs
- Sends automated digest via email
- Runs on GitHub Actions schedule

---

### ⛽ [`gas-tracker-pwa`](./gas-tracker-pwa)
**Progressive Web App for local gas price tracking**

A lightweight PWA that tracks gas prices across San Jose and surrounding areas, with road trip planning utility. Built as a practical tool for a real daily use case.

- Tracks local gas prices in real time
- Road trip cost estimation
- PWA — installable, works offline

---

### 📧 [`gmail-cleanup`](./gmail-cleanup)
**Automated Gmail inbox management agent**

Automates inbox triage — categorising, archiving, and flagging emails based on configurable rules. Runs on a schedule via GitHub Actions with deduplication across runs.

- Automated inbox categorisation and cleanup
- Seen-jobs deduplication logic across runs
- GitHub Actions powered, runs daily

---

### 🔍 [`job-agent`](./job-agent)
**AI-powered job search automation agent**

Automates job search monitoring across sources, deduplicates listings across runs, and delivers a structured daily digest of relevant opportunities. The agent that's helping manage my own search — built and used in parallel.

- Scrapes and deduplicates job listings across runs
- Filters by role, location, and seniority
- Delivers structured daily digest

---

### 📋 [`job-applications`](./job-applications)
**Application tracking and gap analysis**

Tracks active job applications, notes gaps between JD requirements and resume content, and maintains a structured pipeline view. Companion to the job-agent.

- Application status tracking
- JD gap notes and analysis
- Formatted output for review

---

### 🗂️ [`mac-organizer`](./mac-organizer)
**Automated Mac file and system organiser**

Automates file organisation, cleanup of duplicate files, and system tidying on macOS. Includes daily cleanup scripts managed via GitHub Actions.

- Automated file deduplication and organisation
- Configurable cleanup rules
- macOS native, Python-based

---

### 📊 [`tracker.html`](./tracker.html)
**Job search and pipeline tracker (browser-based)**

A standalone HTML tracker for managing the full job search pipeline — applications, status, follow-ups, and notes. Built alongside the Cowork pipeline and master resume workflow.

- Single-file, no dependencies
- Full pipeline view in the browser
- Works locally, no server needed

---

## Why This Exists

Every agent here started with the same question: *what am I doing manually that I shouldn't be?*

Status reporting. Inbox triage. Job monitoring. Financial tracking. System cleanup. These are solvable problems — and solving them with AI tooling is the same discipline I apply to programme delivery at work: identify the bottleneck, automate the repeatable, focus human attention on the judgement calls that actually matter.

This is a working repo, not a portfolio piece. Commits are frequent, agents evolve, and new ones get added when a new manual process becomes worth automating.

---

## Setup

Each agent lives in its own folder with its own README and setup instructions. Start with whichever is most relevant to you.

```bash
git clone https://github.com/VjRa03An/personal-automation-suite.git
cd personal-automation-suite
```

Most agents require:
- Python 3.9+
- A `.env` file with relevant API keys (see each agent's README)
- GitHub Actions enabled (for scheduled agents)

---

## Connect

**Venkatesh Subramanyam**
[linkedin.com/in/venkatesh-coimbatore-subramanyam](https://www.linkedin.com/in/venkatesh-coimbatore-subramanyam)
