# COVENANT AI — Replit Agent Build Brief
### Agent-Native Syndicated Loan Origination & Servicing Platform
### (Vista Equity Partners Agentic AI Hackathon — Finastra Track)

---

## 1. APP OVERVIEW

**App name:** Covenant AI
**One-line description:** A multi-agent system that takes a commercial/syndicated loan from term sheet to closed, monitored deal — autonomously — with humans approving only the handful of decisions that actually carry risk.

**Core problem it solves:**
Commercial and syndicated lending today (the world Finastra's Loan IQ lives in) runs on human-driven workflows: a credit analyst reads financials, a compliance officer runs KYC/AML, a syndications desk manually calls lenders to build a book, a documentation team drafts the credit agreement, and covenant monitoring happens quarterly via spreadsheets email. Each handoff is slow, manual, and disconnected. Covenant AI replaces this chain with a coordinated network of specialist agents that do the work continuously, in parallel, with full auditability — cutting origination-to-close time and catching covenant breaches in near real time instead of a quarter late.

**Target user:**
Commercial/corporate banks, credit unions, and non-bank lenders who currently run syndicated or middle-market commercial lending on platforms like Finastra Loan IQ. Primary persona: a Head of Commercial Lending or Credit Risk Officer who wants faster deal velocity without adding headcount, and needs every agent decision to be explainable to an auditor or regulator.

**Why this is the self-disruption play:** Finastra just sold its core banking business specifically to sharpen focus on payments and lending. Loan IQ is the crown jewel of that remaining lending business. Covenant AI is "the startup that would eat Loan IQ" — built agents-first, with no legacy workflow-screen baggage.

---

## 2. FULL FEATURE LIST

### Core (must have, build these first)
1. **Deal Intake** — user pastes/uploads a term sheet or fills a short form describing a loan request (borrower, amount, purpose, tenor, structure).
2. **Origination Agent** — parses the intake into structured deal terms (amount, tenor, pricing, covenants requested, collateral).
3. **Credit Risk Agent** — ingests mock borrower financials, produces a risk score, leverage ratios, and a recommended covenant package with plain-English rationale.
4. **Know-Your-Agent (KYA) Compliance Agent** — runs a simulated KYC/AML check on the borrower AND, distinctively, checks whether the request originated from a human or from a borrower-side AI agent — and if the latter, verifies that agent's delegated authority/scope before proceeding. This is the standout, on-trend feature.
5. **Syndication Agent** — matches the deal against a mock pool of lender profiles (risk appetite, sector focus, ticket size) and proposes an allocation/syndicate book with percentages.
6. **Documentation Agent** — auto-drafts a credit agreement summary and covenant schedule from the approved terms.
7. **Orchestrator / Agent Activity Feed** — a live, chronological feed showing each agent "thinking," calling the next agent, and handing off — this is the single most important thing for the demo, because it's what makes the multi-agent architecture *visible* to judges instead of a black box.
8. **Human-in-the-Loop Approval Gates** — at 2-3 clearly marked checkpoints (credit approval, final syndicate allocation), the flow pauses and a human must click Approve/Reject before agents continue. This directly answers the "control layer" concern that's top-of-mind for banking AI right now.
9. **Deal Dashboard** — a pipeline view of all deals in flight, their stage, risk score, and status.

### High-impact (build if time allows, huge demo value)
10. **Post-Close Covenant Monitoring Agent** — simulates ingesting quarterly borrower financials on a timer/button-trigger, re-checks covenant compliance, and flags a breach live during the demo with a suggested remediation (waiver request draft).
11. **Explainability panel** — click any agent's output to see its reasoning trace (which data it used, why it scored what it scored).
12. **Full audit log export** — downloadable log of every agent action with timestamps, for the "how would a regulator trust this" story.

### Nice-to-have (polish only, do last)
13. Dark/light mode toggle.
14. Animated agent "handoff" visualization (a simple node graph lighting up as each agent activates).
15. A synthetic "competitor comparison" stat block: "Traditional origination: 4-6 weeks. Covenant AI: 4 minutes (demo)."

---

## 3. TECH STACK

Keep this simple and fast — you have ~24 hours.

- **Frontend:** React + Vite, Tailwind CSS (utility classes only, no custom build config), shadcn/ui components where useful
- **Backend:** Node.js + Express (or a single Next.js app if Replit Agent defaults there — either is fine)
- **Database:** Replit's built-in PostgreSQL (via Drizzle ORM) — or simplest possible: an in-memory / JSON-file store if time is tight. Don't over-engineer persistence for a 24-hour demo.
- **AI / Agent orchestration:** Anthropic Claude API (`claude-sonnet-4-6` or latest available model) via the standard `/v1/messages` endpoint. Build a lightweight orchestrator function in Node that calls the API multiple times with different system prompts — one per agent role — and passes structured JSON between them. This *is* multi-agent orchestration; you don't need heavyweight infra to demonstrate it well.
  - Note for the pitch: frame this as the demo implementation of what would run on **AWS Bedrock Agents / multi-agent collaboration** in production — say that explicitly on one slide, since the challenge references AWS agentic tooling. Don't burn hours wiring real AWS infra into a 24-hour Replit build; the judges care about the orchestration pattern and the business case, not the cloud vendor.
- **Real-time feed:** Simple polling or WebSocket (Socket.io) to stream the "agent activity feed" live as each agent runs, rather than making the user wait on one big spinner.
- **Charts:** Recharts for the risk score / covenant headroom visuals.
- **Auth:** Skip real auth. Single hardcoded "logged in as Credit Officer" state is fine for a hackathon demo.

---

## 4. PAGES & USER FLOW

1. **Landing / Pitch Page** (`/`)
   - Bold headline: "The agent-native successor to syndicated loan origination."
   - One-line stat block, "Start a Deal" CTA → goes to New Deal page.

2. **New Deal Intake** (`/deals/new`)
   - Form: borrower name, loan amount, purpose, tenor, requested structure. Optional "paste term sheet text" box.
   - Toggle: "This request was submitted by a borrower-side AI agent" (to trigger the KYA flow — great demo lever).
   - Submit → routes to Deal Detail page and immediately kicks off the Origination Agent.

3. **Deal Detail / Live Agent Workspace** (`/deals/:id`) — **this is the page judges will watch for 90% of the demo**
   - Left panel: structured deal terms as they're extracted/updated.
   - Center: **live agent activity feed** — each agent's name, avatar/icon, status (thinking / done / waiting for approval), and a one-line summary of its output, streaming in real time.
   - Right panel: risk score gauge, covenant package, syndicate allocation chart — populate as agents complete.
   - Approval Gate modals appear inline when a human decision is needed.
   - "Explain" button on each agent card opens the reasoning trace.

4. **Deal Pipeline Dashboard** (`/dashboard`)
   - Table/kanban of all deals: stage, borrower, amount, risk score, status badge (In Progress / Awaiting Approval / Closed / Covenant Breach).

5. **Post-Close Monitoring** (`/deals/:id/monitoring`)
   - Button: "Simulate Quarterly Financials Update" → triggers the Monitoring Agent, shows covenant headroom before/after, and if a breach is triggered, shows the auto-drafted waiver request.

6. **Audit Log** (`/deals/:id/audit`)
   - Full chronological, exportable log of every agent action.

**Navigation:** Persistent top nav: Dashboard | New Deal | (deal-specific pages appear once a deal is created).

---

## 5. UI & DESIGN INSTRUCTIONS

- **Look and feel:** Modern fintech-serious, not playful. Think "institutional trust meets AI-native speed" — closer to Mercury/Ramp/Ledger than a consumer app.
- **Color scheme:** Deep navy/ink background or crisp white base (pick one, don't mix light and dark inconsistently) with a single confident accent color — an electric teal or indigo — used only for CTAs, active agent states, and key data points. Risk/breach states use a clear amber/red, never ambiguous.
- **Typography:** A clean geometric sans (Inter or similar) for UI text; a slightly heavier weight for numbers/data (tabular figures) so financial figures feel precise.
- **Layout style:** Card-based, generous whitespace, clear visual hierarchy. The agent activity feed should feel alive — subtle pulse/glow animation on the currently "thinking" agent, a checkmark animation on completion.
- **Key UI components:**
  - Agent card component (icon, name, status badge, one-line output, expandable reasoning trace)
  - Risk gauge (semi-circular meter, Recharts or custom SVG)
  - Covenant headroom bar chart
  - Approval gate modal with clear Approve/Reject buttons
  - Status badges (pill-shaped, color-coded)
- Must look finished and demo-ready out of the box — no default unstyled HTML anywhere.

---

## 6. DATA & APIS

### Data models

```
Deal {
  id, borrowerName, amount, purpose, tenor, structure,
  requestedByAgent: boolean,
  stage: "intake" | "credit_review" | "compliance" | "syndication" | "documentation" | "closed" | "monitoring",
  riskScore: number,
  covenants: Covenant[],
  syndicateAllocations: Allocation[],
  createdAt, updatedAt
}

Covenant {
  id, dealId, type ("leverage_ratio" | "interest_coverage" | "min_liquidity"),
  threshold, currentValue, status: "compliant" | "breach" | "watch"
}

Lender {
  id, name, sectorFocus[], riskAppetite ("conservative"|"moderate"|"aggressive"),
  minTicket, maxTicket
}

Allocation {
  id, dealId, lenderId, percentage, amount
}

AgentLogEntry {
  id, dealId, agentName, action, reasoningSummary, timestamp, requiresApproval: boolean, approvedBy: string | null
}

BorrowerFinancials {
  id, dealId, quarter, revenue, ebitda, totalDebt, cash
}
```

### AI API
- **Anthropic Messages API** — `POST https://api.anthropic.com/v1/messages`, `model: "claude-sonnet-4-6"`, `max_tokens: 1000`. Use a distinct system prompt per agent role (Origination, Credit Risk, Compliance/KYA, Syndication, Documentation, Monitoring). Have each agent return **strict JSON** so the orchestrator can pass structured output to the next agent — see the "Structured Outputs" pattern (prompt for JSON-only, no preamble, then parse).

### Mock/dummy data to pre-populate
- 6-8 fictional lenders with varied sector focus and risk appetite, so the Syndication Agent has something real to allocate against.
- 2-3 pre-built sample deals (e.g., "Meridian Manufacturing — $45M Term Loan B", "Cascade Logistics — $18M Revolver") fully populated end-to-end, so if live generation hiccups during the demo, you can fall back to a finished example instantly.
- A sample "quarterly financials" dataset for the monitoring demo, pre-seeded to trigger one clean covenant breach on the button click.

---

## 7. STEP-BY-STEP BUILD INSTRUCTIONS FOR REPLIT AGENT

Paste this whole brief into Replit Agent, then work through in this order:

1. **Scaffold the project.** Create a React + Vite + Tailwind frontend and a Node/Express backend in one Repl. Set up the Anthropic API key as a secret (`ANTHROPIC_API_KEY`).
2. **Build the data layer first.** Set up Postgres via Drizzle (or a simple JSON store if faster) with the schema above. Seed it with the mock lenders, the 2-3 pre-built sample deals, and the sample financials dataset.
3. **Build the agent orchestrator module on the backend.** One function per agent (`runOriginationAgent(deal)`, `runCreditRiskAgent(deal)`, `runComplianceKYAAgent(deal)`, `runSyndicationAgent(deal, lenders)`, `runDocumentationAgent(deal)`, `runMonitoringAgent(deal, financials)`), each calling the Anthropic API with a role-specific system prompt and returning parsed JSON. Build a top-level `runDealPipeline(dealId)` that calls them in sequence, writing an `AgentLogEntry` after each step, and pausing at the two approval gates (credit approval after Credit Risk Agent, allocation approval after Syndication Agent) until the frontend sends an approve/reject signal.
4. **Wire up real-time updates.** Add a WebSocket (or short-poll) channel so the frontend Deal Detail page gets each `AgentLogEntry` as it's created, instead of waiting for the whole pipeline to finish.
5. **Build the New Deal Intake page** with the form and the "submitted by borrower AI agent" toggle, POSTing to create a deal and kick off the pipeline.
6. **Build the Deal Detail / Live Agent Workspace page** — this is the priority page. Get the live agent feed, risk gauge, covenant panel, and approval modals working and polished before anything else.
7. **Build the Dashboard page** listing all deals with stage/status.
8. **Build the Post-Close Monitoring page** with the "simulate quarterly update" button wired to the Monitoring Agent, using the pre-seeded financials to reliably trigger one covenant breach with a drafted waiver.
9. **Build the Audit Log page**, rendering all `AgentLogEntry` rows chronologically with an export-to-JSON/CSV button.
10. **Polish pass:** apply the color scheme and typography consistently, add the agent card pulse/checkmark animations, add the landing page with the pitch headline and stat block.
11. **Prepare the fallback:** confirm the 2-3 pre-built sample deals can be opened and viewed fully-populated with zero live API calls, in case live generation is slow or flaky during the actual demo.
12. **Rehearse the demo path:** Landing page → New Deal (toggle "submitted by AI agent" on) → watch the live agent feed run through Origination → Credit Risk → KYA/Compliance (call out the agent-verification moment explicitly) → approve the credit gate → Syndication → approve the allocation gate → Documentation → Dashboard showing it as closed → Monitoring page → trigger the covenant breach and show the auto-drafted waiver → Audit Log to close on trust/auditability.

---

## Demo script cheat sheet (first 10 seconds matter most)

Open with: *"Loan IQ takes a syndicated loan from term sheet to close in weeks, with a dozen manual handoffs. Watch Covenant AI do it live, with a human approving only the two decisions that actually matter."* Then run the demo path above. Close on the audit log — that's the line that turns "cool demo" into "a credit officer would actually deploy this."
