#!/usr/bin/env python3
"""
Feed Validation Script for Planet Python
Validates RSS/Atom feeds submitted via GitHub issues
"""

import argparse
import configparser
import json
import re
import sys
from urllib.parse import urlparse, quote
from typing import Dict, Tuple, List, Optional

try:
    import feedparser
    import requests
except ImportError:
    print("Error: Required dependencies not installed")
    print("Please install: pip install feedparser requests")
    sys.exit(1)


def parse_issue_body(issue_body: str) -> Dict[str, str]:
    """
    Parse GitHub issue form response to extract structured data.

    Args:
        issue_body: Raw issue body text from GitHub issue form

    Returns:
        Dictionary with extracted fields: feed-url, name, request-type, old-url
    """
    data = {}

    # Split by ### headers (GitHub issue form format)
    sections = re.split(r'\n### ', issue_body)

    for section in sections:
        if not section.strip():
            continue

        lines = section.strip().split('\n', 1)
        if len(lines) < 2:
            continue

        header = lines[0].strip()
        value = lines[1].strip() if len(lines) > 1 else ""

        # Skip empty responses
        if value == "_No response_" or value == "":
            continue

        # Map headers to field IDs
        header_lower = header.lower()
        if 'feed url' in header_lower and 'old' not in header_lower:
            data['feed-url'] = value
        elif 'name' in header_lower or 'blog name' in header_lower:
            data['name'] = value
        elif 'request type' in header_lower:
            data['request-type'] = value
        elif 'old' in header_lower and 'url' in header_lower:
            data['old-url'] = value

    return data


def validate_url_format(url: str) -> Tuple[bool, str]:
    """
    Validate URL format and scheme.

    Args:
        url: URL to validate

    Returns:
        Tuple of (is_valid, message)
    """
    try:
        parsed = urlparse(url)

        if not parsed.scheme:
            return False, "URL missing scheme (http:// or https://)"

        if parsed.scheme not in ['http', 'https']:
            return False, f"Invalid scheme '{parsed.scheme}' (must be http or https)"

        if not parsed.netloc:
            return False, "URL missing domain/hostname"

        return True, "Valid URL format"

    except Exception as e:
        return False, f"URL parsing error: {str(e)}"


def check_feed_accessibility(url: str, timeout: int = 10) -> Tuple[bool, int, Optional[str], str]:
    """
    Check if feed URL is accessible via HTTP.

    Args:
        url: Feed URL to check
        timeout: Request timeout in seconds

    Returns:
        Tuple of (is_accessible, status_code, final_url, message)
    """
    headers = {
        'User-Agent': 'PlanetPython/1.0 (+https://github.com/python/planet)'
    }

    try:
        response = requests.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers=headers
        )

        final_url = response.url if response.url != url else None

        if response.status_code == 200:
            redirect_msg = f" (redirected to {final_url})" if final_url else ""
            return True, response.status_code, final_url, f"Feed accessible{redirect_msg}"
        else:
            return False, response.status_code, None, f"HTTP {response.status_code}"

    except requests.Timeout:
        return False, 0, None, f"Request timed out after {timeout} seconds"
    except requests.ConnectionError:
        return False, 0, None, "Unable to connect to feed URL"
    except requests.TooManyRedirects:
        return False, 0, None, "Too many redirects"
    except Exception as e:
        return False, 0, None, f"Error: {str(e)}"


def validate_feed_structure(url: str) -> Tuple[bool, Optional[str], int, str]:
    """
    Validate RSS/Atom feed structure using feedparser.

    Args:
        url: Feed URL to parse

    Returns:
        Tuple of (is_valid, feed_type, entry_count, message)
    """
    try:
        feed = feedparser.parse(url)

        # Check for parsing errors (bozo bit)
        if feed.bozo:
            error_msg = str(feed.bozo_exception) if hasattr(feed, 'bozo_exception') else "Unknown parsing error"
            return False, None, 0, f"Feed parsing error: {error_msg}"

        # Check if feed type was detected
        if not hasattr(feed, 'version') or not feed.version:
            return False, None, 0, "Unable to detect feed format (not RSS or Atom)"

        # Check if feed has entries
        entry_count = len(feed.entries) if hasattr(feed, 'entries') else 0
        if entry_count == 0:
            return False, feed.version, 0, "Feed has no entries"

        feed_type_name = {
            'rss10': 'RSS 1.0',
            'rss20': 'RSS 2.0',
            'rss': 'RSS',
            'atom': 'Atom',
            'atom10': 'Atom 1.0',
            'atom03': 'Atom 0.3'
        }.get(feed.version, feed.version)

        return True, feed.version, entry_count, f"Valid {feed_type_name} feed"

    except Exception as e:
        return False, None, 0, f"Error parsing feed: {str(e)}"


