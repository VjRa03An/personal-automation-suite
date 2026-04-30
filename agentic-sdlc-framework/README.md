# Agentic SDLC Framework

A comprehensive framework for managing AI-agent-assisted software development — from Ideation to Launch.

## Contents

- `agentic_sdlc_framework.pptx` — Full presentation deck (17 slides)
- `RAPID_MATRIX.md` — RAPID roles matrix across all 10 stages
- `STAGE_GATES.md` — Stage gate process with exit criteria and outcomes

## Framework Overview

### What is Agentic SDLC?
A software development lifecycle where AI agents actively participate in and automate key stages — while humans retain all decision authority.

### The 10 Stages
| Stage | Name | Type |
|-------|------|------|
| 0 | Product Roadmap | Strategic anchor |
| 1 | UX & Design | Human experience anchor |
| 2 | Requirements | All projects |
| 3 | Architecture | All projects |
| 4 | Data Pipeline | ML projects only |
| 5 | Model Training | ML projects only |
| 6 | Code Generation | All projects |
| 7 | Testing & QA | All projects |
| 8 | Deployment | All projects |
| 9 | Monitoring | All projects |

### RAPID Decision Framework
| Letter | Role | In Agentic SDLC |
|--------|------|-----------------|
| R | Recommend | Planning/Code Agents propose options |
| A | Agree | Must approve before proceeding |
| P | Perform | AI Agents execute the work |
| I | Input | Provides information, not in decision path |
| D | Decide | Final authority — humans only, never agents |
| G | Gate | Hard CDO/Gov stop — non-negotiable |

### Key Governance Principles
- Agents perform, humans decide — agents never hold D or G
- Gates are non-negotiable — CDO/Gov must clear before proceeding
- TPM is the orchestration layer — holds Decide on Architecture, Deployment & Monitoring
- Data Governance is horizontal — gates at Stages 0, 4, 5, 8, 9

### The 8 Stage Gates
| Gate | Name | Decides |
|------|------|---------|
| G0 | Ideation & Strategy | PM |
| G1 | UX & Requirements | PM |
| G2 | Architecture | TPM |
| G3 | Data & ML Readiness | Data Eng |
| G4 | Build & Code Review | EM |
| G5 | QA & Validation | EM |
| G6 | Deployment Approval | TPM |
| G7 | Launch & Post-Launch | TPM |

## Built With
- Framework developed: April 2026
- Tools: Claude AI, PptxGenJS
