"""
Local Health Context Service

Gathers location-aware and season-aware health context at patient registration time.
Uses Tavily search to retrieve recent health-related information for the patient's area.

IMPORTANT: This is NOT an outbreak database. It retrieves web information that MAY contain
health alerts. All results are marked as "reported" — never "confirmed" — because web
search results are not verified public health data.
"""

import re
from datetime import datetime, timezone

from tavily import TavilyClient

from app.config import settings
from app.models.session import HealthAlert, HealthContext


# Indian states mapped from common city names (for search context)
CITY_TO_STATE: dict[str, str] = {
    "mumbai": "Maharashtra",
    "pune": "Maharashtra",
    "nagpur": "Maharashtra",
    "nashik": "Maharashtra",
    "aurangabad": "Maharashtra",
    "thane": "Maharashtra",
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "noida": "Uttar Pradesh",
    "gurgaon": "Haryana",
    "gurugram": "Haryana",
    "bangalore": "Karnataka",
    "bengaluru": "Karnataka",
    "chennai": "Tamil Nadu",
    "hyderabad": "Telangana",
    "kolkata": "West Bengal",
    "ahmedabad": "Gujarat",
    "surat": "Gujarat",
    "vadodara": "Gujarat",
    "rajkot": "Gujarat",
    "jaipur": "Rajasthan",
    "lucknow": "Uttar Pradesh",
    "kanpur": "Uttar Pradesh",
    "patna": "Bihar",
    "bhopal": "Madhya Pradesh",
    "indore": "Madhya Pradesh",
    "chandigarh": "Chandigarh",
    "kochi": "Kerala",
    "thiruvananthapuram": "Kerala",
    "kozhikode": "Kerala",
    "guwahati": "Assam",
    "bhubaneswar": "Odisha",
    "visakhapatnam": "Andhra Pradesh",
    "coimbatore": "Tamil Nadu",
    "madurai": "Tamil Nadu",
    "mangalore": "Karnataka",
    "mysore": "Karnataka",
    "mysuru": "Karnataka",
    "dehradun": "Uttarakhand",
    "ranchi": "Jharkhand",
    "raipur": "Chhattisgarh",
    "jammu": "Jammu & Kashmir",
    "srinagar": "Jammu & Kashmir",
    "shimla": "Himachal Pradesh",
    "panaji": "Goa",
    "agartala": "Tripura",
    "imphal": "Manipur",
    "gangtok": "Sikkim",
    "varanasi": "Uttar Pradesh",
    "allahabad": "Uttar Pradesh",
    "prayagraj": "Uttar Pradesh",
    "amritsar": "Punjab",
    "ludhiana": "Punjab",
    "jalandhar": "Punjab",
    "jodhpur": "Rajasthan",
    "udaipur": "Rajasthan",
    "tiruchirappalli": "Tamil Nadu",
    "trichy": "Tamil Nadu",
    "nagapattinam": "Tamil Nadu",
    "pondicherry": "Puducherry",
    "puducherry": "Puducherry",
}

# Health-related keywords for filtering irrelevant results
HEALTH_KEYWORDS = [
    "disease", "outbreak", "cases", "fever", "dengue", "malaria", "virus",
    "infection", "flu", "influenza", "cholera", "typhoid", "chikungunya",
    "leptospirosis", "diarrhea", "diarrhoea", "pneumonia", "covid",
    "nipah", "zika", "measles", "tuberculosis", "tb", "hepatitis",
    "jaundice", "health", "hospital", "patient", "epidemic", "pandemic",
    "alert", "advisory", "warning", "death", "fatal", "chandipura",
    "encephalitis", "swine flu", "h1n1", "respiratory", "gastro",
    "waterborne", "mosquito", "vector", "contamination", "pollution",
]

# Known disease keywords for extraction from text
DISEASE_NAMES = [
    "dengue", "malaria", "chikungunya", "leptospirosis", "typhoid",
    "cholera", "influenza", "flu", "covid", "nipah", "zika", "measles",
    "hepatitis", "tuberculosis", "pneumonia", "encephalitis", "chandipura",
    "diarrhea", "diarrhoea", "gastroenteritis", "jaundice", "swine flu",
    "h1n1", "respiratory syncytial", "scrub typhus", "heat stroke",
    "dehydration", "food poisoning", "viral fever",
]


def detect_season(date: datetime | None = None) -> str:
    """Detect Indian season from the current month."""
    if date is None:
        date = datetime.now(timezone.utc)
    month = date.month
    if month in (6, 7, 8, 9):
        return "monsoon"
    elif month in (11, 12, 1, 2):
        return "winter"
    else:  # 3, 4, 5, 10
        return "summer"


def infer_state(city: str) -> str:
    """Infer state from city name. Returns empty string if unknown."""
    return CITY_TO_STATE.get(city.lower().strip(), "")


def classify_source_type(url: str) -> str:
    """Classify source type based on URL domain. All remain 'reported' regardless."""
    url_lower = url.lower()
    if any(domain in url_lower for domain in ["gov.in", "nic.in", "mohfw", "who.int", "icmr"]):
        return "government"
    elif any(domain in url_lower for domain in ["ndtv", "timesofindia", "hindustantimes", "thehindu", "indianexpress", "livemint", "economictimes", "news18"]):
        return "news"
    return "unverified"


