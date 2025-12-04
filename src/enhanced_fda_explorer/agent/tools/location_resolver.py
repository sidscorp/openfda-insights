"""
Location Resolver Tool - Resolve geographic locations to manufacturers and devices.
"""
from typing import Type, Optional
from collections import Counter
import time
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import httpx

from ...models.responses import LocationContext
from ...openfda_client import OpenFDAClient


COUNTRY_CODES = {
    "united states": "US", "usa": "US", "us": "US", "america": "US",
    "china": "CN", "chinese": "CN", "prc": "CN",
    "germany": "DE", "german": "DE",
    "japan": "JP", "japanese": "JP",
    "united kingdom": "GB", "uk": "GB", "britain": "GB", "british": "GB", "england": "GB",
    "france": "FR", "french": "FR",
    "canada": "CA", "canadian": "CA",
    "mexico": "MX", "mexican": "MX",
    "south korea": "KR", "korea": "KR", "korean": "KR",
    "taiwan": "TW", "taiwanese": "TW",
    "italy": "IT", "italian": "IT",
    "netherlands": "NL", "dutch": "NL", "holland": "NL",
    "switzerland": "CH", "swiss": "CH",
    "australia": "AU", "australian": "AU",
    "india": "IN", "indian": "IN",
    "ireland": "IE", "irish": "IE",
    "belgium": "BE", "belgian": "BE",
    "israel": "IL", "israeli": "IL",
    "denmark": "DK", "danish": "DK",
    "sweden": "SE", "swedish": "SE",
    "spain": "ES", "spanish": "ES",
    "brazil": "BR", "brazilian": "BR",
    "singapore": "SG",
    "hong kong": "HK",
    "austria": "AT", "austrian": "AT",
    "poland": "PL", "polish": "PL",
    "czech republic": "CZ", "czech": "CZ", "czechia": "CZ",
    "vietnam": "VN", "vietnamese": "VN",
    "thailand": "TH", "thai": "TH",
    "malaysia": "MY", "malaysian": "MY",
    "indonesia": "ID", "indonesian": "ID",
    "philippines": "PH", "filipino": "PH",
    "puerto rico": "PR",
    "costa rica": "CR",
}

COUNTRY_NAMES = {
    "US": "United States", "CN": "China", "DE": "Germany", "JP": "Japan",
    "GB": "United Kingdom", "FR": "France", "CA": "Canada", "MX": "Mexico",
    "KR": "South Korea", "TW": "Taiwan", "IT": "Italy", "NL": "Netherlands",
    "CH": "Switzerland", "AU": "Australia", "IN": "India", "IE": "Ireland",
    "BE": "Belgium", "IL": "Israel", "DK": "Denmark", "SE": "Sweden",
    "ES": "Spain", "BR": "Brazil", "SG": "Singapore", "HK": "Hong Kong",
    "AT": "Austria", "PL": "Poland", "CZ": "Czech Republic", "VN": "Vietnam",
    "TH": "Thailand", "MY": "Malaysia", "ID": "Indonesia", "PH": "Philippines",
    "PR": "Puerto Rico", "CR": "Costa Rica",
}

REGIONS = {
    "asia": ["CN", "JP", "KR", "TW", "IN", "SG", "HK", "TH", "MY", "ID", "PH", "VN"],
    "europe": ["DE", "GB", "FR", "IT", "NL", "CH", "IE", "BE", "DK", "SE", "ES", "AT", "PL", "CZ"],
    "eu": ["DE", "FR", "IT", "NL", "IE", "BE", "DK", "SE", "ES", "AT", "PL", "CZ"],
    "north america": ["US", "CA", "MX"],
    "latin america": ["MX", "BR", "CR"],
    "apac": ["CN", "JP", "KR", "TW", "IN", "SG", "HK", "AU", "TH", "MY", "ID", "PH", "VN"],
}