def normalize_url(url: str) -> str:
    """
    Normalize URL for comparison (lowercase, strip trailing slash).

    Args:
        url: URL to normalize

    Returns:
        Normalized URL
    """
    url = url.lower().strip()
    if url.endswith('/'):
        url = url[:-1]
    return url


def check_duplicate_in_config(url: str, config_path: str, request_type: str,
                              old_url: Optional[str] = None) -> Tuple[bool, bool, Optional[str], str]:
    """
    Check if feed URL already exists in config.ini.

    Args:
        url: New feed URL to check
        config_path: Path to config.ini
        request_type: "Add new feed" or "Edit existing feed"
        old_url: Old feed URL (for edits)

    Returns:
        Tuple of (check_passed, is_duplicate, existing_name, message)
    """
    try:
        config = configparser.ConfigParser()
        config.read(config_path)

        normalized_new = normalize_url(url)

        # Check for duplicate
        for section in config.sections():
            if section == 'Planet':
                continue

            normalized_section = normalize_url(section)

            if normalized_section == normalized_new:
                name = config.get(section, 'name', fallback='Unknown')

                if request_type and 'edit' in request_type.lower():
                    # For edits, it's OK if the URL exists (might be the old URL)
                    return True, True, name, f"Feed exists as '{name}' (OK for edit)"
                else:
                    # For new feeds, duplicate is a problem
                    return False, True, name, f"Feed already exists as '{name}'"

        # If editing, check that old URL exists
        if request_type and 'edit' in request_type.lower() and old_url:
            normalized_old = normalize_url(old_url)
            old_found = False

            for section in config.sections():
                if section == 'Planet':
                    continue
                normalized_section = normalize_url(section)
                if normalized_section == normalized_old:
                    old_found = True
                    break

            if not old_found:
                return False, False, None, f"Old feed URL '{old_url}' not found in config"

        return True, False, None, "No duplicate found"

    except FileNotFoundError:
        return False, False, None, f"Config file not found: {config_path}"
    except Exception as e:
        return False, False, None, f"Error reading config: {str(e)}"


def analyze_feed_content(url: str, sample_size: int = 10) -> Tuple[int, Optional[str], List[str], List[str]]:
    """
    Analyze feed content for Python-related keywords.

    Args:
        url: Feed URL to analyze
        sample_size: Number of entries to sample

    Returns:
        Tuple of (python_score, language_hint, sample_titles, warnings)
    """
    python_keywords = [
        'python', 'django', 'flask', 'fastapi', 'pytest', 'pip',
        'pandas', 'numpy', 'asyncio', 'pypi', 'virtualenv', 'conda',
        'jupyter', 'matplotlib', 'scikit', 'tensorflow', 'pytorch'
    ]

    warnings = []

    try:
        feed = feedparser.parse(url)

        if feed.bozo or not hasattr(feed, 'entries'):
            return 0, None, [], ["Unable to parse feed for content analysis"]

        # Get language hint from feed metadata
        language = None
        if hasattr(feed, 'feed'):
            language = getattr(feed.feed, 'language', None)

        entries = feed.entries[:sample_size]
        if not entries:
            return 0, language, [], ["Feed has no entries to analyze"]

        # Analyze entries
        python_count = 0
        sample_titles = []

        for entry in entries:
            title = getattr(entry, 'title', '')
            summary = getattr(entry, 'summary', '')
            content = (title + ' ' + summary).lower()

            # Check if any Python keyword is present
            has_python = any(keyword in content for keyword in python_keywords)
            if has_python:
                python_count += 1

            # Collect sample titles
            if title and len(sample_titles) < 5:
                sample_titles.append(title[:100])

        # Calculate Python score (percentage)
        python_score = int((python_count / len(entries)) * 100)

        # Generate warnings
        if python_score < 30:
            warnings.append("Low Python content detected - feed may not be Python-specific")
        elif python_score < 60:
            warnings.append("Consider filtering your feed by Python tag/category for better relevance")

        return python_score, language, sample_titles, warnings

    except Exception as e:
        return 0, None, [], [f"Error analyzing content: {str(e)}"]


