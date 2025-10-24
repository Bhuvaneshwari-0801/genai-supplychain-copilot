# GenAI SupplyChain Copilot — One-Pager

**Tagline:** From inbox chaos to award + resilient routing — explainable, agentic, and live on Amazon Bedrock.

## The problem
Mid-size electronics buyers juggle noisy quotes (email/PDF/CSV), inconsistent terms, and late disruption signals — leading to slow awards and expensive rush freight.

## What we built
A 6-agent + Supervisor system that:
- Extracts RFQ facts from messy emails
- Normalizes & scores quotes (explainable)
- Drafts counter-offers/awards with context
- Proposes logistics (cost/ETA/CO₂) and checks lane risk
- Writes a clean audit trail (Salesforce + DynamoDB)
- Notifies Slack at decision points

## Why it’s GenAI
Agentic orchestration on Bedrock (Strands + AgentCore), multiple LLMs with tool-use, and grounded decisions (docs/news/weather/Salesforce).

## Wow factors
- **Inbox → Award** in one flow, with explainable rationale  
- **Risk-aware routing** and shareable interactive map  
- **ASC complement** — clean S3 exports for ASC data lake; ingest ASC risk signals back into decisions

## Tech
Models: `amazon.nova-pro-v1:0`, `anthropic.claude-3-5-haiku-20241022-v1:0`, `anthropic.claude-3-5-sonnet-20241022-v2:0`  
Integrations: Salesforce, DynamoDB, SES, Slack, Gmail, S3/Textract, Mapbox, Open-Meteo, Tavily, Wikipedia

## Links
Repo: https://github.com/khan-cloudgeek/genai-supplychain-copilot  
Demo: https://youtu.be/I6AxMIVICbw  
Hackathon: https://aws-agent-hackathon.devpost.com
