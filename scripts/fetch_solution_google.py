#!/usr/bin/env python3
"""
Codeforces Solution Fetcher via Google Search

Searches Google for Codeforces problem solutions from unofficial sources
(blogs, GeeksforGeeks, Medium, etc.) and extracts the content.

No authentication required!

Usage:
    python fetch_solution_google.py 2191 A
    python fetch_solution_google.py 1234 B "Problem Name"
    python fetch_solution_google.py --contest 2191 --problem A
"""

import argparse
import sys
from typing import List, Tuple, Optional
from bs4 import BeautifulSoup
import requests
from urllib.parse import quote_plus, urlparse
import time


class GoogleSolutionFetcher:
    """Fetches Codeforces solutions by searching Google."""
    
    USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0'
    
    # Trusted solution sites (in order of preference)
    TRUSTED_DOMAINS = [
        'geeksforgeeks.org',
        'medium.com',
        'dev.to',
        'hackernoon.com',
        'codeforces.com',  # Sometimes editorials work without auth
        'cp-algorithms.com',
        'usaco.guide',
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.USER_AGENT})
    
    def search_duckduckgo(self, query: str, num_results: int = 10) -> List[Tuple[str, str]]:
        """
        Search DuckDuckGo and return URLs and titles.
        
        Args:
            query: Search query
            num_results: Number of results to return
            
        Returns:
            List of (url, title) tuples
        """
        # Use DuckDuckGo HTML search (more lenient than Google)
        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        
        try:
            response = self.session.get(search_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            results = []
            # Find search result links in DDG
            for result in soup.find_all('a', class_='result__a'):
                url = result.get('href', '')
                title = result.get_text(strip=True)
                
                # DuckDuckGo uses redirect links, try to get the actual URL
                if url.startswith('/'):
                    continue
                    
                # Filter useful results
                if url and title and 'duckduckgo.com' not in url:
                    results.append((url, title))
                    
                    if len(results) >= num_results:
                        break
            
            return results
            
        except Exception as e:
            print(f"Warning: DuckDuckGo search failed: {e}", file=sys.stderr)
            return []
    
    def extract_content(self, url: str) -> Tuple[bool, str]:
        """
        Extract article/blog content from a URL.
        
        Args:
            url: URL to fetch
            
        Returns:
            Tuple of (success, content)
        """
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Try common content selectors
            content_selectors = [
                ('article', {}),
                ('div', {'class': 'post-content'}),
                ('div', {'class': 'article-content'}),
                ('div', {'class': 'entry-content'}),
                ('div', {'class': 'content'}),
                ('div', {'id': 'content'}),
                ('main', {}),
                ('div', {'role': 'main'}),
            ]
            
            content_div = None
            for tag, attrs in content_selectors:
                content_div = soup.find(tag, attrs)
                if content_div:
                    break
            
            if not content_div:
                # Fallback: get body text
                content_div = soup.find('body')
            
            if content_div:
                # Extract text
                text = content_div.get_text(separator='\n', strip=True)
                
                # Clean up excessive whitespace
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                text = '\n'.join(lines)
                
                return True, text
            else:
                return False, "Could not extract content from page"
                
        except Exception as e:
            return False, f"Error fetching URL: {str(e)}"
    
    def find_solution(
        self, 
        contest_id: int, 
        problem_letter: str, 
        problem_name: Optional[str] = None,
        max_attempts: int = 5
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Find solution for a Codeforces problem.
        
        Args:
            contest_id: Contest ID
            problem_letter: Problem letter (A, B, C, etc.)
            problem_name: Optional problem name for better search
            max_attempts: Maximum number of URLs to try
            
        Returns:
            Tuple of (success, content, source_url)
        """
        # Build search query
        query_parts = [
            f"codeforces {contest_id}{problem_letter}",
            "solution" if not problem_name else f"{problem_name} solution",
            "editorial OR explanation OR tutorial"
        ]
        query = ' '.join(query_parts)
        
        print(f"Searching for: {query}", file=sys.stderr)
        
        # Search DuckDuckGo
        results = self.search_duckduckgo(query, num_results=10)
        
        if not results:
            return False, "No search results found", None
        
        print(f"Found {len(results)} results", file=sys.stderr)
        
        # Try each result, prioritizing trusted domains
        def get_priority(url):
            domain = urlparse(url).netloc.lower()
            for i, trusted in enumerate(self.TRUSTED_DOMAINS):
                if trusted in domain:
                    return i
            return len(self.TRUSTED_DOMAINS)
        
        # Sort by priority
        results.sort(key=lambda x: get_priority(x[0]))
        
        # Try to fetch content from each result
        for i, (url, title) in enumerate(results[:max_attempts]):
            print(f"Trying [{i+1}/{max_attempts}]: {title[:60]}...", file=sys.stderr)
            print(f"  URL: {url}", file=sys.stderr)
            
            success, content = self.extract_content(url)
            
            if success and len(content) > 200:  # Minimum content length
                print(f"✓ Successfully extracted {len(content)} characters", file=sys.stderr)
                return True, content, url
            else:
                print(f"✗ Failed or insufficient content", file=sys.stderr)
            
            # Be nice to servers
            time.sleep(0.5)
        
        return False, "Could not extract solution from any source", None


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description='Fetch Codeforces solutions via Google search',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 2191 A
  %(prog)s 1234 B "Problem Name"
  %(prog)s --contest 2191 --problem A
  %(prog)s --contest 1234 --problem B --name "Two Arrays"
  
This tool searches Google for unofficial editorials and solutions,
then extracts the content. No authentication required!
        """
    )
    
    parser.add_argument('contest_id', nargs='?', type=int, help='Contest ID (e.g., 2191)')
    parser.add_argument('problem_letter', nargs='?', help='Problem letter (e.g., A)')
    parser.add_argument('problem_name', nargs='?', help='Optional problem name for better search')
    parser.add_argument('--contest', '-c', type=int, help='Contest ID')
    parser.add_argument('--problem', '-p', help='Problem letter')
    parser.add_argument('--name', '-n', help='Problem name')
    parser.add_argument('--output', '-o', help='Output file (default: stdout)')
    parser.add_argument('--max-results', '-m', type=int, default=5, help='Max URLs to try (default: 5)')
    
    args = parser.parse_args()
    
    # Determine parameters
    contest_id = args.contest or args.contest_id
    problem_letter = (args.problem or args.problem_letter or '').upper()
    problem_name = args.name or args.problem_name
    
    if not contest_id or not problem_letter:
        parser.error("Contest ID and problem letter are required")
    
    # Create fetcher and search
    fetcher = GoogleSolutionFetcher()
    success, content, source_url = fetcher.find_solution(
        contest_id, 
        problem_letter, 
        problem_name,
        max_attempts=args.max_results
    )
    
    # Output results
    if success:
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(f"Source: {source_url}\n")
                f.write("=" * 80 + "\n\n")
                f.write(content)
            print(f"\nSolution saved to: {args.output}")
        else:
            print(f"\nSource: {source_url}")
            print("=" * 80)
            print(content)
        
        return 0
    else:
        print(f"\nError: {content}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
