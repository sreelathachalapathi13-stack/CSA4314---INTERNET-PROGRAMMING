import os
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9"
}

def clean_price(price_str):
    if not price_str:
        return None
    cleaned = re.sub(r"[^0-9.]", "", str(price_str))
    try:
        val = float(cleaned)
        return val if val > 0 else None
    except ValueError:
        return None

def fetch_via_serpapi(query):
    api_key = os.getenv("SERPAPI_KEY", "").strip()
    if not api_key or api_key == "your_serpapi_key_here":
        return None

    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_shopping",
        "q": query,
        "gl": "in",
        "hl": "en",
        "api_key": api_key
    }
    try:
        res = requests.get(url, params=params, timeout=10).json()
        results = res.get("shopping_results", [])
        amazon_item = None
        flipkart_item = None

        for item in results:
            source = item.get("source", "").lower()
            price = clean_price(item.get("extracted_price") or item.get("price"))
            link = item.get("link")
            title = item.get("title")
            image = item.get("thumbnail")

            if "amazon" in source and not amazon_item and price:
                amazon_item = {
                    "platform": "Amazon",
                    "title": title,
                    "price": price,
                    "url": link,
                    "image": image
                }
            elif "flipkart" in source and not flipkart_item and price:
                flipkart_item = {
                    "platform": "Flipkart",
                    "title": title,
                    "price": price,
                    "url": link,
                    "image": image
                }
            if amazon_item and flipkart_item:
                break

        if amazon_item or flipkart_item:
            return {"amazon": amazon_item, "flipkart": flipkart_item}
    except Exception as e:
        print(f"[SerpApi Error]: {e}")
    return None

def scrape_amazon_direct(query):
    encoded = urllib.parse.quote_plus(query)
    search_url = f"https://www.amazon.in/s?k={encoded}"
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=8)
        soup = BeautifulSoup(resp.text, "html.parser")
        card = soup.select_one("div[data-component-type='s-search-result']")
        if card:
            title_el = card.select_one("h2 a span")
            link_el = card.select_one("h2 a")
            price_el = card.select_one("span.a-price span.a-offscreen")
            img_el = card.select_one("img.s-image")

            price = clean_price(price_el.text if price_el else None)
            href = link_el["href"] if link_el and link_el.has_attr("href") else ""
            full_url = f"https://www.amazon.in{href}" if href.startswith("/") else search_url

            if price:
                return {
                    "platform": "Amazon",
                    "title": title_el.text.strip() if title_el else query,
                    "price": price,
                    "url": full_url,
                    "image": img_el["src"] if img_el else ""
                }
    except Exception as e:
        print(f"[Amazon Scrape Error]: {e}")
    return None

def scrape_flipkart_direct(query):
    encoded = urllib.parse.quote_plus(query)
    search_url = f"https://www.flipkart.com/search?q={encoded}"
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=8)
        soup = BeautifulSoup(resp.text, "html.parser")
        # Flipkart uses dynamic classes; match common product anchor & INR symbol blocks
        for a in soup.find_all("a", href=True):
            if "/p/" in a["href"]:
                text_block = a.get_text(" ", strip=True)
                price_match = re.search(r"₹([0-9,]+)", text_block)
                if price_match:
                    price = clean_price(price_match.group(1))
                    full_url = f"https://www.flipkart.com{a['href']}" if a["href"].startswith("/") else a["href"]
                    img_el = a.find("img")
                    title = img_el["alt"] if img_el and img_el.has_attr("alt") else query
                    return {
                        "platform": "Flipkart",
                        "title": title,
                        "price": price,
                        "url": full_url,
                        "image": img_el["src"] if img_el and img_el.has_attr("src") else ""
                    }
    except Exception as e:
        print(f"[Flipkart Scrape Error]: {e}")
    return None

def get_live_prices(query):
    # 1. Try SerpApi first (bypasses anti-bot blocks)
    api_data = fetch_via_serpapi(query)
    if api_data:
        amazon = api_data.get("amazon")
        flipkart = api_data.get("flipkart")
    else:
        # 2. Fallback to direct live HTTP scraping
        amazon = scrape_amazon_direct(query)
        flipkart = scrape_flipkart_direct(query)

    # Ensure direct search links exist even if anti-bot blocks a single store
    encoded = urllib.parse.quote_plus(query)
    if not amazon:
        amazon = {
            "platform": "Amazon",
            "title": f"{query} (View on Amazon.in)",
            "price": None,
            "url": f"https://www.amazon.in/s?k={encoded}",
            "image": ""
        }
    if not flipkart:
        flipkart = {
            "platform": "Flipkart",
            "title": f"{query} (View on Flipkart.com)",
            "price": None,
            "url": f"https://www.flipkart.com/search?q={encoded}",
            "image": ""
        }

    # Determine lowest price recommendation
    a_price = amazon["price"]
    f_price = flipkart["price"]
    recommendation = None

    if a_price is not None and f_price is not None:
        if a_price < f_price:
            recommendation = {
                "best_platform": "Amazon",
                "lowest_price": a_price,
                "savings": round(f_price - a_price, 2),
                "buy_url": amazon["url"]
            }
        elif f_price < a_price:
            recommendation = {
                "best_platform": "Flipkart",
                "lowest_price": f_price,
                "savings": round(a_price - f_price, 2),
                "buy_url": flipkart["url"]
            }
        else:
            recommendation = {
                "best_platform": "Both (Same Price)",
                "lowest_price": a_price,
                "savings": 0,
                "buy_url": amazon["url"]
            }
    elif a_price is not None:
        recommendation = {
            "best_platform": "Amazon",
            "lowest_price": a_price,
            "savings": 0,
            "buy_url": amazon["url"]
        }
    elif f_price is not None:
        recommendation = {
            "best_platform": "Flipkart",
            "lowest_price": f_price,
            "savings": 0,
            "buy_url": flipkart["url"]
        }

    return {
        "query": query,
        "amazon": amazon,
        "flipkart": flipkart,
        "recommendation": recommendation
    }