US_STATES = {
    "california": "CA", "ca": "CA",
    "texas": "TX", "tx": "TX",
    "florida": "FL", "fl": "FL",
    "new york": "NY", "ny": "NY",
    "massachusetts": "MA", "ma": "MA",
    "illinois": "IL", "il": "IL",
    "pennsylvania": "PA", "pa": "PA",
    "new jersey": "NJ", "nj": "NJ",
    "minnesota": "MN", "mn": "MN",
    "ohio": "OH", "oh": "OH",
    "georgia": "GA", "ga": "GA",
    "north carolina": "NC", "nc": "NC",
    "michigan": "MI", "mi": "MI",
    "arizona": "AZ", "az": "AZ",
    "colorado": "CO", "co": "CO",
    "washington": "WA", "wa": "WA",
    "oregon": "OR", "or": "OR",
    "maryland": "MD", "md": "MD",
    "virginia": "VA", "va": "VA",
    "connecticut": "CT", "ct": "CT",
    "indiana": "IN", "in": "IN",
    "wisconsin": "WI", "wi": "WI",
    "tennessee": "TN", "tn": "TN",
    "missouri": "MO", "mo": "MO",
    "utah": "UT", "ut": "UT",
    "nevada": "NV", "nv": "NV",
    "south carolina": "SC", "sc": "SC",
    "alabama": "AL", "al": "AL",
    "kentucky": "KY", "ky": "KY",
    "louisiana": "LA", "la": "LA",
    "oklahoma": "OK", "ok": "OK",
    "iowa": "IA", "ia": "IA",
    "kansas": "KS", "ks": "KS",
    "nebraska": "NE", "ne": "NE",
    "new hampshire": "NH", "nh": "NH",
    "rhode island": "RI", "ri": "RI",
    "delaware": "DE", "de": "DE",
    "maine": "ME", "me": "ME",
    "vermont": "VT", "vt": "VT",
    "arkansas": "AR", "ar": "AR",
    "mississippi": "MS", "ms": "MS",
    "new mexico": "NM", "nm": "NM",
    "idaho": "ID", "id": "ID",
    "montana": "MT", "mt": "MT",
    "wyoming": "WY", "wy": "WY",
    "north dakota": "ND", "nd": "ND",
    "south dakota": "SD", "sd": "SD",
    "west virginia": "WV", "wv": "WV",
    "hawaii": "HI", "hi": "HI",
    "alaska": "AK", "ak": "AK",
}

STATE_NAMES = {
    "CA": "California", "TX": "Texas", "FL": "Florida", "NY": "New York",
    "MA": "Massachusetts", "IL": "Illinois", "PA": "Pennsylvania", "NJ": "New Jersey",
    "MN": "Minnesota", "OH": "Ohio", "GA": "Georgia", "NC": "North Carolina",
    "MI": "Michigan", "AZ": "Arizona", "CO": "Colorado", "WA": "Washington",
    "OR": "Oregon", "MD": "Maryland", "VA": "Virginia", "CT": "Connecticut",
}


class LocationResolverInput(BaseModel):
    location: str = Field(description="Country name, region, or US state (e.g., 'China', 'Europe', 'California')")
    device_type: Optional[str] = Field(default=None, description="Optional device type filter (e.g., 'mask', 'ventilator')")
    limit: int = Field(default=100, description="Maximum results per country/state")


