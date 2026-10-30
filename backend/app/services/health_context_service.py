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

# Keywords that indicate a result is a general guide/article (not an alert)
GENERAL_INFO_KEYWORDS = [
    "guide", "tips", "how to", "protect", "prevention", "precaution",
    "stay safe", "health guide", "awareness", "what you need to know",
    "things to do", "home remedies", "ayurvedic",
]

# Keywords that indicate a result is a specific outbreak/alert
ALERT_KEYWORDS = [
    "outbreak", "cases", "surge", "alert", "deaths", "fatal", "reported",
    "confirmed", "rising", "spike", "emergency", "epidemic", "warning",
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


def is_known_city(city: str) -> bool:
    """Check if city is in our known city-to-state map."""
    return city.lower().strip() in CITY_TO_STATE


def classify_source_type(url: str) -> str:
    """Classify source type based on URL domain. All remain 'reported' regardless."""
    url_lower = url.lower()
    if any(domain in url_lower for domain in ["gov.in", "nic.in", "mohfw", "who.int", "icmr"]):
        return "government"
    elif any(domain in url_lower for domain in ["ndtv", "timesofindia", "hindustantimes", "thehindu", "indianexpress", "livemint", "economictimes", "news18"]):
        return "news"
    return "unverified"


def classify_claim_type(title: str, content: str) -> str:
    """
    Classify whether the result is a general health guide or a specific alert.
    Returns: "reported_alert" | "general_info" | "news"
    """
    text_lower = f"{title} {content}".lower()

    # Check for alert keywords first (higher priority)
    alert_matches = sum(1 for kw in ALERT_KEYWORDS if kw in text_lower)
    if alert_matches >= 2:
        return "reported_alert"

    # Check for general guide keywords
    guide_matches = sum(1 for kw in GENERAL_INFO_KEYWORDS if kw in text_lower)
    if guide_matches >= 1:
        return "general_info"

    return "news"


def build_claim_text(title: str, content: str, claim_type: str, disease_keywords: list[str]) -> str:
    """
    Build a concise claim text based on the claim type.
    - For alerts: keep the original title (it's usually specific)
    - For general info: rewrite as "Seasonal reference: ..."
    """
    if claim_type == "reported_alert":
        # Keep the original title — it's likely something like "Alert in Gujarat due to..."
        return title.strip()

    elif claim_type == "general_info":
        # Rewrite to make it clear this is general seasonal info
        if disease_keywords:
            diseases = ", ".join(disease_keywords[:4])
            return f"Seasonal health reference: {diseases} risks highlighted"
        else:
            return f"General seasonal health information"

    else:
        # News — keep title but it's generic
        return title.strip()


def extract_disease_keywords(text: str) -> list[str]:
    """Extract known disease names mentioned in the text."""
    text_lower = text.lower()
    found = []
    for disease in DISEASE_NAMES:
        if disease in text_lower:
            found.append(disease)
    return list(set(found))


# Domains to exclude (irrelevant or low-quality for health context)
EXCLUDED_DOMAINS = [
    "youtube.com", "youtu.be", "tiktok.com", "instagram.com",
    "facebook.com", "twitter.com", "x.com", "reddit.com",
    "pinterest.com", "quora.com",
]


def is_excluded_domain(url: str) -> bool:
    """Check if URL is from an excluded domain."""
    url_lower = url.lower()
    return any(domain in url_lower for domain in EXCLUDED_DOMAINS)


def is_health_relevant(text: str) -> bool:
    """Check if a search result is health-related."""
    text_lower = text.lower()
    matches = sum(1 for kw in HEALTH_KEYWORDS if kw in text_lower)
    return matches >= 2  # At least 2 health keywords present


def determine_region_match(result_text: str, city: str, state: str) -> str:
    """
    Determine how closely the result matches the patient's location.
    Returns: "local" | "regional" | "general"
    """
    text_lower = result_text.lower()
    city_lower = city.lower().strip()

    if city_lower and city_lower in text_lower:
        return "local"
    elif state and state.lower() in text_lower:
        return "regional"
    else:
        return "general"


# Specialties where regional disease/outbreak context is NOT relevant
SKIP_CONTEXT_SPECIALTIES = [
    "orthopedic",
    "ophthalmology",
    "general_surgery",
    "psychiatry",
    "urology",
]

# Specialty-specific search query templates
SPECIALTY_SEARCH_QUERIES: dict[str, list[str]] = {
    "general_md": [
        "disease outbreak health alert {location} {month} {year}",
        "health advisory {state_or_city} {season} {year} India",
    ],
    "cardiology": [
        "heart disease cardiovascular health alert {state_or_city} {year}",
        "cardiac cases trends India {season} {year}",
    ],
    "neurology": [
        "neurological disease cases {state_or_city} {year}",
        "encephalitis brain infection {state_or_city} {season} {year}",
    ],
    "dermatology": [
        "skin infection fungal disease {state_or_city} {season} {year}",
        "dermatology skin problems {season} India {year}",
    ],
    "gastroenterology": [
        "food poisoning gastro diarrhea outbreak {location} {month} {year}",
        "waterborne disease {state_or_city} {season} {year} India",
    ],
    "ent": [
        "respiratory viral infection ENT {state_or_city} {season} {year}",
        "cold flu sore throat cases {state_or_city} {month} {year}",
    ],
    "gynecology": [
        "women health maternal health {state_or_city} {year}",
        "pregnancy health advisory India {season} {year}",
    ],
    "psychiatry": [
        "mental health depression anxiety trends India {year}",
        "mental health awareness {state_or_city} {year}",
    ],
    "pulmonology": [
        "respiratory infection air pollution AQI {location} {month} {year}",
        "lung disease asthma COPD {state_or_city} {season} {year}",
    ],
    "urology": [
        "kidney urinary infection cases {state_or_city} {season} {year}",
        "UTI kidney stone health {state_or_city} {year}",
    ],
}


def _build_specialty_queries(
    city: str, state: str, season: str, month: str, year: int, specialty: str
) -> list[str]:
    """Build search queries based on specialty and location."""
    location = f"{city} {state}".strip() if is_known_city(city) else (state or city)
    state_or_city = state or city

    # Get specialty-specific query templates (fall back to general_md)
    templates = SPECIALTY_SEARCH_QUERIES.get(specialty, SPECIALTY_SEARCH_QUERIES["general_md"])

    queries = []
    for template in templates:
        query = template.format(
            location=location,
            city=city,
            state=state,
            state_or_city=state_or_city,
            season=season,
            month=month,
            year=year,
        )
        queries.append(query)

    return queries


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

    def gather_context(self, city: str, state: str = "", specialty: str = "general_md") -> HealthContext:
        """
        Gather local health context for a patient's location and specialty.

        Args:
            city: Patient's city (free text from registration)
            state: Patient's state (auto-inferred from city if not provided)
            specialty: Patient's specialty (used to make search relevant)

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

        # Skip health context search for specialties where it's not relevant
        if specialty in SKIP_CONTEXT_SPECIALTIES:
            return context

        # Perform searches and gather alerts
        try:
            alerts = self._search_health_context(city, state, season, now, specialty)
            context.local_alerts = alerts
        except Exception:
            # Graceful degradation: if search fails, AI works without context
            pass

        return context

    def _search_health_context(
        self, city: str, state: str, season: str, now: datetime, specialty: str = "general_md"
    ) -> list[HealthAlert]:
        """Perform Tavily searches and return structured health alerts."""
        month_name = now.strftime("%B")
        year = now.year

        # Build specialty-aware search queries
        queries = _build_specialty_queries(city, state, season, month_name, year, specialty)

        all_results = []
        retrieved_at = now.isoformat()

        for query in queries:
            try:
                response = self.client.search(
                    query=query,
                    search_depth="basic",
                    max_results=5,
                    include_answer=False,
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

            # Filter: exclude social media / video platforms
            if is_excluded_domain(url):
                continue

            # Filter: must be health-relevant
            if not is_health_relevant(full_text):
                continue

            # Filter: minimum relevance score
            if score < 0.70:
                continue

            # Extract disease keywords and classify
            disease_keywords = extract_disease_keywords(full_text)
            claim_type = classify_claim_type(title, content)
            region_match = determine_region_match(full_text, city, state)

            # Build better claim text based on type
            claim = build_claim_text(title, content, claim_type, disease_keywords)

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
                disease_keywords=disease_keywords,
                region_match=region_match,
                published_at=published_date,
                retrieved_at=retrieved_at,
            )
            alerts.append(alert)

        # Sort: alerts first, then by relevance score. Cap at 3 results max.
        alerts.sort(key=lambda a: (
            0 if classify_claim_type(a.claim, "") == "reported_alert" else 1,
            -a.relevance_score,
        ))
        return alerts[:3]


def _extract_source_name(url: str) -> str:
    """Extract a readable source name from a URL."""
    try:
        domain = url.split("//")[-1].split("/")[0]
        domain = domain.replace("www.", "")
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
            "globalriskatlas.com": "Global Risk Atlas",
        }
        return domain_names.get(domain, domain)
    except Exception:
        return "Unknown"
