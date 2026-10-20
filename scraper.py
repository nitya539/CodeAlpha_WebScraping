"""
scraper.py
Scrapes book data from https://books.toscrape.com/ (a practice website),
cleans it, and saves a raw CSV and a clean CSV in the "data" folder.

Run the full scrape:      python scraper.py
Run a quick 2-category test:  python scraper.py --test
"""

import os
import sys
import time
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ----------------------------- Settings -----------------------------
BASE_URL = "https://books.toscrape.com/"
USER_AGENT = "CodeAlpha-Internship-Learning-Scraper/1.0 (educational project)"
REQUEST_DELAY = 0.5      # seconds to wait after each request (polite scraping)
TIMEOUT = 15             # give up on a request after 15 seconds
DATA_FOLDER = "data"
RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


# --------------------------- Setup functions ---------------------------
def create_session():
    """Create a requests session that retries temporary failures automatically."""
    session = requests.Session()
    retry_rules = Retry(total=3, backoff_factor=1,
                        status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry_rules))
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def load_robots_rules(session):
    """Read the site's robots.txt so we can respect its crawling rules."""
    parser = RobotFileParser()
    robots_url = urljoin(BASE_URL, "robots.txt")
    try:
        response = session.get(robots_url, timeout=TIMEOUT)
        print(f"robots.txt status code: {response.status_code}")
        if response.status_code == 200:
            print("robots.txt content:")
            print(response.text[:500])
            parser.parse(response.text.splitlines())
            parser.modified()
        else:
            print("No robots.txt rules found, so no paths are restricted.")
            parser.allow_all = True
    except requests.exceptions.RequestException as error:
        print(f"Could not read robots.txt ({error}). Continuing carefully.")
        parser.allow_all = True
    return parser


# --------------------------- Scraping functions ---------------------------
def fetch_page(session, robots, url):
    """Download one page. Returns a BeautifulSoup object, or None if it fails."""
    if not robots.can_fetch(USER_AGENT, url):
        print(f"Skipped (not allowed by robots.txt): {url}")
        return None
    try:
        response = session.get(url, timeout=TIMEOUT)
        response.raise_for_status()      # raises an error for 404, 500, etc.
        response.encoding = "utf-8"      # avoids broken £ symbols
        time.sleep(REQUEST_DELAY)        # polite delay
        return BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as error:
        print(f"Request failed for {url}: {error}")
        return None


def get_categories(session, robots):
    """Read the category names and links from the home page sidebar."""
    soup = fetch_page(session, robots, BASE_URL)
    if soup is None:
        return {}
    links = soup.select("div.side_categories ul li ul li a")
    return {link.get_text(strip=True): urljoin(BASE_URL, link["href"])
            for link in links}


def parse_book(article, page_url, category):
    """Extract the fields of one book from its <article> HTML block."""
    link = article.h3.a
    rating_classes = article.select_one("p.star-rating")["class"]  # ['star-rating', 'Three']
    return {
        "title": link["title"],
        "category": category,
        "price_text": article.select_one("p.price_color").get_text(strip=True),
        "rating_word": [c for c in rating_classes if c != "star-rating"][0],
        "availability": article.select_one("p.availability").get_text(strip=True),
        "product_url": urljoin(page_url, link["href"]),
    }


def scrape_category(session, robots, category_name, start_url):
    """Scrape all pages of one category by following the 'next' button."""
    books = []
    page_url = start_url
    while page_url:
        soup = fetch_page(session, robots, page_url)
        if soup is None:
            print(f"  Stopped early in '{category_name}' because a page failed.")
            break
        for article in soup.select("article.product_pod"):
            try:
                books.append(parse_book(article, page_url, category_name))
            except (AttributeError, KeyError, IndexError, TypeError) as error:
                print(f"  Skipped one book in '{category_name}': {error}")
        next_link = soup.select_one("li.next a")        # pagination
        page_url = urljoin(page_url, next_link["href"]) if next_link else None
    return books


