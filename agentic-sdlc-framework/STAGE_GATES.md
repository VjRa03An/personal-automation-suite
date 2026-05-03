# Stage Gate Process — Agentic SDLC

## Overview

8 formal gates from Ideation to Launch. Each gate has defined exit criteria, 
RAPID decision owners, an AI agent role, and three possible outcomes.

| Gate | Name | Stage | Decides |
|------|------|-------|---------|
| G0 | Ideation & Strategy | Before roadmap commitment | PM |
| G1 | UX & Requirements | Before architecture begins | PM |
| G2 | Architecture | Before development begins | TPM |
| G3 | Data & ML Readiness | Before model training (ML only) | Data Eng |
| G4 | Build & Code Review | Before QA and testing | EM |
| G5 | QA & Validation | Before deployment approval | EM |
| G6 | Deployment Approval | Before production release | TPM |
| G7 | Launch & Post-Launch | 30-day post-launch review | TPM |

---

## Gate Outcomes

Every gate has exactly three outcomes:

- **Go** — exit criteria met, proceed to next stage
- **Iterate** — gaps identified, return to fix before re-review
- **Stop** — fundamental issue, project paused or cancelled

---

## G0 — Ideation & Strategy
**Before roadmap commitment**

### Exit Criteria
- Problem statement validated with user research
- Strategic fit confirmed against company OKRs
- Preliminary tech and data feasibility assessed
- Regulatory landscape reviewed by CDO/Gov
- Competitive landscape summarized by Planning Agent

### RAPID Owners
- Decide: PM | Agree: TPM, CDO/Gov | Input: EM, Tech Arch, UX

### Agent Role
Planning Agent — synthesizes market signals, competitor data, strategic context

### Outcomes
- Go: Approved for roadmap inclusion
- Iterate: Return for additional research or scoping
- Stop: Not strategically viable — shelved

---

## G1 — UX & Requirements
**Before architecture begins**

### Exit Criteria
- User research completed, personas defined
- UX prototypes reviewed and approved
- Functional and non-functional requirements documented
- Data requirements and PII scope identified

### RAPID Owners
- Decide: PM | Agree: UX, TPM, CDO/Gov | Input: EM, Data Eng, ML Eng

### Agent Role
UX Agent — generates wireframe variants and design options for human review

### Outcomes
- Go: Requirements baselined, architecture can begin
- Iterate: Revisit UX or requirements gaps
- Stop: User need not confirmed — pause project

---

## G2 — Architecture
**Before development begins**

### Exit Criteria
- System architecture reviewed and approved
- Technology stack finalized
- Security and privacy architecture signed off
- Technical risks logged with mitigations

### RAPID Owners
- Decide: TPM | Agree: EM, Tech Arch, CDO/Gov | Input: Data Eng, ML Eng, MLOps

### Agent Role
Planning Agent — proposes architecture options and flags risks for human review

### Outcomes
- Go: Architecture approved, dev team can begin
- Iterate: Redesign specific components or address risks
- Stop: Technical feasibility not established — halt

---

## G3 — Data & ML Readiness ★
**ML projects only — before model training**

### Exit Criteria
- Data pipeline validated end-to-end
- Data quality metrics meet defined thresholds
- PII handling and consent compliance verified
- Bias assessment completed on training data
- Feature engineering reviewed by ML Eng

### RAPID Owners
- Decide: Data Eng | Agree: ML Eng, CDO/Gov | Input: TPM, Tech Arch, MLOps

### Agent Role
Data Agent — performs ingestion, cleaning, profiling; surfaces quality issues

### Outcomes
- Go: Data ready, model training can begin
- Iterate: Fix data quality or governance gaps
- Stop: Data insufficient or non-compliant — halt

---

## G4 — Build & Code Review
**Before QA and testing**

### Exit Criteria
- Code complete against acceptance criteria
- Code review passed — Tech Arch sign-off
- Security scan completed, critical findings resolved
- Unit test coverage meets threshold
- Technical documentation updated

### RAPID Owners
- Decide: EM | Agree: Tech Arch | Input: TPM, ML Eng

### Agent Role
Code Agent — writes and iterates code; Test Agent flags coverage gaps

### Outcomes
- Go: Code approved, QA testing can begin
- Iterate: Address code review findings or coverage gaps
- Stop: Fundamental architecture issues found — redesign

---

## G5 — QA & Validation
**Before deployment approval**

### Exit Criteria
- All critical and high severity bugs resolved
- Integration and regression tests passed
- Performance benchmarks met
- ML model evaluation metrics approved (if applicable)
- UAT sign-off from PM and UX

### RAPID Owners
- Decide: EM | Agree: TPM, PM, UX | Input: MLOps, CDO/Gov

### Agent Role
Test Agent — runs full regression suite, surfaces failures and coverage gaps

### Outcomes
- Go: QA passed, deployment approval process begins
- Iterate: Fix outstanding bugs or performance issues
- Stop: Quality bar not met — return to build

---

## G6 — Deployment Approval
**Before production release**

### Exit Criteria
- Rollback plan documented and tested
- Runbook and on-call documentation complete
- CDO/Gov final compliance sign-off obtained
- MLOps model serving infrastructure validated
- Stakeholder launch communication prepared

### RAPID Owners
- Decide: TPM | Agree: EM, MLOps, CDO/Gov | Input: PM, Tech Arch

### Agent Role
Deploy Agent — executes CI/CD pipeline; Monitor Agent confirms pre-launch health

### Outcomes
- Go: Approved for production deployment
- Iterate: Resolve compliance or infrastructure gaps
- Stop: Regulatory or critical risk — do not deploy

---

## G7 — Launch & Post-Launch
**30-day post-launch review**

### Exit Criteria
- Key success metrics tracking against targets
- No critical incidents in first 30 days
- Model drift within acceptable bounds (ML)
- Data governance audit completed
- Lessons learned documented in GitHub repo

### RAPID Owners
- Decide: TPM | Agree: PM, CDO/Gov, MLOps | Input: EM, Tech Arch, ML Eng

### Agent Role
Monitor Agent — tracks metrics, flags drift and anomalies; Deploy Agent manages rollback if needed

### Outcomes
- Go: Project healthy — move to steady-state ops
- Iterate: Targeted fixes or model retraining required
- Stop: Rollback and root-cause investigation

---

## Key Governance Principles

1. **Agents perform, humans decide** — agents never hold Decide or Gate
2. **Gates are non-negotiable** — CDO/Gov clearance is a hard stop, not a suggestion
3. **TPM owns the most gates** — G2, G6, G7 — reflecting cross-functional risk ownership
4. **G3 is ML-only** — skip entirely for non-ML projects
5. **G7 closes the loop** — post-launch is a formal gate, not an afterthought

★ G3 applies to ML/data-intensive projects only
