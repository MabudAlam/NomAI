from typing import List, Optional
from pydantic import BaseModel, Field


class SearchTerm(BaseModel):
    term: str = Field(description="A specific search term to look up")
    reason: str = Field(description="Why this term is important for nutrition analysis")


class EnrichedQuery(BaseModel):
    main_query: str = Field(description="The enriched main food query")
    search_terms: List[SearchTerm] = Field(
        description="List of 3 individual search terms to look up",
        min_length=3,
        max_length=3,
    )
    context: str = Field(description="Additional context for better analysis")


class SearchResult(BaseModel):
    title: str = Field(description="Title of the search result")
    url: str = Field(description="URL of the search result")
    snippet: str = Field(description="Snippet/highlight from the result")
    score: float = Field(description="Relevance score")


class SearchResponse(BaseModel):
    results: List[SearchResult] = Field(description="List of search results")
    query_used: str = Field(description="The original search query")


class AgentResponse(BaseModel):
    """Structured response from the agent LLM."""

    text: str = Field(description="The text response to show the user")
    needs_tools: bool = Field(
        description="Whether tools need to be called for this query"
    )
    tool_name: Optional[str] = Field(
        default=None, description="The tool to call if needs_tools is True"
    )
