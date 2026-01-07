#!/usr/bin/env python3
"""
Format Validation Results as Markdown Comment
Converts JSON validation results to user-friendly GitHub comment
"""

import argparse
import json
import sys
from urllib.parse import quote
from typing import Dict


def get_emoji(passed: bool, warning: bool = False) -> str:
    """
    Get emoji indicator for validation result.

    Args:
        passed: Whether check passed
        warning: Whether this is a warning state

    Returns:
        Emoji string
    """
    if warning:
        return "⚠️"
    return "✅" if passed else "❌"


def get_status_emoji(status: str) -> str:
    """
    Get emoji for overall status.

    Args:
        status: Overall status (pass/warning/fail)

    Returns:
        Emoji string
    """
    return {
        'pass': '✅',
        'warning': '⚠️',
        'fail': '❌'
    }.get(status, '❓')


def format_url_validation(validation: Dict) -> str:
    """Format URL format validation result."""
    passed = validation.get('passed', False)
    message = validation.get('message', 'Unknown')
    emoji = get_emoji(passed)
    return f"{emoji} **URL Format:** {message}"


def format_accessibility_validation(validation: Dict) -> str:
    """Format accessibility validation result."""
    passed = validation.get('passed', False)
    message = validation.get('message', 'Unknown')
    status_code = validation.get('status_code', 0)
    emoji = get_emoji(passed)

    if status_code > 0:
        return f"{emoji} **Accessibility:** {message} (HTTP {status_code})"
    else:
        return f"{emoji} **Accessibility:** {message}"


def format_structure_validation(validation: Dict) -> str:
    """Format feed structure validation result."""
    passed = validation.get('passed', False)
    message = validation.get('message', 'Unknown')
    feed_type = validation.get('feed_type')
    entries = validation.get('entries', 0)
    emoji = get_emoji(passed)

    if passed and entries > 0:
        return f"{emoji} **Feed Structure:** {message} ({entries} entries)"
    else:
        return f"{emoji} **Feed Structure:** {message}"


def format_duplicate_validation(validation: Dict) -> str:
    """Format duplicate check result."""
    passed = validation.get('passed', False)
    is_duplicate = validation.get('is_duplicate', False)
    message = validation.get('message', 'Unknown')
    existing_name = validation.get('existing_name')

    # Warning emoji if duplicate detected
    emoji = get_emoji(passed, warning=is_duplicate)

    if is_duplicate and existing_name:
        return f"{emoji} **Duplicate Check:** Feed already exists as \"{existing_name}\""
    else:
        return f"{emoji} **Duplicate Check:** {message}"


def format_content_validation(validation: Dict) -> str:
    """Format content analysis result."""
    python_score = validation.get('python_score', 0)
    warnings = validation.get('warnings', [])

    # Determine status based on score
    if python_score >= 60:
        emoji = "✅"
        status_text = "Good"
    elif python_score >= 30:
        emoji = "⚠️"
        status_text = "Moderate"
    else:
        emoji = "⚠️"
        status_text = "Low"

    result = f"{emoji} **Python Content:** {python_score}% Python keywords detected ({status_text})"

    # Add warnings if any
    if warnings and warnings[0] != 'Skipped (feed structure invalid)':
        for warning in warnings[:2]:  # Limit to 2 warnings
            result += f"\n   - ⚠️  {warning}"

    return result


def format_sample_titles(titles: list) -> str:
    """Format sample article titles."""
    if not titles:
        return ""

    result = "\n### 📝 Sample Article Titles\n\n"
    for i, title in enumerate(titles[:5], 1):
        result += f"{i}. {title}\n"

    return result


def format_recommendations(recommendations: list) -> str:
    """Format recommendations section."""
    if not recommendations:
        return ""

    result = "### 💡 Recommendations\n\n"
    for rec in recommendations:
        result += f"- {rec}\n"

    return result + "\n"


def generate_comment(result: Dict) -> str:
    """
    Generate full markdown comment from validation results.

    Args:
        result: Validation result dictionary

    Returns:
        Formatted markdown comment
    """
    feed_url = result.get('feed_url', 'Unknown')
    feed_name = result.get('feed_name', 'Unknown')
    request_type = result.get('request_type', 'Unknown')
    overall_status = result.get('overall_status', 'unknown')
    validations = result.get('validations', {})
    recommendations = result.get('recommendations', [])
    labels = result.get('labels', [])

    # Build comment
    comment = "## 🔍 Feed Validation Results\n\n"
    comment += f"**Feed URL:** `{feed_url}`\n"
    comment += f"**Feed Name:** {feed_name}\n"
    comment += f"**Request Type:** {request_type}\n\n"

    comment += "### Validation Checks\n\n"

    # Format each validation
    if 'url_format' in validations:
        comment += format_url_validation(validations['url_format']) + "\n"

    if 'accessibility' in validations:
        comment += format_accessibility_validation(validations['accessibility']) + "\n"

    if 'structure' in validations:
        comment += format_structure_validation(validations['structure']) + "\n"

    if 'duplicate' in validations:
        comment += format_duplicate_validation(validations['duplicate']) + "\n"

    if 'content' in validations:
        comment += format_content_validation(validations['content']) + "\n"

    comment += "\n---\n\n"

    # Overall status
    status_emoji = get_status_emoji(overall_status)
    status_text = overall_status.upper()
    comment += f"### {status_emoji} Overall Status: {status_text}\n\n"

    # Recommendations
    if recommendations:
        comment += format_recommendations(recommendations)

    # Sample titles (if available)
    sample_titles = validations.get('content', {}).get('sample_titles', [])
    if sample_titles and overall_status != 'fail':
        comment += format_sample_titles(sample_titles)

    # Next steps
    comment += "\n---\n\n"
    comment += "### 📋 Next Steps\n\n"

    if overall_status == 'fail':
        comment += "- ❌ Please fix the errors above and update your issue\n"
    elif overall_status == 'warning':
        comment += "- ⚠️ Review the warnings above\n"
        comment += "- ✅ A maintainer will review your submission\n"
    else:
        comment += "- ✅ Your feed looks good!\n"
        comment += "- 👀 A maintainer will review and add your feed\n"

    # W3C Validator link
    encoded_url = quote(feed_url, safe='')
    comment += f"\n**Additional Validation:** [W3C Feed Validator](https://validator.w3.org/feed/check.cgi?url={encoded_url})\n\n"

    # Footer
    comment += "---\n\n"
    comment += f"*🤖 Automated validation • Labels: `{', '.join(labels) if labels else 'none'}`*\n"
    comment += "*Maintainers will manually review Python-specific content and English language requirements.*\n"

    return comment


def main():
    """Main entry point for comment formatting script."""
    parser = argparse.ArgumentParser(description='Format validation results as markdown comment')
    parser.add_argument('--input', required=True, help='Input JSON file path')
    parser.add_argument('--output', required=True, help='Output markdown file path')

    args = parser.parse_args()

    try:
        # Read validation results
        with open(args.input, 'r') as f:
            result = json.load(f)

        # Generate comment
        comment = generate_comment(result)

        # Write comment to file
        with open(args.output, 'w') as f:
            f.write(comment)

        print(f"Comment generated successfully: {args.output}")
        sys.exit(0)

    except FileNotFoundError:
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error generating comment: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
