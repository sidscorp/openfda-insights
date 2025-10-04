"""
OpenFDA documentation scraper.

Fetches device endpoint docs, converts HTML → markdown, chunks by section.
Rationale: Build a minimal, authoritative corpus for RAG without hallucinating fields.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List
from urllib.parse import urljoin

import requests
from pydantic import BaseModel, Field


class DocChunk(BaseModel):
    """A chunk of documentation with metadata."""

    url: str = Field(description="Source URL")
    endpoint: str = Field(description="Endpoint name (e.g., '510k', 'classification')")
    section: str = Field(description="Section heading (e.g., 'Fields', 'Query Examples')")
    content: str = Field(description="Markdown content")
    chunk_id: str = Field(description="Unique ID for this chunk")


class DocScraper:
    """Scrapes openFDA device documentation."""

    BASE_URL = "https://open.fda.gov"

    # Device endpoint pages to scrape (base + searchable-fields)
    ENDPOINTS = {
        "device_overview": ["/apis/device/"],
        "registrationlisting": ["/apis/device/registrationlisting/", "/apis/device/registrationlisting/searchable-fields/"],
        "classification": ["/apis/device/classification/", "/apis/device/classification/searchable-fields/"],
        "510k": ["/apis/device/510k/", "/apis/device/510k/searchable-fields/"],
        "pma": ["/apis/device/pma/", "/apis/device/pma/searchable-fields/"],
        "enforcement": ["/apis/device/enforcement/", "/apis/device/enforcement/searchable-fields/"],
        "event": ["/apis/device/event/", "/apis/device/event/searchable-fields/"],
        "udi": ["/apis/device/udi/", "/apis/device/udi/searchable-fields/"],
    }

    # General API docs
    GENERAL_DOCS = {
        "query_syntax": ["/apis/query-syntax/"],
        "query_parameters": ["/apis/query-parameters/"],
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "openfda-agent-doc-scraper/1.0"})

    def fetch_page(self, path: str) -> str:
        """Fetch HTML content from openFDA."""
        url = urljoin(self.BASE_URL, path)
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text

    def html_to_markdown(self, html: str) -> str:
        """
        Minimal HTML → markdown conversion.

        Note: This is a simple implementation. For production, consider using
        html2text or markdownify libraries.
        """
        # Remove script/style tags
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

        # Extract main content (simple heuristic: look for article or main tags)
        main_match = re.search(r"<(article|main)[^>]*>(.*?)</\1>", html, re.DOTALL | re.IGNORECASE)
        if main_match:
            html = main_match.group(2)

        # Convert headings
        html = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n# \1\n", html, flags=re.IGNORECASE)
        html = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n## \1\n", html, flags=re.IGNORECASE)
        html = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n### \1\n", html, flags=re.IGNORECASE)
        html = re.sub(r"<h4[^>]*>(.*?)</h4>", r"\n#### \1\n", html, flags=re.IGNORECASE)

        # Convert paragraphs and line breaks
        html = re.sub(r"<p[^>]*>", r"\n", html, flags=re.IGNORECASE)
        html = re.sub(r"</p>", r"\n", html, flags=re.IGNORECASE)
        html = re.sub(r"<br\s*/?>", r"\n", html, flags=re.IGNORECASE)

        # Convert code blocks
        html = re.sub(r"<pre[^>]*><code[^>]*>(.*?)</code></pre>", r"\n```\n\1\n```\n", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", html, flags=re.IGNORECASE)

        # Convert lists
        html = re.sub(r"<li[^>]*>", r"- ", html, flags=re.IGNORECASE)
        html = re.sub(r"</li>", r"\n", html, flags=re.IGNORECASE)
        html = re.sub(r"</?[uo]l[^>]*>", r"\n", html, flags=re.IGNORECASE)

        # Convert links
        html = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r"[\2](\1)", html, flags=re.IGNORECASE)

        # Remove remaining HTML tags
        html = re.sub(r"<[^>]+>", "", html)

        # Clean up whitespace
        html = re.sub(r"\n\s*\n\s*\n+", r"\n\n", html)
        html = html.strip()

        return html

    def extract_field_names(self, markdown: str) -> List[str]:
        """
        Extract field names from searchable-fields pages.

        Looks for patterns like:
        - `field.name`
        - field_name
        - Lists of field names after "Searchable fields:" heading
        """
        fields = set()

        # Pattern 1: backtick-wrapped fields (most common in openFDA docs)
        backtick_fields = re.findall(r"`([a-z_\.]+)`", markdown, re.IGNORECASE)
        fields.update(backtick_fields)

        # Pattern 2: Code blocks with field lists
        code_blocks = re.findall(r"```\n(.*?)\n```", markdown, re.DOTALL)
        for block in code_blocks:
            # Extract field-like tokens (alphanumeric with dots/underscores)
            block_fields = re.findall(r"\b([a-z][a-z0-9_\.]+)\b", block, re.IGNORECASE)
            fields.update(block_fields)

        # Filter: keep only fields with . or _ (exclude common words)
        fields = {f for f in fields if "." in f or "_" in f}

        return sorted(fields)

    def synth_header(self, endpoint: str, field_names: List[str]) -> str:
        """
        Generate synthetic header to boost endpoint/field surface forms.

        Repeats endpoint name and canonical field names to improve retrieval.
        Rationale: CEO resolution #2b - keyword boosting for endpoint names.
        """
        # Clean endpoint name (remove special chars)
        clean_endpoint = endpoint.replace("_", " ").replace("registrationlisting", "registration listing")

        header = f"[ENDPOINT]: {endpoint} {clean_endpoint}\n"
        if field_names:
            header += f"[FIELDS]: {', '.join(field_names[:20])}\n"  # Limit to 20 fields to avoid bloat

        return header + "\n"

    def chunk_by_sections(self, markdown: str, endpoint: str, url: str, is_fields_page: bool = False) -> List[DocChunk]:
        """
        Split markdown into chunks by H2 sections.

        Each chunk gets metadata: endpoint, section heading, URL.
        Adds synthetic headers to boost endpoint/field matching.
        """
        chunks = []

        # Extract field names if this is a searchable-fields page
        field_names = self.extract_field_names(markdown) if is_fields_page else []

        # Generate synthetic header
        synth_header = self.synth_header(endpoint, field_names)

        # Split by H2 headings
        sections = re.split(r"\n## ", markdown)

        # First section (before first H2) is the overview
        if sections[0].strip():
            content = synth_header + sections[0].strip()
            chunks.append(
                DocChunk(
                    url=url,
                    endpoint=endpoint,
                    section="Overview",
                    content=content,
                    chunk_id=f"{endpoint}_overview",
                )
            )

        # Remaining sections
        for i, section in enumerate(sections[1:], start=1):
            lines = section.split("\n", 1)
            heading = lines[0].strip()
            section_content = lines[1].strip() if len(lines) > 1 else ""

            if section_content:
                content = synth_header + f"## {heading}\n\n{section_content}"
                chunks.append(
                    DocChunk(
                        url=url,
                        endpoint=endpoint,
                        section=heading,
                        content=content,
                        chunk_id=f"{endpoint}_{i}_{heading.lower().replace(' ', '_')}",
                    )
                )

        return chunks

    def load_synthetic_howtos(self) -> List[DocChunk]:
        """Load synthetic howto documents from docs/synthetic_howtos/."""
        chunks = []
        howto_dir = Path("docs/synthetic_howtos")

        if not howto_dir.exists():
            print("  ⚠️  No synthetic howtos found (expected in docs/synthetic_howtos/)")
            return chunks

        # Map filenames to endpoint names
        filename_to_endpoint = {
            "classification.md": "classification",
            "510k.md": "510k",
            "pma.md": "pma",
            "enforcement.md": "enforcement",
            "event.md": "event",
            "udi.md": "udi",
            "registrationlisting.md": "registrationlisting",
        }

        for filename, endpoint in filename_to_endpoint.items():
            filepath = howto_dir / filename
            if filepath.exists():
                try:
                    markdown = filepath.read_text()
                    # Create a single chunk per howto (don't split by sections)
                    chunk = DocChunk(
                        url=f"file://{filepath}",
                        endpoint=endpoint,
                        section="Synthetic Howto",
                        content=markdown,
                        chunk_id=f"{endpoint}_synthetic_howto",
                    )
                    chunks.append(chunk)
                except Exception as e:
                    print(f"    ✗ Error loading {filename}: {e}", file=sys.stderr)

        return chunks

    def scrape_all(self) -> List[DocChunk]:
        """Scrape all device endpoint docs and general API docs."""
        all_chunks = []

        # Load synthetic howtos first (highest quality, manually curated)
        print("Loading synthetic howtos...")
        synthetic_chunks = self.load_synthetic_howtos()
        all_chunks.extend(synthetic_chunks)
        print(f"  ✓ Loaded {len(synthetic_chunks)} synthetic howto docs")

        # Scrape device endpoints (now with multiple pages per endpoint)
        print("\nScraping device endpoint docs...")
        for name, paths in self.ENDPOINTS.items():
            for path in paths:
                try:
                    is_fields_page = "searchable-fields" in path
                    page_type = "searchable-fields" if is_fields_page else "overview"
                    print(f"  Fetching {name} ({page_type})...")
                    html = self.fetch_page(path)
                    markdown = self.html_to_markdown(html)
                    url = urljoin(self.BASE_URL, path)
                    chunks = self.chunk_by_sections(markdown, name, url, is_fields_page=is_fields_page)
                    all_chunks.extend(chunks)
                    print(f"    ✓ {len(chunks)} chunks")
                except Exception as e:
                    print(f"    ✗ Error: {e}", file=sys.stderr)

        # Scrape general API docs
        print("\nScraping general API docs...")
        for name, paths in self.GENERAL_DOCS.items():
            for path in paths:
                try:
                    print(f"  Fetching {name}...")
                    html = self.fetch_page(path)
                    markdown = self.html_to_markdown(html)
                    url = urljoin(self.BASE_URL, path)
                    chunks = self.chunk_by_sections(markdown, name, url, is_fields_page=False)
                    all_chunks.extend(chunks)
                    print(f"    ✓ {len(chunks)} chunks")
                except Exception as e:
                    print(f"    ✗ Error: {e}", file=sys.stderr)

        return all_chunks


def main():
    """CLI for doc scraper."""
    parser = argparse.ArgumentParser(
        description="Scrape openFDA device documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m rag.scraper --output docs/corpus.json
        """,
    )
    parser.add_argument(
        "--output",
        default="docs/corpus.json",
        help="Output JSON file for doc chunks (default: docs/corpus.json)",
    )
    parser.add_argument("--config", help="Path to config file (unused, reserved)")
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO"
    )

    args = parser.parse_args()

    scraper = DocScraper()
    chunks = scraper.scrape_all()

    # Save to JSON
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w") as f:
        json.dump([chunk.model_dump() for chunk in chunks], f, indent=2)

    print(f"\n✓ Scraped {len(chunks)} chunks → {output_path}")


if __name__ == "__main__":
    main()
