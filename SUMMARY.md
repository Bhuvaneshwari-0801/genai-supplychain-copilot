# Solution Summary — GenAI SupplyChain Copilot

**Elevator pitch:** An agentic copilot on **Amazon Bedrock (Strands Agents + AgentCore)** that converts messy supplier replies into **awards and resilient logistics plans**—with **explainable** decisions and an **audit trail** back to Salesforce and DynamoDB.

![Process Flow](docs/images/process-flow.png)

## Who it’s for (personas)
- **Category/Sourcing Manager** – wants clean, comparable quotes, faster awards, and fewer surprises.
- **Logistics Planner** – wants cost/ETA/CO₂ trade‑offs and early disruption signals.
- **Procurement Ops/Leadership** – wants explainable decisions and traceability.

## Problem → Impact
- Quotes arrive as email/PDF/CSV → manual parsing → slow decisions and late risk detection → rush freight.
- Impact: delayed RFQs/POs, higher logistics spend, weak auditability.

## What we built
- **Six agents + one Supervisor** coordinating RFQ→selection→negotiation→logistics.
- **Models (Bedrock):** `amazon.nova-pro-v1:0` (Supervisor), `anthropic.claude-3-5-haiku-20241022-v1:0` (extraction/outreach), `anthropic.claude-3-5-sonnet-20241022-v2:0` (evaluation/negotiation/logistics).
- **Tools/data:** Salesforce, DynamoDB, Gmail API, Amazon SES, S3/Textract, Slack, Mapbox, Open‑Meteo, Tavily, Wikipedia, Folium.

## End‑to‑end at a glance
1) **Ingest** supplier replies from Gmail; extract `{unit_price, currency, lead_time_days, incoterms, valid_till, notes}`.  
2) **Upsert** RFQ/Account in **Salesforce**, seed **DynamoDB**.  
3) **Shortlist** and send RFQs; gather quotes; **normalize** to a comparable schema.  
4) **Score & explain** trade‑offs (price, delivery, quality, sustainability).  
5) **Negotiate** (counter‑offers/awards) and notify via **Slack/Email**.  
6) **Plan logistics** (ALL_OCEAN vs SPLIT_AIR_OCEAN) with cost/ETA/CO₂; check **news/weather** along the lane; render a **map**.  
7) **Summarize** and **audit** the full trail.

## Why this is GenAI (not just automation)
- **Agentic orchestration** with tool‑use and role‑specialization.  
- **Explainable selection** and rationale persisted to audit.  
- **Risk‑aware** logistics driven by live signals (news/weather).

## Fit with **AWS Supply Chain (ASC)**
- **Complementary:** We handle the upstream **tactical sourcing loop** and export clean snapshots (S3) that ASC can ingest for planning/visibility.  
- **Closed loop:** ASC risk/visibility signals can feed the **Supervisor** to adjust negotiation timing or routing choices.  
- **N‑Tier:** Use ASC for supplier collaboration post‑award; our agents keep doing supplier comms and exception handling.

## Wow factors
- Inbox → **Award** in one flow with transparent scoring.  
- **Resilient routing** with disruption sensing and a shareable map.  
- **Human‑readable** outputs (emails/Slack) + leadership summary.

## Try it (quick)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in keys
python test_env_setup.py

# Local AgentCore entry
LOCAL_TEST=1 python master-agent-runtime-entrypoint.py

# Full orchestrator demo
python supply-chain-master-agent.py
```

## Links
- Repo: https://github.com/khan-cloudgeek/genai-supplychain-copilot  
- Demo: https://youtu.be/I6AxMIVICbw
