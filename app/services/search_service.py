from abc import ABC, abstractmethod
import os
import logging
from typing import List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)

from langchain_community.utilities import DuckDuckGoSearchAPIWrapper

from app.agent.models import SearchResult, SearchResponse
from langchain_community.tools import DuckDuckGoSearchResults


class SearchProviderType(Enum):
    EXA = "exa"
    DUCKDUCKGO = "duckduckgo"


class SearchProvider(ABC):
    """Abstract base class for search providers."""

    @abstractmethod
    def search_web(self, query: str, num_results: int = 1) -> SearchResponse:
        """Search the web and return structured results."""
        pass

    @abstractmethod
    def search_multiple(self, queries: List[str], num_results: int = 1) -> List[SearchResponse]:
        """Search multiple queries and return combined results."""
        pass

    @staticmethod
    def _parse_search_result(item: Any) -> SearchResult:
        """Normalize provider-specific result objects into SearchResult."""
        if isinstance(item, SearchResult):
            return item

        if isinstance(item, dict):
            title = item.get("title", "") or ""
            url = item.get("url", "") or item.get("link", "") or ""
            snippet = (
                item.get("snippet", "")
                or item.get("highlight", "")
                or item.get("description", "")
                or item.get("text", "")
                or ""
            )
            score = item.get("score", 0.0) or 0.0
            return SearchResult(
                title=title,
                url=url,
                snippet=str(snippet)[:500],
                score=float(score),
            )

        if hasattr(item, "metadata") or hasattr(item, "page_content"):
            metadata = getattr(item, "metadata", {}) or {}
            page_content = getattr(item, "page_content", "") or ""
            title = metadata.get("title", "") or getattr(item, "title", "") or ""
            url = metadata.get("url", "") or metadata.get("link", "") or getattr(item, "url", "") or ""
            snippet = (
                metadata.get("snippet", "")
                or metadata.get("highlight", "")
                or metadata.get("summary", "")
                or page_content
                or ""
            )
            score = metadata.get("score", 0.0) or getattr(item, "score", 0.0) or 0.0
            return SearchResult(
                title=title or url or str(item),
                url=url,
                snippet=str(snippet)[:500],
                score=float(score),
            )

        if hasattr(item, "title"):
            title = getattr(item, "title", "") or ""
            url = getattr(item, "url", "") or getattr(item, "link", "") or ""
            snippet = (
                getattr(item, "snippet", "")
                or getattr(item, "highlight", "")
                or getattr(item, "description", "")
                or ""
            )
            score = getattr(item, "score", 0.0) or 0.0
            return SearchResult(
                title=title or url or str(item),
                url=url,
                snippet=str(snippet)[:500],
                score=float(score),
            )

        return SearchResult(
            title=str(item),
            url="",
            snippet="",
            score=0.0,
        )

    @classmethod
    def _normalize_results(cls, results: Any) -> List[SearchResult]:
        if not results:
            return []
        if isinstance(results, list):
            return [cls._parse_search_result(item) for item in results]
        return [cls._parse_search_result(results)]


class ExaSearchProvider(SearchProvider):
    """Exa search implementation."""

    _exa_retriever = None
    _exa_k: int = 1

    def _get_exa_retriever(self, k: int = 1):
        if self._exa_retriever is None or self._exa_k != k:
            from langchain_exa import ExaSearchRetriever
            exa_api_key = os.getenv("EXA_API_KEY")
            if not exa_api_key:
                raise ValueError("EXA_API_KEY environment variable not set")
            try:
                self._exa_retriever = ExaSearchRetriever(
                    exa_api_key=exa_api_key,
                    k=k,
                    type="auto",
                    highlights=True,
                    text_contents_options={"max_characters": 2000},
                )
            except TypeError:
                # Older langchain_exa versions used api_key instead of exa_api_key.
                self._exa_retriever = ExaSearchRetriever(
                    api_key=exa_api_key,
                    k=k,
                    type="auto",
                    highlights=True,
                    text_contents_options={"max_characters": 2000},
                )
            self._exa_k = k
        return self._exa_retriever

    def search_web(self, query: str, num_results: int = 1) -> SearchResponse:
        logger.info(f"Using ExaSearchProvider to search for query: '{query}' with num_results={num_results}")
        try:
            retriever = self._get_exa_retriever(k=num_results)
            results = retriever.invoke(query)
            search_results = self._normalize_results(results)

            return SearchResponse(
                results=search_results,
                query_used=query,
            )
        except Exception as e:
            logger.exception("Exa search failed for query '%s'", query)
            return SearchResponse(
                results=[],
                query_used=query,
            )

    def search_multiple(self, queries: List[str], num_results: int = 1) -> List[SearchResponse]:
        return [self.search_web(q, num_results) for q in queries]


class DuckDuckGoSearchProvider(SearchProvider):
    """DuckDuckGo search implementation using ddgs library."""

    def search_web(self, query: str, num_results: int = 1) -> SearchResponse:
        logger.info(f"Using DuckDuckGoSearchProvider to search for query: '{query}' with num_results={num_results}")
        try:
            wrapper = DuckDuckGoSearchAPIWrapper(max_results=num_results)
            search = DuckDuckGoSearchResults(
                api_wrapper=wrapper,
                num_results=num_results,
                output_format="list",
            )
            search_results = search.invoke(query)

            logger.debug(f"DDG Search results for query '{query}': {search_results}")

            return SearchResponse(
                results=self._normalize_results(search_results),
                query_used=query,
            )
        except Exception as e:
            logger.exception("DuckDuckGo search failed for query '%s'", query)
            return SearchResponse(
                results=[],
                query_used=query,
            )

    def search_multiple(self, queries: List[str], num_results: int = 1) -> List[SearchResponse]:
        return [self.search_web(q, num_results) for q in queries]


class SearchService:
    """Router class that delegates to the appropriate search provider."""

    _provider: Optional[SearchProvider] = None
    _provider_type: Optional[SearchProviderType] = None

    @classmethod
    def _get_provider(cls) -> SearchProvider:
        provider_str = os.getenv("SEARCH_PROVIDER", "exa").lower()

        if cls._provider is None or cls._provider_type.value != provider_str:
            if provider_str == "duckduckgo":
                cls._provider_type = SearchProviderType.DUCKDUCKGO
                cls._provider = DuckDuckGoSearchProvider()
            else:
                cls._provider_type = SearchProviderType.EXA
                cls._provider = ExaSearchProvider()

        return cls._provider

    @classmethod
    def search_web(cls, query: str, num_results: int = 1) -> SearchResponse:
        """
        Search the web using the configured provider.

        Args:
            query: The search query
            num_results: Number of results to return (default 1)

        Returns:
            SearchResponse with search results
        """
        provider = cls._get_provider()
        return provider.search_web(query, num_results)

    @classmethod
    def search_multiple(cls, queries: List[str], num_results: int = 1) -> List[SearchResponse]:
        """
        Search multiple queries using the configured provider.

        Args:
            queries: List of search queries
            num_results: Number of results per query

        Returns:
            List of SearchResponse for each query
        """
        provider = cls._get_provider()
        return provider.search_multiple(queries, num_results)