def scrape_all(session, robots, max_categories=None):
    """Scrape every category (or only the first few when testing)."""
    categories = get_categories(session, robots)
    print(f"Found {len(categories)} categories")
    names = list(categories)
    if max_categories:
        names = names[:max_categories]
    all_books = []
    for number, name in enumerate(names, start=1):
        books = scrape_category(session, robots, name, categories[name])
        all_books.extend(books)
        print(f"[{number}/{len(names)}] {name}: {len(books)} books "
              f"(total so far: {len(all_books)})")
    return pd.DataFrame(all_books)


# --------------------------- Cleaning functions ---------------------------
def clean_data(raw_df):
    """Remove duplicates, convert price and rating to numbers, tidy columns."""
    df = raw_df.copy()
    print(f"\nRows before cleaning: {len(df)}")

    # 1. Remove duplicates (every book has a unique product URL)
    duplicates = df.duplicated(subset="product_url").sum()
    df = df.drop_duplicates(subset="product_url").reset_index(drop=True)
    print(f"Duplicates removed: {duplicates}")

    # 2. Price: "£51.77" -> 51.77
    df["price_gbp"] = df["price_text"].str.replace(r"[^\d.]", "", regex=True).astype(float)

    # 3. Rating: "Three" -> 3
    df["rating"] = df["rating_word"].map(RATING_WORDS)

    # 4. Tidy text and create a True/False stock column
    df["title"] = df["title"].str.strip()
    df["category"] = df["category"].str.strip()
    df["in_stock"] = df["availability"].str.contains("In stock", case=False)

    # 5. Keep useful columns in a sensible order
    df = df[["title", "category", "price_gbp", "rating",
             "availability", "in_stock", "product_url"]]
    print(f"Rows after cleaning: {len(df)}")
    return df


def verify_dataset(df):
    """Print basic checks so you can confirm the dataset is sound."""
    print("\n----- Dataset verification -----")
    print("Shape (rows, columns):", df.shape)
    print("Number of categories:", df["category"].nunique())
    print("\nMissing values per column:")
    print(df.isnull().sum())
    checks = {
        "No duplicate product URLs": df["product_url"].duplicated().sum() == 0,
        "No missing values": df.isnull().sum().sum() == 0,
        "All prices are positive": (df["price_gbp"] > 0).all(),
        "All ratings are between 1 and 5": df["rating"].between(1, 5).all(),
    }
    print("\nAutomatic checks:")
    for name, passed in checks.items():
        print("PASS" if passed else "CHECK", "-", name)


# ------------------------------- Main program -------------------------------
def main():
    test_mode = "--test" in sys.argv
    os.makedirs(DATA_FOLDER, exist_ok=True)

    if test_mode:
        print("TEST MODE: scraping only 2 categories\n")

    session = create_session()
    robots = load_robots_rules(session)
    raw_df = scrape_all(session, robots, max_categories=2 if test_mode else None)

    if raw_df.empty:
        print("\nNo data was collected. Check your internet connection and the messages above.")
        sys.exit(1)

    suffix = "_test" if test_mode else ""
    raw_path = os.path.join(DATA_FOLDER, f"books_raw{suffix}.csv")
    clean_path = os.path.join(DATA_FOLDER, f"books_clean{suffix}.csv")

    # utf-8-sig keeps the £ symbol readable if you open the CSV in Excel
    raw_df.to_csv(raw_path, index=False, encoding="utf-8-sig")
    print(f"\nSaved raw data to {raw_path}")

    clean_df = clean_data(raw_df)
    clean_df.to_csv(clean_path, index=False, encoding="utf-8-sig")
    print(f"Saved clean data to {clean_path}")

    verify_dataset(clean_df)
    print("\nFirst 5 rows:")
    print(clean_df.head().to_string())


if __name__ == "__main__":
    main()
