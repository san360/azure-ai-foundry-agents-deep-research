"""Citation processing utilities for research content."""

import re
import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse

from azure_ai_research.security.validation import sanitize_html_output

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Citation:
    """Immutable citation data structure."""
    
    title: str
    url: str
    snippet: str
    index: int
    
    def __post_init__(self) -> None:
        """Validate citation data."""
        if not self.title or not isinstance(self.title, str):
            raise ValueError("Citation title must be a non-empty string")
        
        if not self.url or not isinstance(self.url, str):
            raise ValueError("Citation URL must be a non-empty string")
        
        # Basic URL validation
        try:
            parsed = urlparse(self.url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
        except Exception as e:
            raise ValueError(f"Invalid URL: {e}")
        
        if self.index < 0:
            raise ValueError("Citation index must be non-negative")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert citation to dictionary."""
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "index": self.index
        }


class CitationProcessor:
    """Processor for extracting and formatting citations in research content."""
    
    def __init__(self, max_citations: int = 50) -> None:
        """Initialize citation processor with limits."""
        self.max_citations = max_citations
        
        # Regex patterns for citation detection
        self.citation_patterns = [
            # Standard citation formats
            r'\[(\d+)\]\s*([^\[\]]+?)(?:\s+)?(https?://[^\s\]]+)',
            r'\[(\d+)\]:\s*([^\[\]]+?)(?:\s+)?(https?://[^\s\]]+)',
            r'(\d+)\.\s*([^\[\]]+?)(?:\s+)?(https?://[^\s\]]+)',
            # URL with title
            r'"([^"]+)"\s*-?\s*(https?://[^\s\]]+)',
            r'([^:\[\]]+):\s*(https?://[^\s\]]+)',
        ]
        
        logger.debug("CitationProcessor initialized")
    
    def extract_citations(self, content: str) -> List[Dict[str, Any]]:
        """Extract citations from research content."""
        try:
            if not content or not isinstance(content, str):
                logger.warning("Invalid content provided for citation extraction")
                return []
            
            # Sanitize content first
            sanitized_content = sanitize_html_output(content)
            
            citations = []
            citation_index = 1
            
            # Try each citation pattern
            for pattern in self.citation_patterns:
                matches = re.finditer(pattern, sanitized_content, re.IGNORECASE | re.MULTILINE)
                
                for match in matches:
                    if len(citations) >= self.max_citations:
                        logger.warning(f"Maximum citations limit ({self.max_citations}) reached")
                        break
                    
                    try:
                        citation = self._create_citation_from_match(match, citation_index)
                        if citation and not self._is_duplicate_citation(citation, citations):
                            citations.append(citation.to_dict())
                            citation_index += 1
                    except Exception as e:
                        logger.warning(f"Failed to create citation from match: {e}")
                        continue
                
                if len(citations) >= self.max_citations:
                    break
            
            logger.info(f"Extracted {len(citations)} citations from content")
            return citations
            
        except Exception as e:
            logger.error(f"Citation extraction failed: {e}")
            return []
    
    def _create_citation_from_match(self, match: re.Match, index: int) -> Citation:
        """Create citation object from regex match."""
        groups = match.groups()
        
        if len(groups) >= 3:
            # Pattern with index, title, and URL
            title = groups[1].strip()
            url = groups[2].strip()
        elif len(groups) == 2:
            # Pattern with title and URL
            title = groups[0].strip()
            url = groups[1].strip()
        else:
            raise ValueError("Insufficient groups in citation match")
        
        # Clean up title
        title = self._clean_citation_title(title)
        
        # Validate URL
        if not self._is_valid_url(url):
            raise ValueError(f"Invalid URL in citation: {url}")
        
        # Extract snippet from surrounding context
        snippet = self._extract_snippet(match.string, match.start(), match.end())
        
        return Citation(
            title=title,
            url=url,
            snippet=snippet,
            index=index
        )
    
    def _clean_citation_title(self, title: str) -> str:
        """Clean and validate citation title."""
        if not title:
            return "Untitled"
        
        # Remove extra whitespace and special characters
        cleaned = re.sub(r'\s+', ' ', title.strip())
        cleaned = re.sub(r'[^\w\s\-\.\,\:\;]', '', cleaned)
        
        # Truncate if too long
        if len(cleaned) > 200:
            cleaned = cleaned[:197] + "..."
        
        return cleaned or "Untitled"
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format and scheme."""
        try:
            parsed = urlparse(url)
            return parsed.scheme in ['http', 'https'] and parsed.netloc
        except Exception:
            return False
    
    def _extract_snippet(self, content: str, start: int, end: int, context_length: int = 100) -> str:
        """Extract snippet with context around citation."""
        try:
            # Calculate context boundaries
            snippet_start = max(0, start - context_length)
            snippet_end = min(len(content), end + context_length)
            
            snippet = content[snippet_start:snippet_end]
            
            # Clean up snippet
            snippet = re.sub(r'\s+', ' ', snippet).strip()
            
            # Add ellipsis if truncated
            if snippet_start > 0:
                snippet = "..." + snippet
            if snippet_end < len(content):
                snippet = snippet + "..."
            
            return snippet[:300]  # Limit snippet length
            
        except Exception as e:
            logger.warning(f"Failed to extract snippet: {e}")
            return ""
    
    def _is_duplicate_citation(self, citation: Citation, existing_citations: List[Dict[str, Any]]) -> bool:
        """Check if citation is a duplicate."""
        for existing in existing_citations:
            if (citation.url == existing.get("url") or 
                citation.title.lower() == existing.get("title", "").lower()):
                return True
        return False
    
    def convert_to_superscript(self, content: str) -> str:
        """Convert citation numbers to superscript format."""
        try:
            if not content or not isinstance(content, str):
                return content
            
            # Convert [1], [2], etc. to superscript
            content = re.sub(r'\[(\d+)\]', r'<sup>[\1]</sup>', content)
            
            # Convert standalone numbers at end of sentences to superscript
            content = re.sub(r'(\w)\s*(\d+)(?=\s*[\.!?])', r'\1<sup>\2</sup>', content)
            
            logger.debug("Citation numbers converted to superscript format")
            return content
            
        except Exception as e:
            logger.error(f"Failed to convert citations to superscript: {e}")
            return content
    
    def format_citation_list(self, citations: List[Dict[str, Any]]) -> str:
        """Format citations as a numbered list."""
        try:
            if not citations:
                return ""
            
            formatted_citations = []
            for citation in citations:
                index = citation.get("index", 0)
                title = citation.get("title", "Untitled")
                url = citation.get("url", "")
                
                formatted = f"{index}. {title}"
                if url:
                    formatted += f" - {url}"
                
                formatted_citations.append(formatted)
            
            return "\n".join(formatted_citations)
            
        except Exception as e:
            logger.error(f"Failed to format citation list: {e}")
            return ""
    
    def validate_citations(self, citations: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Validate citations and return valid ones with error messages."""
        valid_citations = []
        errors = []
        
        for i, citation_data in enumerate(citations):
            try:
                # Validate required fields
                if not isinstance(citation_data, dict):
                    errors.append(f"Citation {i}: Invalid data type")
                    continue
                
                title = citation_data.get("title", "")
                url = citation_data.get("url", "")
                index = citation_data.get("index", 0)
                snippet = citation_data.get("snippet", "")
                
                # Create citation object for validation
                citation = Citation(
                    title=title,
                    url=url,
                    snippet=snippet,
                    index=index
                )
                
                valid_citations.append(citation.to_dict())
                
            except Exception as e:
                errors.append(f"Citation {i}: {str(e)}")
        
        logger.info(f"Validated {len(valid_citations)} out of {len(citations)} citations")
        if errors:
            logger.warning(f"Citation validation errors: {errors}")
        
        return valid_citations, errors
    
    def get_citation_statistics(self, citations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get statistics about citations."""
        try:
            if not citations:
                return {"total": 0, "domains": {}, "avg_title_length": 0}
            
            domain_counts = {}
            title_lengths = []
            
            for citation in citations:
                url = citation.get("url", "")
                title = citation.get("title", "")
                
                # Count domains
                try:
                    domain = urlparse(url).netloc
                    domain_counts[domain] = domain_counts.get(domain, 0) + 1
                except Exception:
                    pass
                
                # Track title lengths
                if title:
                    title_lengths.append(len(title))
            
            avg_title_length = sum(title_lengths) / len(title_lengths) if title_lengths else 0
            
            return {
                "total": len(citations),
                "domains": domain_counts,
                "avg_title_length": round(avg_title_length, 1),
                "unique_domains": len(domain_counts)
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate citation statistics: {e}")
            return {"total": 0, "error": str(e)}


def create_citation_processor(max_citations: int = 50) -> CitationProcessor:
    """Factory function to create citation processor."""
    return CitationProcessor(max_citations)