def extract_disease_keywords(text: str) -> list[str]:
    """Extract known disease names mentioned in the text."""
    text_lower = text.lower()
    found = []
    for disease in DISEASE_NAMES:
        if disease in text_lower:
            found.append(disease)
    return list(set(found))


def is_health_relevant(text: str) -> bool:
    """Check if a search result is health-related."""
    text_lower = text.lower()
    matches = sum(1 for kw in HEALTH_KEYWORDS if kw in text_lower)
    return matches >= 2  # At least 2 health keywords present


def determine_region_match(result_text: str, city: str, state: str) -> str:
    """Determine how closely the result matches the patient's location."""
    text_lower = result_text.lower()
    city_lower = city.lower().strip()

    if city_lower and city_lower in text_lower:
        return "exact_city"
    elif state and state.lower() in text_lower:
        return "same_state"
    elif any(s.lower() in text_lower for s in CITY_TO_STATE.values()):
        return "nearby_state"
    return "national"


class HealthContextService:
    """
    Local Health Context Service.

    Gathers health-related context for a patient's location and season.
    Calls Tavily search at registration time (once per session).
    Results are stored as structured data on the session for auditability.
    """

    def __init__(self):
        self.client = None
        if settings.tavily_api_key:
            self.client = TavilyClient(api_key=settings.tavily_api_key)

    def gather_context(self, city: str, state: str = "") -> HealthContext:
        """
        Gather local health context for a patient's location.

        Args:
            city: Patient's city (free text from registration)
            state: Patient's state (auto-inferred from city if not provided)

        Returns:
            HealthContext with season, location, and any relevant health alerts.
            If Tavily is unavailable or fails, returns context with empty alerts (graceful degradation).
        """
        now = datetime.now(timezone.utc)
        season = detect_season(now)

        # Infer state if not provided
        if not state:
            state = infer_state(city)

        # Build base context (always available, even if search fails)
        context = HealthContext(
            city=city.strip(),
            state=state,
            date=now.strftime("%Y-%m-%d"),
            season=season,
            local_alerts=[],
        )

        # If Tavily is not configured, return context without alerts
        if not self.client:
            return context

        # Perform searches and gather alerts
        try:
            alerts = self._search_health_context(city, state, season, now)
            context.local_alerts = alerts
        except Exception:
            # Graceful degradation: if search fails, AI works without context
            pass

        return context

    def _search_health_context(
        self, city: str, state: str, season: str, now: datetime
    ) -> list[HealthAlert]:
        """Perform Tavily searches and return structured health alerts."""
        month_name = now.strftime("%B")
        year = now.year
        location = f"{city} {state}".strip()

        # Two focused searches
        queries = [
            f"disease outbreak health alert {location} {month_name} {year}",
            f"health advisory {state or city} {season} {year} India",
        ]

        all_results = []
        retrieved_at = now.isoformat()

        for query in queries:
            try:
                response = self.client.search(
                    query=query,
                    search_depth="basic",
                    max_results=5,
                    include_answer=False,  # Raw content only, no AI-generated summary
                    include_raw_content=False,
                )
                results = response.get("results", [])
                all_results.extend(results)
            except Exception:
                continue

        # Process and filter results
        alerts: list[HealthAlert] = []
        seen_claims: set[str] = set()

        for result in all_results:
            title = result.get("title", "")
            content = result.get("content", "")
            url = result.get("url", "")
            score = result.get("score", 0.0)
            published_date = result.get("published_date", None)

            # Combine title and content for analysis
            full_text = f"{title} {content}"

            # Filter: must be health-relevant
            if not is_health_relevant(full_text):
                continue

            # Filter: minimum relevance score
            if score < 0.70:
                continue

            # Build claim from title (concise)
            claim = title.strip()
            if not claim:
                # Use first sentence of content as claim
                claim = content.split(".")[0].strip() if content else ""

            if not claim or claim in seen_claims:
                continue
            seen_claims.add(claim)

            # Extract metadata
            alert = HealthAlert(
                claim=claim,
                source=_extract_source_name(url),
                url=url,
                source_type=classify_source_type(url),
                verification_status="reported",
                relevance_score=round(score, 2),
                disease_keywords=extract_disease_keywords(full_text),
                region_match=determine_region_match(full_text, city, state),
                published_at=published_date,
                retrieved_at=retrieved_at,
            )
            alerts.append(alert)

        # Sort by relevance score (highest first) and cap at 5
        alerts.sort(key=lambda a: a.relevance_score, reverse=True)
        return alerts[:5]


def _extract_source_name(url: str) -> str:
    """Extract a readable source name from a URL."""
    try:
        # Get domain without www
        domain = url.split("//")[-1].split("/")[0]
        domain = domain.replace("www.", "")
        # Map known domains to readable names
        domain_names = {
            "timesofindia.indiatimes.com": "Times of India",
            "ndtv.com": "NDTV",
            "hindustantimes.com": "Hindustan Times",
            "thehindu.com": "The Hindu",
            "indianexpress.com": "Indian Express",
            "livemint.com": "Livemint",
            "news18.com": "News18",
            "who.int": "WHO",
            "mohfw.gov.in": "Ministry of Health (India)",
            "economictimes.indiatimes.com": "Economic Times",
        }
        return domain_names.get(domain, domain)
    except Exception:
        return "Unknown"
