"""Web search integration for CRAG.

Supports multiple search providers:
    - tavily: Tavily AI search API
    - serpapi: SerpAPI Google search
    - brave: Brave Search API

Provider selection via config. All results are receipted.
"""
import time
from dataclasses import dataclass
from typing import List, Optional

from core.receipt import emit_receipt, dual_hash


@dataclass
class WebResult:
    """A single web search result."""
    url: str
    title: str
    snippet: str
    content: str = ""
    content_hash: str = ""
    relevance_score: float = 0.0
    source_provider: str = ""


@dataclass
class WebSearchResult:
    """Complete web search response."""
    query: str
    results: List[WebResult]
    provider: str
    elapsed_ms: float
    total_results: int = 0


def search(
    query: str,
    max_results: int = 5,
    timeout_ms: int = 2000,
    provider: str = "tavily",
    tenant_id: str = "default",
) -> List[WebResult]:
    """Search the web using configured provider.

    Args:
        query: Search query
        max_results: Maximum results to return
        timeout_ms: Timeout in milliseconds
        provider: Search provider ("tavily", "serpapi", "brave")
        tenant_id: Tenant identifier

    Returns:
        List of WebResult objects
    """
    start_time = time.perf_counter()

    # Check if provider is available
    if provider == "tavily":
        results = _search_tavily(query, max_results, timeout_ms)
    elif provider == "serpapi":
        results = _search_serpapi(query, max_results, timeout_ms)
    elif provider == "brave":
        results = _search_brave(query, max_results, timeout_ms)
    else:
        # Fallback to mock results for testing
        results = _search_mock(query, max_results)

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    # Add content hashes
    for result in results:
        if result.content or result.snippet:
            content = result.content or result.snippet
            result.content_hash = dual_hash(content)
        result.source_provider = provider

    # Emit web retrieval receipt
    emit_receipt("web_retrieval", {
        "query": query,
        "provider": provider,
        "results_count": len(results),
        "sources": [r.url for r in results],
        "content_hashes": [r.content_hash for r in results],
        "latency_ms": elapsed_ms,
        "tenant_id": tenant_id,
    })

    return results


def _search_tavily(
    query: str,
    max_results: int,
    timeout_ms: int,
) -> List[WebResult]:
    """Search using Tavily AI search API.

    Requires TAVILY_API_KEY environment variable.
    """
    try:
        import os
        from tavily import TavilyClient

        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            return _search_mock(query, max_results)

        client = TavilyClient(api_key=api_key)

        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
        )

        results = []
        for item in response.get("results", []):
            results.append(WebResult(
                url=item.get("url", ""),
                title=item.get("title", ""),
                snippet=item.get("content", ""),
                content=item.get("raw_content", ""),
                relevance_score=item.get("score", 0.0),
            ))

        return results

    except ImportError:
        return _search_mock(query, max_results)
    except Exception:
        return _search_mock(query, max_results)


def _search_serpapi(
    query: str,
    max_results: int,
    timeout_ms: int,
) -> List[WebResult]:
    """Search using SerpAPI Google search.

    Requires SERPAPI_API_KEY environment variable.
    """
    try:
        import os
        from serpapi import GoogleSearch

        api_key = os.environ.get("SERPAPI_API_KEY")
        if not api_key:
            return _search_mock(query, max_results)

        search = GoogleSearch({
            "q": query,
            "num": max_results,
            "api_key": api_key,
        })

        response = search.get_dict()

        results = []
        for item in response.get("organic_results", []):
            results.append(WebResult(
                url=item.get("link", ""),
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                relevance_score=item.get("position", 10) / 10.0,
            ))

        return results[:max_results]

    except ImportError:
        return _search_mock(query, max_results)
    except Exception:
        return _search_mock(query, max_results)


def _search_brave(
    query: str,
    max_results: int,
    timeout_ms: int,
) -> List[WebResult]:
    """Search using Brave Search API.

    Requires BRAVE_API_KEY environment variable.
    """
    try:
        import os
        import requests

        api_key = os.environ.get("BRAVE_API_KEY")
        if not api_key:
            return _search_mock(query, max_results)

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
        }

        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": max_results},
            headers=headers,
            timeout=timeout_ms / 1000,
        )

        data = response.json()

        results = []
        for item in data.get("web", {}).get("results", []):
            results.append(WebResult(
                url=item.get("url", ""),
                title=item.get("title", ""),
                snippet=item.get("description", ""),
                relevance_score=1.0 - (len(results) / max_results),
            ))

        return results[:max_results]

    except ImportError:
        return _search_mock(query, max_results)
    except Exception:
        return _search_mock(query, max_results)


def _search_mock(query: str, max_results: int) -> List[WebResult]:
    """Mock search for testing when no provider is configured.

    Returns placeholder results.
    """
    results = []

    for i in range(min(max_results, 3)):
        results.append(WebResult(
            url=f"https://example.com/result-{i+1}",
            title=f"Mock Result {i+1} for: {query[:30]}",
            snippet=f"This is a mock search result for the query '{query}'. "
                   f"In production, configure a real web search provider.",
            content="",
            relevance_score=1.0 - (i * 0.2),
        ))

    return results


def fetch_content(
    url: str,
    timeout_ms: int = 5000,
    tenant_id: str = "default",
) -> Optional[str]:
    """Fetch full content from a URL.

    Args:
        url: URL to fetch
        timeout_ms: Timeout in milliseconds
        tenant_id: Tenant identifier

    Returns:
        Page content as text, or None on error
    """
    try:
        import requests

        response = requests.get(
            url,
            timeout=timeout_ms / 1000,
            headers={"User-Agent": "ProofPack/1.0"},
        )

        if response.status_code == 200:
            content = response.text

            emit_receipt("web_fetch", {
                "url": url,
                "status": response.status_code,
                "content_length": len(content),
                "content_hash": dual_hash(content),
                "tenant_id": tenant_id,
            })

            return content

        return None

    except Exception:
        return None


def get_available_providers() -> List[str]:
    """Get list of available web search providers.

    Checks for required environment variables.

    Returns:
        List of available provider names
    """
    import os

    available = []

    if os.environ.get("TAVILY_API_KEY"):
        available.append("tavily")

    if os.environ.get("SERPAPI_API_KEY"):
        available.append("serpapi")

    if os.environ.get("BRAVE_API_KEY"):
        available.append("brave")

    # Mock is always available for testing
    available.append("mock")

    return available
