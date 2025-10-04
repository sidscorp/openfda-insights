"""
Sanity check queries to verify the FDA Agent implementation.

Run these to quickly verify all components are working correctly.
"""
import os
from agent.graph import FDAAgent
from rag.retrieval import DocRetriever
from agent.extractor import ParameterExtractor
from langchain_anthropic import ChatAnthropic

print("=" * 70)
print("FDA AGENT SANITY CHECKS")
print("=" * 70)

# Check 1: RAG Hybrid Retrieval
print("\n[1] Testing RAG Hybrid Retrieval...")
print("-" * 70)
retriever = DocRetriever("docs/corpus.json")
print(f"✓ Loaded {len(retriever.docs)} docs")

test_queries = [
    "How do I search for Class II devices?",
    "What fields are in the 510k endpoint?",
    "Show me recalls",
]

for query in test_queries:
    results = retriever.search(query, top_k=2)
    print(f"\nQuery: '{query}'")
    print(f"  Top result: {results[0].endpoint} ({results[0].section}) - score: {results[0].score:.4f}")
    if results[0].endpoint in ["classification", "510k", "enforcement", "event"]:
        print(f"  ✓ Correctly identified device endpoint")

# Check 2: Parameter Extraction
print("\n\n[2] Testing Parameter Extraction...")
print("-" * 70)
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    print("⚠️  ANTHROPIC_API_KEY not set - skipping extraction tests")
else:
    llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0)
    extractor = ParameterExtractor(llm)

    test_cases = [
        ("Show me 5 Class II devices", {"device_class": "2", "limit": 5}),
        ("Find 510k clearances from Medtronic since 2023", {"applicant": "Medtronic", "date_start": "20230101"}),
        ("Any Class I recalls?", {"recall_class": "Class I"}),
        ("Show me K123456", {"k_number": "K123456"}),
    ]

    for query, expected in test_cases:
        extracted = extractor.extract(query)
        print(f"\nQuery: '{query}'")
        matches = []
        for key, value in expected.items():
            actual = getattr(extracted, key)
            if str(value) in str(actual):
                matches.append(f"✓ {key}={actual}")
            else:
                matches.append(f"✗ {key}={actual} (expected {value})")
        print(f"  {', '.join(matches)}")

# Check 3: End-to-End Agent
print("\n\n[3] Testing End-to-End Agent...")
print("-" * 70)
if not api_key:
    print("⚠️  ANTHROPIC_API_KEY not set - skipping agent tests")
else:
    agent = FDAAgent()

    test_queries = [
        "Show me 3 Class II devices",
        "Find 510k clearances from Medtronic",
    ]

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        try:
            result = agent.query(query)
            print(f"  Endpoint: {result['selected_endpoint']}")
            print(f"  Extracted: device_class={result['extracted_params'].get('device_class')}, "
                  f"applicant={result['extracted_params'].get('applicant')}")
            print(f"  Results: {result['provenance'].get('result_count')}")
            print(f"  Sufficient: {result['is_sufficient']}")
            if result['is_sufficient'] and result['provenance'].get('result_count', 0) > 0:
                print(f"  ✓ Success")
        except Exception as e:
            print(f"  ✗ Error: {e}")

# Check 4: Router Tool Calling
print("\n\n[4] Testing Router Tool Calling...")
print("-" * 70)
if not api_key:
    print("⚠️  ANTHROPIC_API_KEY not set - skipping router tests")
else:
    from agent.router import route

    test_cases = [
        ("Show me Class II devices", "classification"),
        ("Find 510k clearances", "510k"),
        ("Any recalls?", "recall"),
        ("Show adverse events", "maude"),
    ]

    for query, expected in test_cases:
        selected = route(query, llm)
        match = "✓" if expected in selected else "✗"
        print(f"{match} '{query}' → {selected} (expected: {expected})")

# Check 5: Assessor Validation
print("\n\n[5] Testing Assessor Validation...")
print("-" * 70)
from tools.utils import AnswerAssessorParams, answer_assessor

test_cases = [
    {
        "name": "Missing class filter",
        "params": AnswerAssessorParams(
            question="Show me Class I recalls",
            search_query="firm_name:Medtronic",  # Missing class!
            result_count=10,
            date_filter_present=False,
            class_filter_present=False,
        ),
        "expect_sufficient": False,
    },
    {
        "name": "Proper filters applied",
        "params": AnswerAssessorParams(
            question="Show me Class I recalls since 2023",
            search_query="recall_class:Class I AND date:[20230101 TO 20251231]",
            result_count=5,
            date_filter_present=True,
            class_filter_present=True,
        ),
        "expect_sufficient": True,
    },
    {
        "name": "Zero results with filters OK",
        "params": AnswerAssessorParams(
            question="Show me Class III recalls from XYZ Corp in 1999",
            search_query="recall_class:Class III AND firm_name:XYZ",
            result_count=0,
            date_filter_present=True,
            class_filter_present=True,
        ),
        "expect_sufficient": True,
    },
]

for test in test_cases:
    assessment = answer_assessor(test["params"])
    match = "✓" if assessment.sufficient == test["expect_sufficient"] else "✗"
    print(f"{match} {test['name']}: sufficient={assessment.sufficient} - {assessment.reason}")

print("\n" + "=" * 70)
print("SANITY CHECKS COMPLETE")
print("=" * 70)
print("\nTo run these checks:")
print("  source .venv/bin/activate")
print("  python sanity_checks.py")
print("\nNote: Checks 2-4 require ANTHROPIC_API_KEY environment variable")