def determine_overall_status(validations: Dict) -> Tuple[str, List[str], List[str]]:
    """
    Determine overall validation status and generate labels and recommendations.

    Args:
        validations: Dictionary of validation results

    Returns:
        Tuple of (overall_status, labels, recommendations)
    """
    labels = []
    recommendations = []

    # Check critical validations
    critical_checks = ['url_format', 'accessibility', 'structure']
    has_critical_failure = any(
        not validations.get(check, {}).get('passed', False)
        for check in critical_checks
    )

    if has_critical_failure:
        labels.append('validation-failed')
        recommendations.append("Please fix the critical errors above before resubmitting")
        return 'fail', labels, recommendations

    # Check for duplicate
    is_duplicate = validations.get('duplicate', {}).get('is_duplicate', False)
    if is_duplicate:
        labels.append('duplicate-feed')
        recommendations.append("This feed appears to already exist - please verify this is an edit request")

    # Check Python content score
    python_score = validations.get('content', {}).get('python_score', 0)
    if python_score < 30:
        labels.append('validation-warning')
        recommendations.append("Feed appears to have low Python-specific content")
        recommendations.append("Consider providing a filtered feed URL (by tag/category)")
        return 'warning', labels, recommendations
    elif python_score < 60:
        labels.append('validation-warning')
        recommendations.append("Feed has moderate Python content - consider filtering by Python tag/category")
        return 'warning', labels, recommendations

    # All good!
    if not labels:
        labels.append('validation-passed')

    return 'pass', labels, recommendations


def main():
    """Main entry point for feed validation script."""
    parser = argparse.ArgumentParser(description='Validate RSS/Atom feed for Planet Python')
    parser.add_argument('--issue-body', required=True, help='GitHub issue body text')
    parser.add_argument('--config-path', required=True, help='Path to config.ini')
    parser.add_argument('--output', required=True, help='Output JSON file path')

    args = parser.parse_args()

    # Parse issue body
    issue_data = parse_issue_body(args.issue_body)
    feed_url = issue_data.get('feed-url', '')
    feed_name = issue_data.get('name', 'Unknown')
    request_type = issue_data.get('request-type', 'Add new feed')
    old_url = issue_data.get('old-url')

    # Initialize result structure
    result = {
        'success': True,
        'feed_url': feed_url,
        'feed_name': feed_name,
        'request_type': request_type,
        'validations': {},
        'overall_status': 'unknown',
        'labels': [],
        'recommendations': []
    }

    # If no feed URL found, fail early
    if not feed_url:
        result['success'] = False
        result['overall_status'] = 'fail'
        result['validations']['parsing'] = {
            'passed': False,
            'message': 'Unable to extract feed URL from issue body'
        }
        result['labels'] = ['validation-failed']
        result['recommendations'] = ['Please ensure the feed URL field is filled in the issue template']
    else:
        # Run validations

        # 1. URL Format
        url_valid, url_msg = validate_url_format(feed_url)
        result['validations']['url_format'] = {
            'passed': url_valid,
            'message': url_msg
        }

        # 2. Accessibility (only if URL format is valid)
        if url_valid:
            accessible, status_code, final_url, access_msg = check_feed_accessibility(feed_url)
            result['validations']['accessibility'] = {
                'passed': accessible,
                'status_code': status_code,
                'final_url': final_url,
                'message': access_msg
            }
        else:
            result['validations']['accessibility'] = {
                'passed': False,
                'status_code': 0,
                'message': 'Skipped (invalid URL format)'
            }

        # 3. Structure (only if accessible)
        if url_valid and result['validations']['accessibility']['passed']:
            struct_valid, feed_type, entry_count, struct_msg = validate_feed_structure(feed_url)
            result['validations']['structure'] = {
                'passed': struct_valid,
                'feed_type': feed_type,
                'entries': entry_count,
                'message': struct_msg
            }
        else:
            result['validations']['structure'] = {
                'passed': False,
                'message': 'Skipped (feed not accessible)'
            }

        # 4. Duplicate Check
        dup_passed, is_dup, existing_name, dup_msg = check_duplicate_in_config(
            feed_url, args.config_path, request_type, old_url
        )
        result['validations']['duplicate'] = {
            'passed': dup_passed,
            'is_duplicate': is_dup,
            'existing_name': existing_name,
            'message': dup_msg
        }

        # 5. Content Analysis (only if structure is valid)
        if result['validations']['structure'].get('passed', False):
            py_score, language, titles, warnings = analyze_feed_content(feed_url)
            result['validations']['content'] = {
                'python_score': py_score,
                'language': language,
                'sample_titles': titles,
                'warnings': warnings
            }
        else:
            result['validations']['content'] = {
                'python_score': 0,
                'warnings': ['Skipped (feed structure invalid)']
            }

        # Determine overall status
        overall_status, labels, recommendations = determine_overall_status(result['validations'])
        result['overall_status'] = overall_status
        result['labels'] = labels
        result['recommendations'] = recommendations

    # Write result to output file
    try:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Validation complete: {result['overall_status']}")
        sys.exit(0)
    except Exception as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
