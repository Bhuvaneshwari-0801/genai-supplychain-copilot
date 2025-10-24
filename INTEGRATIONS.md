# Integrations & Data Shapes

This page documents the primary integrations, plus lightweight schemas for **S3 hand-off into AWS Supply Chain (ASC)** and our DynamoDB audit trail.

## Salesforce
Objects used in our flows:
- **RFQ__c**: `External_Ref__c` (unique), `Name`, `SKU__c`, `Quantity__c`, `Target_Delivery__c`, `Status__c`, `Priority__c`, `Currency__c`, `Expected_Unit_Price__c`, `Notes__c`, `Incoterms__c`, `Delivery_Location__c`, `Payment_Terms__c`, `OTD_Floor_Pct__c`, `Account__c`.
- **Account**: `External_Ref__c`, `Name`, `Type`, `Industry`, `Phone`, `Website`, `BillingCity`, `BillingState`, `BillingCountry`.

## DynamoDB tables (prefix `supply_`)
- `supply_suppliers(pk: supplier_id)` — attributes: location, lead_time_days, otd_pct, capacity, certifications[], risk_notes, sustainability_score, etc.
- `supply_rfqs(pk: rfq_id)` — `{ sku, org, qty, target_delivery_utc, specs(json), created_utc }`
- `supply_bids(pk: rfq_id, sk: supplier_id)` — `{ unit_price_usd, shipping_mode, lead_time_days, total_score, currency, valid_till_utc, created_utc }`
- `supply_shipments(pk: shipment_id)` — `{ po_id, rfq_id, supplier_id, mode, origin_port, dest_port, lane, carrier, etd_utc, eta_utc, status, co2_kg }`
- `supply_alerts(pk: alert_id)` — `{ lane, source, title, severity, observed_utc, details }`
- `supply_audit(pk: audit_id)` — `{ entity_id, actor, action, details, ts_utc }`

## Outbound S3 (for ASC ingestion)
We emit compact JSON snapshots per RFQ award to `s3://<bucket>/asc/rfq_awards/<rfq_id>.json`.

```json
{
  "rfq_id": "RFQ-2024-00017",
  "external_ref": "SFDC-EXT-00017",
  "sku": "18650-2P-NICKEL",
  "quantity": 10000,
  "currency": "USD",
  "award": {
    "supplier_id": "SUP-NEO-88",
    "unit_price": 1.72,
    "incoterms": "FOB-SHENZHEN",
    "lead_time_days": 21,
    "valid_till_utc": "2025-11-01T00:00:00Z",
    "rationale": {
      "price_score": 0.42,
      "delivery_score": 0.33,
      "quality_score": 0.18,
      "sustainability_score": 0.07,
      "explanation": "Best blended score; meets OTD floor; favorable terms."
    }
  },
  "logistics": {
    "option": "SPLIT_AIR_OCEAN",
    "eta_utc": "2025-11-24T00:00:00Z",
    "cost_total_usd": 19250,
    "co2_kg": 3412,
    "lane": "CNSZX→USLAX",
    "risk_signals": ["Port congestion advisory", "Gale warnings 48–72h"]
  },
  "audit_ref": "AUD-9c7e2f"
}
```

> **Why:** This structure maps cleanly into an ASC data lake for planning/visibility while preserving the agentic rationale.

## Inbound signals from **AWS Supply Chain (ASC)**
Supervised polling/webhooks (shape suggestion):

```json
{
  "source": "aws-supply-chain",
  "signal_type": "order_risk|stock_out|overstock|shipment_delay",
  "entity_ref": "PO-10239",
  "severity": "low|medium|high|critical",
  "lane": "CNSZX→USLAX",
  "message": "ETA slippage risk due to weather and port backlog.",
  "observed_utc": "2025-10-24T08:23:00Z",
  "links": ["https://console.aws.amazon.com/..."]
}
```

Our **Supervisor** translates these into goals/constraints for A4/A5 (renegotiate timing, switch route, add buffer days).

## Messaging
- **Email in**: Gmail API (read), attachments routed to Textract as needed.
- **Email out**: Amazon SES (text/HTML).
- **Slack**: channel posts for shortlist ready, award sent, risk detected, route proposed.

## Routing & risk
- **Mapbox** for geocoding/directions; **Open-Meteo** for short-range weather; **Tavily/Wikipedia** for headlines/background; **Folium** to render a shareable map HTML.
