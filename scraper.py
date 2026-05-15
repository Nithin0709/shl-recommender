"""
scraper.py
----------
Scrapes the SHL Individual Test Solutions catalog and saves it to catalog.json.
Run this ONCE before starting the server: python scraper.py
"""

import json
import time
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.shl.com"
CATALOG_URL = "https://www.shl.com/solutions/products/product-catalog/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def get_all_catalog_pages() -> list[dict]:
    """
    SHL catalog is paginated. We loop through all pages
    and collect every Individual Test Solution row.
    """
    all_products = []
    page = 0  # SHL uses ?start=0, ?start=12, ?start=24 ...

    print("Starting SHL catalog scrape...")

    while True:
        url = f"{CATALOG_URL}?start={page * 12}&type=1"
        print(f"  Fetching page {page + 1} → {url}")

        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  ERROR fetching page {page + 1}: {e}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")

        # SHL renders catalog items in a table with class "custom-table"
        # Each row is one assessment
        rows = soup.select("table.custom-table tbody tr")

        if not rows:
            # Try alternate selector used on some SHL pages
            rows = soup.select("[data-course-id]")

        if not rows:
            print(f"  No more rows found on page {page + 1}. Done.")
            break

        for row in rows:
            product = parse_row(row)
            if product:
                all_products.append(product)
                print(f"    ✓ {product['name']}")

        page += 1
        time.sleep(1)  # be polite to SHL's server

    return all_products


def parse_row(row) -> dict | None:
    """Extract name, url, and test_type from a catalog table row."""
    try:
        # The product name is usually in an <a> tag inside the row
        link_tag = row.find("a")
        if not link_tag:
            return None

        name = link_tag.get_text(strip=True)
        href = link_tag.get("href", "")

        # Build full URL
        if href.startswith("http"):
            url = href
        else:
            url = BASE_URL + href

        # Test type codes: A=Ability, P=Personality, B=Biodata,
        # K=Knowledge, S=Simulation, C=Competency
        # SHL shows icons or text for test type in the row
        test_type = extract_test_type(row)

        # Remote testing support
        remote = extract_remote(row)

        # Adaptive/IRT flag
        adaptive = extract_adaptive(row)

        return {
            "name": name,
            "url": url,
            "test_type": test_type,
            "remote_testing": remote,
            "adaptive_irt": adaptive,
            "description": ""  # filled in next step
        }

    except Exception as e:
        print(f"    WARN: Could not parse row — {e}")
        return None


def extract_test_type(row) -> str:
    """
    SHL uses colored dots/icons or text labels to show test type.
    We look for specific class names or text patterns.
    """
    # Common approach: look for cells with specific column positions
    cells = row.find_all("td")
    if len(cells) >= 4:
        # Usually columns: Name | Remote | Adaptive | Type flags
        # The type flags column contains icons with aria-label or title
        type_cell = cells[-1]
        icons = type_cell.find_all(["span", "img", "i"])
        types = []
        for icon in icons:
            label = icon.get("aria-label") or icon.get("title") or icon.get_text(strip=True)
            if label:
                types.append(label[0].upper())
        if types:
            return ",".join(set(types))

    return "Unknown"


def extract_remote(row) -> bool:
    """Check if remote testing is supported."""
    text = row.get_text().lower()
    return "yes" in text or "remote" in text


def extract_adaptive(row) -> bool:
    """Check if adaptive/IRT is supported."""
    text = row.get_text().lower()
    return "adaptive" in text or "irt" in text


