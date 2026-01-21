#!/usr/bin/env python3
"""
Codeforces Editorial Fetcher

Fetches problem editorials from Codeforces using authenticated cookies.
Supports fetching editorials by contest ID and problem letter.

Usage:
    python fetch_codeforces_editorial.py 2191 A
    python fetch_codeforces_editorial.py --contest 2191 --problem A
    python fetch_codeforces_editorial.py --url https://codeforces.com/blog/entry/150256
"""

import argparse
import os
import re
import sys
from typing import Optional, Tuple
from bs4 import BeautifulSoup
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class CodeforcesEditorialFetcher:
    """Fetches Codeforces problem editorials with authentication."""
    
    BASE_URL = "https://codeforces.com"
    
    def __init__(self, cookies: Optional[str] = None):
        """
        Initialize the fetcher with Codeforces cookies.
        
        Args:
            cookies: Cookie string from Codeforces (optional, will use env var if not provided)
        """
        self.cookies = cookies or os.getenv("CODEFORCES_COOKIES", "")
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with appropriate headers and cookies."""
        session = requests.Session()
        
        # Parse cookies from string
        if self.cookies:
            cookie_dict = {}
            for item in self.cookies.split(';'):
                item = item.strip()
                if '=' in item:
                    key, value = item.split('=', 1)
                    cookie_dict[key.strip()] = value.strip()
            
            for key, value in cookie_dict.items():
                session.cookies.set(key, value)
        
        # Set headers
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        return session
    
    def find_editorial_url(self, contest_id: int, problem_letter: str) -> Optional[str]:
        """
        Find the editorial URL for a given contest and problem.
        
        Args:
            contest_id: Contest ID (e.g., 2191)
            problem_letter: Problem letter (e.g., 'A')
            
        Returns:
            Editorial URL if found, None otherwise
        """
        # Try to get the contest page
        contest_url = f"{self.BASE_URL}/contest/{contest_id}"
        
        try:
            response = self.session.get(contest_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for tutorial/editorial link
            # Codeforces usually has a "Tutorial" link in the contest page
            tutorial_links = soup.find_all('a', href=re.compile(r'/blog/entry/\d+'))
            
            if tutorial_links:
                editorial_path = tutorial_links[0]['href']
                return f"{self.BASE_URL}{editorial_path}"
            
            # Alternative: Try common editorial URL pattern
            # Sometimes editorials are at /contest/{id}/tutorial
            tutorial_url = f"{self.BASE_URL}/contest/{contest_id}/tutorial"
            response = self.session.head(tutorial_url, timeout=5)
            if response.status_code == 200:
                return tutorial_url
                
        except Exception as e:
            print(f"Warning: Could not find editorial URL: {e}", file=sys.stderr)
        
        return None
    
    def fetch_editorial(self, url: str, debug: bool = False) -> Tuple[bool, str]:
        """
        Fetch editorial content from a given URL.
        
        Args:
            url: Editorial URL
            debug: If True, print debug information
            
        Returns:
            Tuple of (success, content)
        """
        try:
            if debug:
                print(f"DEBUG: Fetching URL: {url}", file=sys.stderr)
                print(f"DEBUG: Cookies: {len(self.session.cookies)} cookies set", file=sys.stderr)
            
            response = self.session.get(url, timeout=15)
            
            if debug:
                print(f"DEBUG: Response status: {response.status_code}", file=sys.stderr)
                print(f"DEBUG: Response length: {len(response.text)} bytes", file=sys.stderr)
            
            # Check for Cloudflare blocking BEFORE raising for status
            if response.status_code == 403 or ('Cloudflare' in response.text and 'blocked' in response.text.lower()):
                return False, (
                    "Blocked by Cloudflare (403 Forbidden). Your cookies may be expired or invalid.\n"
                    "To fix this:\n"
                    "1. Login to Codeforces in your browser\n"
                    "2. Open DevTools (F12) → Network tab\n"
                    "3. Refresh the page and copy the Cookie header from any request\n"
                    "4. Update CODEFORCES_COOKIES in your .env file or pass with --cookies"
                )
            
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try multiple selectors for Codeforces content
            selectors = [
                ('div', {'class': 'ttypography'}),
                ('div', {'class': 'content'}),
                ('div', {'class': 'topic-text'}),
                ('div', {'id': 'pageContent'}),
                ('article', {}),
            ]
            
            content_div = None
            for tag, attrs in selectors:
                content_div = soup.find(tag, attrs)
                if content_div:
                    if debug:
                        print(f"DEBUG: Found content with selector: {tag} {attrs}", file=sys.stderr)
                    break
            
            if content_div:
                # Extract text content
                content = content_div.get_text(separator='\n', strip=True)
                
                if debug:
                    print(f"DEBUG: Extracted {len(content)} characters", file=sys.stderr)
                    print(f"DEBUG: First 200 chars: {content[:200]}", file=sys.stderr)
                
                return True, content
            else:
                if debug:
                    print("DEBUG: HTML structure:", file=sys.stderr)
                    # Print first 1000 chars of HTML to see structure
                    print(response.text[:1000], file=sys.stderr)
                
                return False, "Could not find editorial content in the page. Try --debug flag to see HTML structure."
                
        except requests.RequestException as e:
            return False, f"Error fetching editorial: {str(e)}"
    
    def get_editorial_for_problem(self, contest_id: int, problem_letter: str) -> Tuple[bool, str, Optional[str]]:
        """
        Get editorial for a specific problem.
        
        Args:
            contest_id: Contest ID
            problem_letter: Problem letter
            
        Returns:
            Tuple of (success, content, editorial_url)
        """
        # First, try to find the editorial URL
        editorial_url = self.find_editorial_url(contest_id, problem_letter)
        
        if not editorial_url:
            return False, f"Could not find editorial for contest {contest_id}", None
        
        # Fetch the editorial
        success, content = self.fetch_editorial(editorial_url)
        
        if success:
            # Try to extract the specific problem's editorial section
            # Usually editorials have headers like "A. Problem Name" or "Problem A"
            lines = content.split('\n')
            problem_section = []
            in_section = False
            
            for i, line in enumerate(lines):
                # Check if this line starts the problem section
                if re.match(rf'^{problem_letter}[.\s]', line, re.IGNORECASE) or \
                   re.search(rf'Problem\s+{problem_letter}', line, re.IGNORECASE):
                    in_section = True
                    problem_section.append(line)
                    continue
                
                # Check if we've reached the next problem
                if in_section:
                    next_letter = chr(ord(problem_letter.upper()) + 1)
                    if re.match(rf'^{next_letter}[.\s]', line, re.IGNORECASE) or \
                       re.search(rf'Problem\s+{next_letter}', line, re.IGNORECASE):
                        break
                    problem_section.append(line)
            
            if problem_section:
                return True, '\n'.join(problem_section), editorial_url
            else:
                # Return full content if we couldn't extract the specific section
                return True, content, editorial_url
        
        return success, content, editorial_url


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description='Fetch Codeforces problem editorials',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 2191 A
  %(prog)s --contest 2191 --problem A
  %(prog)s --url https://codeforces.com/blog/entry/150256
  
Environment Variables:
  CODEFORCES_COOKIES  - Your Codeforces authentication cookies
        """
    )
    
    parser.add_argument('contest_id', nargs='?', type=int, help='Contest ID (e.g., 2191)')
    parser.add_argument('problem_letter', nargs='?', help='Problem letter (e.g., A)')
    parser.add_argument('--contest', '-c', type=int, help='Contest ID')
    parser.add_argument('--problem', '-p', help='Problem letter')
    parser.add_argument('--url', '-u', help='Direct editorial URL')
    parser.add_argument('--cookies', help='Codeforces cookies (overrides env var)')
    parser.add_argument('--output', '-o', help='Output file (default: stdout)')
    parser.add_argument('--debug', '-d', action='store_true', help='Enable debug output')
    
    args = parser.parse_args()
    
    # Determine contest and problem
    contest_id = args.contest or args.contest_id
    problem_letter = args.problem or args.problem_letter
    
    if not args.url and (not contest_id or not problem_letter):
        parser.error("Either provide contest_id and problem_letter, or use --url")
    
    # Create fetcher
    fetcher = CodeforcesEditorialFetcher(cookies=args.cookies)
    
    # Fetch editorial
    if args.url:
        success, content = fetcher.fetch_editorial(args.url, debug=args.debug)
        editorial_url = args.url
    else:
        # Note: get_editorial_for_problem also calls fetch_editorial internally
        # We need to update it to pass debug flag
        editorial_url = fetcher.find_editorial_url(contest_id, problem_letter.upper())
        if editorial_url:
            success, content = fetcher.fetch_editorial(editorial_url, debug=args.debug)
        else:
            success = False
            content = f"Could not find editorial for contest {contest_id}"
    
    # Output results
    if success:
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(f"Editorial URL: {editorial_url}\n")
                f.write("=" * 80 + "\n\n")
                f.write(content)
            print(f"Editorial saved to: {args.output}")
        else:
            print(f"Editorial URL: {editorial_url}")
            print("=" * 80)
            print(content)
        
        return 0
    else:
        print(f"Error: {content}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
