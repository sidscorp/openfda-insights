# FDA Analyst Test Queries

Real-world questions an FDA analyst might ask. Copy-paste these to verify the agent works correctly.

## Setup
```bash
source .venv/bin/activate
export ANTHROPIC_API_KEY="your-key-here"  # Required
```

---

## Device Classification Queries

```python
from agent.graph import FDAAgent
agent = FDAAgent()

# Q1: What are the Class III (high-risk) devices?
result = agent.query("Show me 5 Class III medical devices")
print(f"Found {result['provenance']['result_count']} Class III devices")
# Should route to: classification endpoint
```

```python
# Q2: Find devices by product code
result = agent.query("What is product code LZG?")
print(f"Endpoint: {result['selected_endpoint']}")  # Should be: classification
```

```python
# Q3: Search for surgical devices
result = agent.query("Find Class II surgical instruments")
# Should extract: device_class=2
```

---

## 510(k) Clearance Queries

```python
# Q4: Find recent 510k clearances from a specific manufacturer
result = agent.query("Show me 510k clearances from Medtronic approved since January 2023")
print(f"Applicant: {result['extracted_params']['applicant']}")  # Should be: Medtronic
print(f"Date filter: {result['extracted_params']['date_start']}")  # Should be: 20230101
```

```python
# Q5: Lookup specific K-number
result = agent.query("What is K123456?")
print(f"K-number: {result['extracted_params']['k_number']}")  # Should be: K123456
print(f"Endpoint: {result['selected_endpoint']}")  # Should be: 510k
```

```python
# Q6: Find clearances for a device type
result = agent.query("Find 510k clearances for pacemakers in 2024")
# Should route to: 510k
# Should extract: device_name=pacemakers, dates for 2024
```

---

## PMA Approval Queries

```python
# Q7: Find recent PMA approvals
result = agent.query("What PMA approvals happened in 2024?")
print(f"Endpoint: {result['selected_endpoint']}")  # Should be: pma
print(f"Date range: {result['extracted_params']['date_start']}")  # Should be: 20240101
```

```python
# Q8: Find PMAs from specific company
result = agent.query("Show me PMA approvals from Boston Scientific")
print(f"Applicant: {result['extracted_params']['applicant']}")  # Should be: Boston Scientific
```

```python
# Q9: Lookup specific P-number
result = agent.query("Find PMA P850016")
print(f"PMA number: {result['extracted_params']['pma_number']}")  # Should be: P850016
```

---

## Recall/Enforcement Queries

```python
# Q10: Find serious recalls
result = agent.query("Show me Class I recalls")
print(f"Recall class: {result['extracted_params']['recall_class']}")  # Should be: Class I
print(f"Endpoint: {result['selected_endpoint']}")  # Should be: recall
```

```python
# Q11: Find recalls by manufacturer
result = agent.query("Any recalls from Medtronic in the last year?")
print(f"Firm: {result['extracted_params']['firm_name']}")  # Should be: Medtronic
# Should have date filter for last year
```

```python
# Q12: Find recalls for specific device type
result = agent.query("Show me Class II recalls for insulin pumps")
# Should extract: recall_class=Class II, device_name or firm containing insulin pump info
```

---

## Adverse Event (MAUDE) Queries

```python
# Q13: Find adverse events for a device
result = agent.query("Show me adverse events for pacemakers")
print(f"Endpoint: {result['selected_endpoint']}")  # Should be: maude
print(f"Device: {result['extracted_params']['device_name']}")  # Should be: pacemakers
```

```python
# Q14: Find malfunction reports
result = agent.query("Find device malfunctions reported in 2024")
print(f"Event type: {result['extracted_params']['event_type']}")  # Should be: Malfunction
```

```python
# Q15: Find injury/death reports
result = agent.query("Show me adverse events involving patient deaths")
# Should route to: maude (event endpoint)
# Should extract event_type or search for death-related events
```

---

## UDI/GUDID Queries