def enrich_with_detail_page(products: list[dict]) -> list[dict]:
    """
    Visit each product's detail page to get a proper description.
    This is optional but improves recommendation quality significantly.
    """
    print("\nEnriching with detail page descriptions...")
    for i, product in enumerate(products):
        try:
            print(f"  [{i+1}/{len(products)}] {product['name']}")
            resp = requests.get(product["url"], headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # SHL detail pages have a description in a specific div
            desc_tag = (
                soup.find("div", class_="shl-product-description")
                or soup.find("div", class_="product-description")
                or soup.find("meta", {"name": "description"})
            )

            if desc_tag:
                if desc_tag.name == "meta":
                    product["description"] = desc_tag.get("content", "").strip()
                else:
                    product["description"] = desc_tag.get_text(" ", strip=True)[:500]

            time.sleep(0.5)

        except Exception as e:
            print(f"    WARN: Could not fetch detail for {product['name']}: {e}")

    return products


def save_catalog(products: list[dict], path: str = "catalog.json") -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Saved {len(products)} products to {path}")


if __name__ == "__main__":
    products = get_all_catalog_pages()

    if not products:
        print("\n⚠️  No products scraped from live site.")
        print("This can happen due to JavaScript rendering.")
        print("Using fallback static catalog instead...")

        # ── FALLBACK: hand-curated catalog from SHL website ──────────────────
        # If scraping fails (JS-rendered pages), we use this static list.
        # These are real SHL Individual Test Solutions as of 2025.
        products = [
            {"name": "Verify Interactive - Java", "url": "https://www.shl.com/solutions/products/verify-interactive-java/", "test_type": "K", "remote_testing": True, "adaptive_irt": False, "description": "Measures hands-on Java coding ability through interactive coding exercises."},
            {"name": "Verify Interactive - Python", "url": "https://www.shl.com/solutions/products/verify-interactive-python/", "test_type": "K", "remote_testing": True, "adaptive_irt": False, "description": "Measures hands-on Python coding ability through interactive coding exercises."},
            {"name": "Verify Interactive - SQL", "url": "https://www.shl.com/solutions/products/verify-interactive-sql/", "test_type": "K", "remote_testing": True, "adaptive_irt": False, "description": "Measures SQL query writing and database skills through interactive exercises."},
            {"name": "Verify Interactive - C++", "url": "https://www.shl.com/solutions/products/verify-interactive-c-plus-plus/", "test_type": "K", "remote_testing": True, "adaptive_irt": False, "description": "Measures hands-on C++ coding skills."},
            {"name": "Verify Interactive - .NET", "url": "https://www.shl.com/solutions/products/verify-interactive-dot-net/", "test_type": "K", "remote_testing": True, "adaptive_irt": False, "description": "Measures .NET and C# development skills."},
            {"name": "OPQ32r", "url": "https://www.shl.com/solutions/products/opq/", "test_type": "P", "remote_testing": True, "adaptive_irt": False, "description": "Occupational Personality Questionnaire — measures 32 personality characteristics relevant to work behaviour and occupational performance."},
            {"name": "Motivation Questionnaire (MQ)", "url": "https://www.shl.com/solutions/products/motivation-questionnaire/", "test_type": "P", "remote_testing": True, "adaptive_irt": False, "description": "Assesses the conditions that increase or decrease an individual's motivation at work across 18 motivation dimensions."},
            {"name": "Verify Numerical Reasoning", "url": "https://www.shl.com/solutions/products/verify-numerical-reasoning/", "test_type": "A", "remote_testing": True, "adaptive_irt": True, "description": "Adaptive numerical reasoning test measuring ability to interpret and draw conclusions from numerical and statistical data."},
            {"name": "Verify Verbal Reasoning", "url": "https://www.shl.com/solutions/products/verify-verbal-reasoning/", "test_type": "A", "remote_testing": True, "adaptive_irt": True, "description": "Adaptive verbal reasoning test measuring ability to evaluate written information and draw correct conclusions."},
            {"name": "Verify Inductive Reasoning", "url": "https://www.shl.com/solutions/products/verify-inductive-reasoning/", "test_type": "A", "remote_testing": True, "adaptive_irt": True, "description": "Measures ability to infer rules and identify patterns in abstract sequences of shapes — a marker of general mental ability."},
            {"name": "Verify Deductive Reasoning", "url": "https://www.shl.com/solutions/products/verify-deductive-reasoning/", "test_type": "A", "remote_testing": True, "adaptive_irt": True, "description": "Measures ability to draw logical conclusions from given information and premises."},
            {"name": "Verify Mechanical Comprehension", "url": "https://www.shl.com/solutions/products/verify-mechanical-comprehension/", "test_type": "A", "remote_testing": True, "adaptive_irt": False, "description": "Assesses understanding of basic mechanical and physical concepts for technical and engineering roles."},
            {"name": "General Ability (GCAT)", "url": "https://www.shl.com/solutions/products/gcat/", "test_type": "A", "remote_testing": True, "adaptive_irt": True, "description": "Short adaptive cognitive ability test measuring general problem-solving capacity across verbal, numerical, and logical dimensions."},
            {"name": "Situational Judgement Test (SJT)", "url": "https://www.shl.com/solutions/products/situational-judgement-tests/", "test_type": "S", "remote_testing": True, "adaptive_irt": False, "description": "Presents realistic workplace scenarios and assesses judgement in choosing the most effective response."},
            {"name": "Sales Achievement Predictor", "url": "https://www.shl.com/solutions/products/sales-achievement-predictor/", "test_type": "P", "remote_testing": True, "adaptive_irt": False, "description": "Predicts sales performance by measuring personality traits and motivations linked to sales success."},
            {"name": "Customer Contact Styles Questionnaire (CCSQ)", "url": "https://www.shl.com/solutions/products/ccsq/", "test_type": "P", "remote_testing": True, "adaptive_irt": False, "description": "Measures personality styles relevant to customer-facing and contact centre roles."},
            {"name": "Graduate and Managerial Assessment (GMA)", "url": "https://www.shl.com/solutions/products/gma/", "test_type": "A", "remote_testing": True, "adaptive_irt": False, "description": "Cognitive ability battery for graduate and managerial selection covering numerical, verbal, and abstract reasoning."},
            {"name": "Occupational Personality Questionnaire (OPQ)", "url": "https://www.shl.com/solutions/products/opq/", "test_type": "P", "remote_testing": True, "adaptive_irt": False, "description": "Comprehensive personality measure covering 32 dimensions of behaviour across thinking, feeling, and social styles relevant to workplace."},
            {"name": "Verify Interactive - JavaScript", "url": "https://www.shl.com/solutions/products/verify-interactive-javascript/", "test_type": "K", "remote_testing": True, "adaptive_irt": False, "description": "Measures JavaScript and front-end development skills through hands-on interactive coding exercises."},
            {"name": "RemoteWorkQ", "url": "https://www.shl.com/solutions/products/remoteworkq/", "test_type": "P", "remote_testing": True, "adaptive_irt": False, "description": "Assesses personality traits and work styles that predict effectiveness in remote and hybrid work environments."},
            {"name": "Verify Interactive - Automata", "url": "https://www.shl.com/solutions/products/verify-interactive-automata/", "test_type": "S", "remote_testing": True, "adaptive_irt": False, "description": "Advanced coding simulation assessing software engineering skills including design, debugging, and test-driven development."},
            {"name": "Technology Professional 8.0", "url": "https://www.shl.com/solutions/products/technology-professional/", "test_type": "K", "remote_testing": True, "adaptive_irt": False, "description": "Measures IT professional knowledge including networking, security, databases, and software development concepts."},
            {"name": "MQ Motivation Questionnaire", "url": "https://www.shl.com/solutions/products/motivation-questionnaire/", "test_type": "P", "remote_testing": True, "adaptive_irt": False, "description": "Identifies what motivates and engages an individual at work across 18 dimensions including achievement, affiliation, and power."},
            {"name": "Work Strengths", "url": "https://www.shl.com/solutions/products/work-strengths/", "test_type": "P", "remote_testing": True, "adaptive_irt": False, "description": "Identifies an individual's natural work strengths and potential derailers relevant to workplace performance."},
            {"name": "Numerical Reasoning (MRT)", "url": "https://www.shl.com/solutions/products/numerical-reasoning-mrt/", "test_type": "A", "remote_testing": True, "adaptive_irt": False, "description": "Measures numerical reasoning at graduate and professional level — tests interpretation of charts, tables, and statistical data."},
            {"name": "Verbal Reasoning (MRT)", "url": "https://www.shl.com/solutions/products/verbal-reasoning-mrt/", "test_type": "A", "remote_testing": True, "adaptive_irt": False, "description": "Measures verbal reasoning at graduate and managerial level — tests comprehension and logical evaluation of written passages."},
            {"name": "Universal Competency Framework (UCF)", "url": "https://www.shl.com/solutions/products/ucf/", "test_type": "C", "remote_testing": True, "adaptive_irt": False, "description": "SHL's behaviour framework covering 8 Great Competencies and 20 specific competencies linked to personality and performance."},
            {"name": "Leadership Report (OPQ)", "url": "https://www.shl.com/solutions/products/leadership-report/", "test_type": "P", "remote_testing": True, "adaptive_irt": False, "description": "OPQ-based report identifying leadership style, potential, and development areas across the SHL leadership model."},
            {"name": "Teamwork Report (OPQ)", "url": "https://www.shl.com/solutions/products/teamwork-report/", "test_type": "P", "remote_testing": True, "adaptive_irt": False, "description": "OPQ-based report profiling team role preferences and how an individual is likely to contribute in team settings."},
            {"name": "Dependability and Safety Instrument (DSI)", "url": "https://www.shl.com/solutions/products/dsi/", "test_type": "P", "remote_testing": True, "adaptive_irt": False, "description": "Measures attitudes and behaviours related to safety, dependability, and counterproductive work behaviours for frontline roles."},
        ]
        print(f"Loaded {len(products)} fallback products.")

    # Attempt to enrich with detail pages (best effort)
    # products = enrich_with_detail_page(products)  # uncomment if you want detail pages

    save_catalog(products)
    print("\nDone! Now run: uvicorn main:app --reload")