class LocationResolverTool(BaseTool):
    name: str = "resolve_location"
    description: str = """Find medical device manufacturers by geographic location.
    Supports countries (China, Germany, Japan), regions (Asia, Europe, EU), and US states (California, Texas).
    Returns manufacturer counts, top companies, and device types made in that location."""
    args_schema: Type[BaseModel] = LocationResolverInput

    _api_key: Optional[str] = None
    _last_structured_result: Optional[LocationContext] = None
    _client: OpenFDAClient

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._api_key = api_key
        self._client = OpenFDAClient(api_key=api_key)

    def get_last_structured_result(self) -> Optional[LocationContext]:
        return self._last_structured_result

    def _run(self, location: str, device_type: Optional[str] = None, limit: int = 100) -> str:
        location_lower = location.lower().strip()
        self._last_structured_result = None

        if location_lower in REGIONS:
            return self._search_region(location_lower, REGIONS[location_lower], device_type, limit)

        if location_lower in US_STATES:
            return self._search_state(US_STATES[location_lower], device_type, limit)

        if location_lower in COUNTRY_CODES:
            return self._search_country(COUNTRY_CODES[location_lower], device_type, limit)

        if len(location) == 2 and location.upper() in COUNTRY_NAMES:
            return self._search_country(location.upper(), device_type, limit)

        if len(location) == 2 and location.upper() in STATE_NAMES:
            return self._search_state(location.upper(), device_type, limit)

        return f"Unknown location: '{location}'. Try a country (China, Germany), region (Asia, Europe), or US state (California, TX)."

    def _search_country(self, country_code: str, device_type: Optional[str], limit: int) -> str:
        search = f"registration.iso_country_code:{country_code}"
        if device_type:
            search += f" AND (proprietary_name:{device_type} OR products.openfda.device_name:{device_type})"

        return self._execute_search(
            search,
            COUNTRY_NAMES.get(country_code, country_code),
            "country",
            limit,
            country_codes=[country_code],
            device_type_filter=device_type
        )

    def _search_state(self, state_code: str, device_type: Optional[str], limit: int) -> str:
        search = f"registration.state_code:{state_code}"
        if device_type:
            search += f" AND (proprietary_name:{device_type} OR products.openfda.device_name:{device_type})"

        return self._execute_search(
            search,
            STATE_NAMES.get(state_code, state_code),
            "state",
            limit,
            state_code=state_code,
            device_type_filter=device_type
        )

    def _search_region(self, region_name: str, country_codes: list, device_type: Optional[str], limit: int) -> str:
        lines = [f"Medical device manufacturers in {region_name.upper()}:\n"]
        total_establishments = 0
        country_totals = {}

        for code in country_codes:
            search = f"registration.iso_country_code:{code}"
            if device_type:
                search += f" AND (proprietary_name:{device_type} OR products.openfda.device_name:{device_type})"

            try:
                data = self._fetch(search, 1)
                count = data.get("meta", {}).get("results", {}).get("total", 0)
                if count > 0:
                    country_totals[code] = count
                    total_establishments += count
            except Exception:
                continue

        lines.append(f"Total registered establishments: {total_establishments:,}\n")
        lines.append("BY COUNTRY:")
        for code, count in sorted(country_totals.items(), key=lambda x: x[1], reverse=True):
            name = COUNTRY_NAMES.get(code, code)
            lines.append(f"  {name}: {count:,}")

        top_manufacturers = []
        top_country = max(country_totals.items(), key=lambda x: x[1])[0] if country_totals else None
        if top_country:
            lines.append(f"\nTOP COMPANIES IN {COUNTRY_NAMES.get(top_country, top_country).upper()}:")
            search = f"registration.iso_country_code:{top_country}"
            if device_type:
                search += f" AND (proprietary_name:{device_type} OR products.openfda.device_name:{device_type})"
            data = self._fetch(search, 20)
            companies = {}
            for r in data.get("results", []):
                name = r.get("registration", {}).get("name", "Unknown")
                if name not in companies:
                    companies[name] = {"city": r.get("registration", {}).get("city", "")}
            for name, info in list(companies.items())[:10]:
                city = f" ({info['city']})" if info["city"] else ""
                lines.append(f"  • {name}{city}")
                top_manufacturers.append(name)

        self._last_structured_result = LocationContext(
            location_type="region",
            location_name=region_name.title(),
            country_codes=list(country_totals.keys()),
            total_establishments=total_establishments,
            top_manufacturers=top_manufacturers,
            device_types_filter=device_type
        )

        return "\n".join(lines)

    def _execute_search(
        self,
        search: str,
        location_name: str,
        location_type: str,
        limit: int,
        country_codes: list[str] = None,
        state_code: str = None,
        device_type_filter: str = None
    ) -> str:
        try:
            data = self._fetch_all(search, limit)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return f"No manufacturers found in {location_name}."
            return f"FDA API error: {str(e)}"
        except Exception as e:
            return f"Error: {str(e)}"

        results = data.get("results", [])
        total = data.get("meta", {}).get("results", {}).get("total", 0)

        if not results:
            return f"No manufacturers found in {location_name}."

        lines = [f"Medical device manufacturers in {location_name}:\n"]
        lines.append(f"Total registered establishments: {total:,}\n")

        companies = Counter()
        city_counts = Counter()
        device_types = Counter()
        company_cities: dict[str, str] = {}

        for result in results:
            reg = result.get("registration", {})
            name = reg.get("name", "Unknown")
            city = reg.get("city", "")

            companies[name] += 1
            if city and name not in company_cities:
                company_cities[name] = city
            if city:
                city_counts[city] += 1

            for prod in result.get("products", []):
                openfda = prod.get("openfda", {})
                device_name = openfda.get("device_name", "")
                if device_name:
                    device_types[device_name] += 1

        if city_counts:
            lines.append("TOP CITIES:")
            for city, count in city_counts.most_common(10):
                lines.append(f"  {city}: {count}")

        if device_types:
            lines.append("\nTOP DEVICE TYPES MADE HERE:")
            for dtype, count in device_types.most_common(15):
                lines.append(f"  {dtype}: {count}")

        lines.append(f"\nTOP COMPANIES (showing up to {min(20, len(companies))}):")
        top_manufacturers = []
        for name, count in companies.most_common(20):
            city_str = f" - {company_cities.get(name, '')}" if company_cities.get(name) else ""
            lines.append(f"  • {name}{city_str} ({count} records)")
            top_manufacturers.append(name)

        self._last_structured_result = LocationContext(
            location_type=location_type,
            location_name=location_name,
            country_codes=country_codes or [],
            state_code=state_code,
            total_establishments=total,
            top_manufacturers=top_manufacturers,
            device_types_filter=device_type_filter
        )

        return "\n".join(lines)

    def _fetch(self, search: str, limit: int) -> dict:
        params = {"search": search, "limit": min(limit, 100)}
        return self._client.get("device/registrationlisting.json", params=params)

    def _fetch_all(self, search: str, max_records: int) -> dict:
        """Fetch and aggregate up to max_records across pages."""
        params = {"search": search}
        return self._client.get_paginated(
            "device/registrationlisting.json",
            params=params,
            limit=max_records,
            page_size=100,
        )

    async def _fetch_async(self, search: str, limit: int) -> dict:
        params = {"search": search, "limit": min(limit, 100)}
        return await self._client.aget("device/registrationlisting.json", params=params)

    async def _fetch_all_async(self, search: str, max_records: int) -> dict:
        return await self._client.aget_paginated(
            "device/registrationlisting.json",
            params={"search": search},
            limit=max_records,
            page_size=100,
        )

    async def _arun(self, location: str, device_type: Optional[str] = None, limit: int = 100) -> str:
        """Async version using httpx for non-blocking HTTP calls."""
        start_time = time.time()
        location_lower = location.lower().strip()
        self._last_structured_result = None

        if location_lower in REGIONS:
            result = await self._search_region_async(location_lower, REGIONS[location_lower], device_type, limit)
        elif location_lower in US_STATES:
            result = await self._search_state_async(US_STATES[location_lower], device_type, limit)
        elif location_lower in COUNTRY_CODES:
            result = await self._search_country_async(COUNTRY_CODES[location_lower], device_type, limit)
        elif len(location) == 2 and location.upper() in COUNTRY_NAMES:
            result = await self._search_country_async(location.upper(), device_type, limit)
        elif len(location) == 2 and location.upper() in STATE_NAMES:
            result = await self._search_state_async(location.upper(), device_type, limit)
        else:
            return f"Unknown location: '{location}'. Try a country (China, Germany), region (Asia, Europe), or US state (California, TX)."

        elapsed_ms = (time.time() - start_time) * 1000
        return f"{result}\n\n[Query completed in {elapsed_ms:.0f}ms]"

    async def _search_country_async(self, country_code: str, device_type: Optional[str], limit: int) -> str:
        search = f"registration.iso_country_code:{country_code}"
        if device_type:
            search += f" AND (proprietary_name:{device_type} OR products.openfda.device_name:{device_type})"

        return await self._execute_search_async(
            search,
            COUNTRY_NAMES.get(country_code, country_code),
            "country",
            limit,
            country_codes=[country_code],
            device_type_filter=device_type
        )

    async def _search_state_async(self, state_code: str, device_type: Optional[str], limit: int) -> str:
        search = f"registration.state_code:{state_code}"
        if device_type:
            search += f" AND (proprietary_name:{device_type} OR products.openfda.device_name:{device_type})"

        return await self._execute_search_async(
            search,
            STATE_NAMES.get(state_code, state_code),
            "state",
            limit,
            state_code=state_code,
            device_type_filter=device_type
        )

    async def _search_region_async(self, region_name: str, country_codes: list, device_type: Optional[str], limit: int) -> str:
        import asyncio
        lines = [f"Medical device manufacturers in {region_name.upper()}:\n"]
        total_establishments = 0
        country_totals = {}

        async def fetch_country_count(code: str) -> tuple:
            search = f"registration.iso_country_code:{code}"
            if device_type:
                search += f" AND (proprietary_name:{device_type} OR products.openfda.device_name:{device_type})"
            try:
                data = await self._fetch_async(search, 1)
                count = data.get("meta", {}).get("results", {}).get("total", 0)
                return code, count
            except Exception:
                return code, 0

        results = await asyncio.gather(*[fetch_country_count(code) for code in country_codes])
        for code, count in results:
            if count > 0:
                country_totals[code] = count
                total_establishments += count

        lines.append(f"Total registered establishments: {total_establishments:,}\n")
        lines.append("BY COUNTRY:")
        for code, count in sorted(country_totals.items(), key=lambda x: x[1], reverse=True):
            name = COUNTRY_NAMES.get(code, code)
            lines.append(f"  {name}: {count:,}")

        top_manufacturers = []
        top_country = max(country_totals.items(), key=lambda x: x[1])[0] if country_totals else None
        if top_country:
            lines.append(f"\nTOP COMPANIES IN {COUNTRY_NAMES.get(top_country, top_country).upper()}:")
            search = f"registration.iso_country_code:{top_country}"
            if device_type:
                search += f" AND (proprietary_name:{device_type} OR products.openfda.device_name:{device_type})"
            data = await self._fetch_async(search, 20)
            companies = {}
            for r in data.get("results", []):
                name = r.get("registration", {}).get("name", "Unknown")
                if name not in companies:
                    companies[name] = {"city": r.get("registration", {}).get("city", "")}
            for name, info in list(companies.items())[:10]:
                city = f" ({info['city']})" if info["city"] else ""
                lines.append(f"  • {name}{city}")
                top_manufacturers.append(name)

        self._last_structured_result = LocationContext(
            location_type="region",
            location_name=region_name.title(),
            country_codes=list(country_totals.keys()),
            total_establishments=total_establishments,
            top_manufacturers=top_manufacturers,
            device_types_filter=device_type
        )

        return "\n".join(lines)

    async def _execute_search_async(
        self,
        search: str,
        location_name: str,
        location_type: str,
        limit: int,
        country_codes: list[str] = None,
        state_code: str = None,
        device_type_filter: str = None
    ) -> str:
        try:
            data = await self._fetch_all_async(search, limit)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return f"No manufacturers found in {location_name}."
            return f"FDA API error: {str(e)}"
        except Exception as e:
            return f"Error: {str(e)}"

        results = data.get("results", [])
        total = data.get("meta", {}).get("results", {}).get("total", 0)

        if not results:
            return f"No manufacturers found in {location_name}."

        lines = [f"Medical device manufacturers in {location_name}:\n"]
        lines.append(f"Total registered establishments: {total:,}\n")

        companies = {}
        device_types = Counter()
        cities = Counter()

        for result in results:
            reg = result.get("registration", {})
            name = reg.get("name", "Unknown")
            city = reg.get("city", "")

            if name not in companies:
                companies[name] = {"city": city, "products": []}

            if city:
                cities[city] += 1

            for prod in result.get("products", []):
                openfda = prod.get("openfda", {})
                device_name = openfda.get("device_name", "")
                if device_name:
                    device_types[device_name] += 1
                    if device_name not in companies[name]["products"]:
                        companies[name]["products"].append(device_name)

        if cities:
            lines.append("TOP CITIES:")
            for city, count in cities.most_common(10):
                lines.append(f"  {city}: {count}")

        if device_types:
            lines.append("\nTOP DEVICE TYPES MADE HERE:")
            for dtype, count in device_types.most_common(15):
                lines.append(f"  {dtype}: {count}")

        lines.append(f"\nTOP COMPANIES ({len(companies)} shown):")
        top_manufacturers = []
        for name, info in list(companies.items())[:20]:
            city_str = f" - {info['city']}" if info["city"] else ""
            lines.append(f"  • {name}{city_str}")
            top_manufacturers.append(name)
            if info["products"]:
                prod_list = ", ".join(info["products"][:3])
                if len(info["products"]) > 3:
                    prod_list += f" (+{len(info['products']) - 3} more)"
                lines.append(f"    Products: {prod_list}")

        self._last_structured_result = LocationContext(
            location_type=location_type,
            location_name=location_name,
            country_codes=country_codes or [],
            state_code=state_code,
            total_establishments=total,
            top_manufacturers=top_manufacturers,
            device_types_filter=device_type_filter
        )

        return "\n".join(lines)
