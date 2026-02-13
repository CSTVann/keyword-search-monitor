"""
Google Search Link Finder

Searches Google for a keyword and returns a list of website links.
Uses SerpAPI (recommended) or Google Custom Search JSON API.
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

RESULTS_PER_REQUEST = 10


def _search_serpapi(
    keyword: str,
    num_results: int,
    api_key: str,
) -> list[dict]:
    """Use SerpAPI to get Google search results (works for new users)."""
    results: list[dict] = []
    start = 0
    num = min(20, max(10, num_results))

    while len(results) < num_results:
        url = "https://serpapi.com/search"
        params = {
            "engine": "google",
            "q": keyword,
            "api_key": api_key,
            "num": num,
            "start": start,
        }
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code != 200:
            raise RuntimeError(f"SerpAPI error {resp.status_code}: {resp.text}")
        data = resp.json()
        for item in data.get("organic_results", []):
            link = item.get("link")
            if link and link not in (r["link"] for r in results):
                results.append({
                    "link": link,
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "display_link": item.get("displayed_link", ""),
                })
            if len(results) >= num_results:
                break
        if len(results) >= num_results:
            break
        start += num
        if start >= 100 or not data.get("serpapi_pagination", {}).get("next_link"):
            break
    return results[:num_results]


def _search_google_cse(
    keyword: str,
    num_results: int,
    api_key: str,
    search_engine_id: str,
    lang: str,
) -> list[dict]:
    """Use Google Custom Search JSON API (may 403 for new projects)."""
    results: list[dict] = []
    start_index = 1
    while len(results) < num_results:
        count = min(RESULTS_PER_REQUEST, num_results - len(results))
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": api_key,
            "cx": search_engine_id,
            "q": keyword,
            "num": count,
            "start": start_index,
        }
        if lang:
            params["lr"] = lang
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Google Custom Search API error {resp.status_code}: {resp.text}"
            )
        data = resp.json()
        total = data.get("searchInformation", {}).get("totalResults")
        if total is not None and int(total) == 0:
            break
        for item in data.get("items", []):
            link = item.get("link")
            if link and link not in (r["link"] for r in results):
                results.append({
                    "link": link,
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "display_link": item.get("displayLink", ""),
                })
            if len(results) >= num_results:
                break
        if len(results) >= num_results:
            break
        start_index += count
        if start_index > 100 or not data.get("queries", {}).get("nextPage"):
            break
    return results[:num_results]


def search_google(
    keyword: str,
    num_results: int = 10,
    api_key: str | None = None,
    search_engine_id: str | None = None,
    lang: str = "lang_en",
    *,
    use_serpapi: bool | None = None,
    serpapi_key: str | None = None,
) -> list[dict]:
    """
    Search Google for a keyword and return links (and metadata).

    By default uses SerpAPI if SERPAPI_KEY is set, otherwise Google Custom Search.
    SerpAPI works for new users; Google CSE often returns 403 for new projects.

    Args:
        keyword: Search term (e.g. "Monoreah").
        num_results: How many links to return (e.g. 10).
        api_key: Google API key (for Custom Search). Uses env GOOGLE_SEARCH_API_KEY if None.
        search_engine_id: Google Search Engine ID (cx). Uses env GOOGLE_SEARCH_ENGINE_ID if None.
        lang: Language filter for Google CSE (e.g. lang_en, lang_km).
        use_serpapi: If True, use SerpAPI; if False, use Google CSE; if None, auto (SerpAPI if key set).
        serpapi_key: SerpAPI key. Uses env SERPAPI_KEY if None.

    Returns:
        List of dicts with keys: link, title, snippet, display_link.
    """
    if num_results <= 0:
        return []

    serp_key = serpapi_key or os.environ.get("SERPAPI_KEY")
    google_key = api_key or os.environ.get("GOOGLE_SEARCH_API_KEY")
    cx = search_engine_id or os.environ.get("GOOGLE_SEARCH_ENGINE_ID")

    use_serp = use_serpapi
    if use_serp is None:
        use_serp = bool(serp_key)

    if use_serp:
        if not serp_key:
            raise ValueError(
                "SerpAPI requested but no key. Set SERPAPI_KEY in .env or pass serpapi_key=..."
            )
        return _search_serpapi(keyword, num_results, serp_key)

    if not google_key or not cx:
        raise ValueError(
            "Google Custom Search requested but credentials missing. "
            "Set GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID, or use SerpAPI by setting SERPAPI_KEY."
        )
    return _search_google_cse(keyword, num_results, google_key, cx, lang)


def get_links_only(
    keyword: str,
    num_results: int = 10,
    api_key: str | None = None,
    search_engine_id: str | None = None,
    serpapi_key: str | None = None,
    use_serpapi: bool | None = None,
) -> list[str]:
    """
    Same as search_google but returns only the URLs as a list of strings.
    Uses SerpAPI if SERPAPI_KEY is set (or serpapi_key passed); otherwise Google CSE.
    """
    rows = search_google(
        keyword=keyword,
        num_results=num_results,
        api_key=api_key,
        search_engine_id=search_engine_id,
        serpapi_key=serpapi_key,
        use_serpapi=use_serpapi,
    )
    return [r["link"] for r in rows]


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Search Google for a keyword and print website links."
    )
    parser.add_argument(
        "keyword",
        help='Search keyword (e.g. "Monoreah")',
    )
    parser.add_argument(
        "-n", "--num",
        type=int,
        default=10,
        help="Number of links to return (default: 10)",
    )
    parser.add_argument(
        "--links-only",
        action="store_true",
        help="Print only URLs, one per line",
    )
    args = parser.parse_args()

    try:
        results = search_google(keyword=args.keyword, num_results=args.num)
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=__import__("sys").stderr)
        raise SystemExit(1)

    if args.links_only:
        for r in results:
            print(r["link"])
    else:
        for i, r in enumerate(results, 1):
            print(f"{i}. {r['title']}")
            print(f"   {r['link']}")
            if r["snippet"]:
                print(f"   {r['snippet'][:150]}...")
            print()


if __name__ == "__main__":
    main()
