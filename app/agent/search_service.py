import os
from typing import List, Optional, Any

from langchain_exa import ExaSearchRetriever
from app.agent.models import ExaResult, ExaSearchResponse


class SearchService:
    _exa_retriever: Optional[ExaSearchRetriever] = None

    @classmethod
    def _get_exa_retriever(cls) -> ExaSearchRetriever:
        if cls._exa_retriever is None:
            exa_api_key = os.getenv("EXA_API_KEY")
            if not exa_api_key:
                raise ValueError("EXA_API_KEY environment variable not set")
            cls._exa_retriever = ExaSearchRetriever(
                api_key=exa_api_key,
                k=3,
                type="auto",
                highlights=True,
                text_contents_options={"max_characters": 2000},
            )
        return cls._exa_retriever

    @classmethod
    def search_web(cls, query: str, num_results: int = 5) -> ExaSearchResponse:
        """
        Search the web using Exa Retriever and return structured results.

        Args:
            query: The search query (should be a proper search query, not a statement)
            num_results: Number of results to return

        Returns:
            ExaSearchResponse with search results
        """
        try:
            retriever = cls._get_exa_retriever()
            results = retriever.invoke(query)

            exa_results = []
            if results:
                if isinstance(results, list):
                    for item in results:
                        exa_results.append(cls._parse_result(item))
                else:
                    exa_results.append(cls._parse_result(results))

            return ExaSearchResponse(
                results=exa_results,
                query_used=query,
            )
        except Exception as e:
            return ExaSearchResponse(
                results=[],
                query_used=query,
            )

    @classmethod
    def _parse_result(cls, item: Any) -> ExaResult:
        """Parse a single result into ExaResult format."""
        if isinstance(item, dict):
            title = item.get("title", "")
            url = item.get("url", "")
            snippet = item.get("snippet", "") or item.get("highlight", "")
            score = item.get("score", 0.0)
        elif hasattr(item, "title"):
            title = getattr(item, "title", "")
            url = getattr(item, "url", "")
            snippet = getattr(item, "snippet", "") or getattr(item, "highlight", "")
            score = getattr(item, "score", 0.0)
        else:
            title = str(item)
            url = ""
            snippet = ""
            score = 0.0

        return ExaResult(
            title=title,
            url=url,
            snippet=snippet[:500] if snippet else "",
            score=score,
        )

    @classmethod
    def search_multiple(
        cls, queries: List[str], num_results: int = 3
    ) -> List[ExaSearchResponse]:
        """
        Search multiple queries and return combined results.

        Args:
            queries: List of search queries
            num_results: Number of results per query

        Returns:
            List of ExaSearchResponse for each query
        """
        results = []
        for query in queries:
            result = cls.search_web(query, num_results)
            results.append(result)
        return results
