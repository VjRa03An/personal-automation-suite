# RAPID Matrix — Agentic SDLC

## Role Definitions

| Letter | Role | Description |
|--------|------|-------------|
| D | Decide | Final decision authority — humans only, never agents |
| A | Agree | Must approve before work proceeds |
| P | Perform | Does the work — AI agents typically hold this |
| I | Input | Provides information, not in decision path |
| R | Recommend | Proposes options for human review |
| G | Gate | Hard CDO/Gov stop — non-negotiable clearance required |

---

## Human Roles
- **PM** — Product Manager
- **TPM** — Technical Program Manager
- **EM** — Engineering Manager
- **Tech Arch** — Technical Architect
- **UX** — UX/Design Team
- **Data Eng** — Data Engineer
- **ML Eng** — Machine Learning Engineer
- **MLOps** — ML Operations Engineer
- **CDO/Gov** — Chief Data Officer / Data Governance

## Agent Roles
- **Planning Agent** — synthesizes requirements, architecture options, market signals
- **UX Agent** — generates wireframes and design variants
- **Data Agent** — ingestion, cleaning, profiling, quality checks
- **Code Agent** — writes and iterates on code
- **Test Agent** — runs regression suites, flags coverage gaps
- **Deploy Agent** — executes CI/CD pipelines, manages rollback
- **Monitor Agent** — tracks metrics, flags drift and anomalies

---

## Matrix

| Stage | PM | TPM | EM | Tech Arch | UX | Data Eng | ML Eng | MLOps | CDO/Gov | Plan Agent | UX Agent | Data Agent | Code Agent | Test Agent | Deploy Agent | Mon Agent |
|-------|----|-----|----|-----------|----|----------|--------|-------|---------|------------|----------|------------|------------|------------|--------------|-----------|
| 0. Roadmap | D | A | I | I | I | — | — | — | G | R | — | — | — | — | — | I |
| 1. UX & Design | A | I | I | I | D | — | — | — | I | — | P | — | — | — | — | — |
| 2. Requirements | D | A | I | I | A | I | I | — | A | P | — | — | — | — | — | — |
| 3. Architecture | I | D | A | A | — | I | I | I | A | R | — | I | I | — | — | — |
| 4. Data Pipeline ★ | — | A | I | I | — | D | A | I | G | — | — | P | — | — | — | — |
| 5. Model Training ★ | I | A | I | I | — | I | D | A | G | — | — | I | — | R | — | — |
| 6. Code Generation | — | I | D | A | — | — | I | — | — | — | — | — | P | I | — | — |
| 7. Testing & QA | — | A | D | I | — | — | I | I | I | — | — | — | I | P | — | — |
| 8. Deployment | I | D | A | I | — | — | I | A | G | — | — | — | — | R | P | I |
| 9. Monitoring | I | D | A | I | — | — | I | A | A | — | — | — | — | — | R | P |

★ ML/data-intensive projects only

---

## Key Observations

- **TPM holds Decide** on Architecture (3), Deployment (8), and Monitoring (9) — the highest cross-functional risk stages
- **PM holds Decide** on Roadmap (0) and Requirements (2) — the strategic and scope-defining stages
- **EM holds Decide** on Code Generation (6) and Testing (7) — the technical execution stages
- **CDO/Gov holds Gate** at Stages 0, 4, 5, and 8 — data and compliance critical points
- **Agents never hold D or G** — humans retain all final decision authority
