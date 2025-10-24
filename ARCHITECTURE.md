# Architecture

This project uses **Strands Agents** orchestrated via **Amazon Bedrock AgentCore** to run a multi-agent, tool-using workflow across RFQ, selection, negotiation, and logistics.

![Technical Architecture](docs/images/tech-architecture.png)

## Components
- **Supervisor (Nova Pro)** — Plans the sequence, dispatches tasks to sub-agents, aggregates results, manages retries, and emits a final summary.
- **Specialized agents**
  - **A0 Email Intelligence (Haiku)** — Gmail + attachment parsing → RFQ JSON
  - **A1 RFQ Update (Haiku)** — Upsert RFQ/Account in Salesforce; seed DynamoDB
  - **A2 Supplier Selection (Haiku/Sonnet)** — Score & shortlist; generate outreach
  - **A3 Quote Normalization (Sonnet)** — Textract + LLM normalization + market/wiki checks
  - **A4 Negotiation (Sonnet)** — Counter-offers/awards; Slack notifications
  - **A5 Logistics (Sonnet)** — Compute mode/route; risk via news/weather; render map

## Runtime
- **AgentCore entrypoint** (`master-agent-runtime-entrypoint.py`) exposes a handler that:
  1) Validates and flattens incoming runtime payloads.  
  2) Invokes the **Supervisor** with the derived `user_input` and tool context.  
  3) Returns a JSON-serializable result for downstream systems.
- **Security/config**: `.env.example` + `test_env_setup.py` to verify required variables (no secrets committed).
- **Observability**: each agent writes structured events to DynamoDB `supply_audit` and emits step summaries.

## Data flow (end-to-end)
![Process Flow](docs/images/process-flow.png)

1. **Ingest**: Gmail → A0 extracts RFQ entities; documents optionally from S3/Textract.
2. **Upsert**: A1 writes RFQ__c / Account to Salesforce; seeds routing metadata in DynamoDB.
3. **Shortlist & Outreach**: A2 computes shortlist and drafts/send RFQs (SES/Gmail API).
4. **Normalize & Benchmark**: A3 converts quotes to comparable schema; enrich with reputation/market signals.
5. **Negotiate & Award**: A4 performs weighted scoring, drafts counter-offer/award; notifies Slack; persists decisions.
6. **Plan Logistics**: A5 computes ALL_OCEAN vs SPLIT_AIR_OCEAN with cost/ETA/CO₂; checks news/weather; renders Folium map.
7. **Summarize**: Supervisor produces human-readable recap + links to audit artifacts.

## Placement vs. **AWS Supply Chain (ASC)**
- **Upstream/side-car** to ASC: Our outputs (RFQ facts, scored quotes, award decisions, shipment options) can be landed to **S3** and mapped into the **ASC Data Lake** for visibility and planning.
- **Signals back from ASC** (inventory risk, order tracking, constraints) influence negotiation timing and logistics choices.
- **N-Tier**: Post-award, use ASC for multi-tier PO/forecast/status sharing; our agents continue comms and exception handling.

## Tools & adapters
- **Salesforce**: list/create/update `RFQ__c`; upsert Account via `External_Ref__c`
- **DynamoDB**: `supply_*` tables (suppliers, rfqs, bids, shipments, alerts, audit)
- **Messaging**: Gmail API (ingest), SES (outbound), Slack (notifications)
- **Docs & data**: S3, Textract, Tavily, Wikipedia
- **Routing**: Mapbox (geo/directions), Open-Meteo (weather), Folium (map)

## Models (env-configurable IDs)
- `amazon.nova-pro-v1:0` (Supervisor)
- `anthropic.claude-3-5-haiku-20241022-v1:0` (Extraction/Outreach)
- `anthropic.claude-3-5-sonnet-20241022-v2:0` (Analysis/Negotiation/Logistics)

## Security notes
- No credentials in Git; use `.env` and AWS secret stores as appropriate.
- `test_env_setup.py` validates required keys and endpoint reachability where safe.
