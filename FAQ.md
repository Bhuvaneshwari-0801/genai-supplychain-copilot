# FAQ

**Is this a replacement for my ERP or AWS Supply Chain?**  
No. It **augments** your existing tools. Think of it as an upstream, agentic copilot for RFQ→award→routing that **feeds** AWS Supply Chain (ASC) for network-wide planning and visibility.

**What makes this truly GenAI (not “just automation”)?**  
Six specialized agents + a Supervisor coordinate reasoning over unstructured inputs, call real tools, explain decisions, and adapt to signals (news/weather/ASC).

**Which models are used and why?**  
- **Nova Pro**: planning/orchestration (tool-use & decomposition)  
- **Claude 3.5 Haiku**: fast/cheap extraction, parsing, outreach  
- **Claude 3.5 Sonnet**: deeper reasoning for evaluation, negotiation, logistics

**Can I change models/regions?**  
Yes — IDs/regions are env-driven. Swap models as needed; the agent prompts/tools stay the same.

**Where do the decisions get logged?**  
Salesforce (RFQ/Account updates) and DynamoDB `supply_audit` for traceability (who/what/why/when).

**How does routing consider risk?**  
We compute cost/ETA/CO₂ and enrich with news/weather signals along the lane. The map output is a Folium HTML asset you can attach/share.

**How does this integrate with ASC?**  
We export award & shipment-option snapshots to S3 for ASC ingestion; ASC risk/order-tracking insights can be pulled back to adjust negotiations or routes.

**What about security?**  
No secrets in Git. Use `.env` locally and AWS secret stores in cloud. `test_env_setup.py` validates required settings.