```python
# Q16: Lookup device by UDI
result = agent.query("Find device with UDI 00819320201234")
print(f"Endpoint: {result['selected_endpoint']}")  # Should be: udi
```

```python
# Q17: Find devices by manufacturer in GUDID
result = agent.query("What devices does Johnson & Johnson manufacture?")
print(f"Endpoint: {result['selected_endpoint']}")  # Should be: udi
```

---

## Establishment Registration Queries

```python
# Q18: Find manufacturers in a state
result = agent.query("Show me device manufacturers in California")
print(f"Endpoint: {result['selected_endpoint']}")  # Should be: rl_search
print(f"State: {result['extracted_params']['state']}")  # Should be: CA
```

```python
# Q19: Find establishments by FEI number
result = agent.query("What is establishment FEI 3004184753?")
print(f"FEI: {result['extracted_params']['fei_number']}")
```

```python
# Q20: Find facilities owned by a company
result = agent.query("Show me Medtronic facilities registered with FDA")
print(f"Firm: {result['extracted_params']['firm_name']}")  # Should be: Medtronic
```

---

## Complex Multi-Filter Queries

```python
# Q21: Multiple filters
result = agent.query("Show me Class I recalls from California manufacturers in 2024")
print(f"Recall class: {result['extracted_params']['recall_class']}")  # Class I
print(f"State: {result['extracted_params']['state']}")  # CA
print(f"Date: {result['extracted_params']['date_start']}")  # 20240101
```

```python
# Q22: Time-bound device search
result = agent.query("Find 510k clearances for cardiovascular devices approved between 2020 and 2023")
# Should extract: date_start=20200101, date_end=20231231
```

---

## Edge Cases & Error Handling

```python
# Q23: Ambiguous query (should still route somewhere reasonable)
result = agent.query("Tell me about medical devices")
print(f"Routed to: {result['selected_endpoint']}")
# Likely: classification (most general)
```

```python
# Q24: Zero results (should handle gracefully)
result = agent.query("Show me recalls from XYZ Fake Company in 1950")
print(f"Sufficient: {result['is_sufficient']}")  # Should be: True
print(f"Results: {result['provenance']['result_count']}")  # Should be: 0
print(f"Reason: {result.get('assessor_reason')}")  # Should accept zero results
```

---

## Verification Commands (One-Liners)

```bash
# Test 1: Class III devices
python -m agent.cli "Show me 5 Class III devices"

# Test 2: 510k from Medtronic
python -m agent.cli "Find 510k clearances from Medtronic since 2023"

# Test 3: Class I recalls
python -m agent.cli "Show me Class I recalls"

# Test 4: Adverse events
python -m agent.cli "Find adverse events for pacemakers"

# Test 5: California manufacturers
python -m agent.cli "Show me device manufacturers in California"

# Test 6: With explain mode
python -m agent.cli "Show me Class II devices" --explain
```

---

## Expected Behavior Checklist

For each query above, verify:
- ✅ **Router**: Selects correct endpoint (classification/510k/pma/recall/maude/udi/rl_search)
- ✅ **Extractor**: Pulls out correct filters (device_class, dates, firm_name, etc.)
- ✅ **Assessor**: Validates filters match question intent
- ✅ **Results**: Returns actual data from openFDA API
- ✅ **Provenance**: Includes endpoint, filters, last_updated timestamp

---

## Quick Visual Test

Run this to see the agent work on 5 realistic queries:

```python
from agent.graph import FDAAgent
agent = FDAAgent()

queries = [
    "Show me Class III devices",
    "Find 510k clearances from Medtronic",
    "Any Class I recalls?",
    "Show me adverse events for insulin pumps",
    "Find manufacturers in Texas",
]

for q in queries:
    print(f"\n{'='*60}")
    print(f"Q: {q}")
    print('='*60)
    result = agent.query(q)
    print(f"Endpoint: {result['selected_endpoint']}")
    print(f"Results: {result['provenance']['result_count']}")
    print(f"Answer: {result['answer']}")
```

All 5 should succeed with actual results from openFDA!
