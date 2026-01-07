#!/usr/bin/env python3
"""
Extract Labels from Validation Results
Simple helper script to extract labels for gh CLI
"""

import json
import sys


def main():
    """Extract and print labels from validation result JSON."""
    if len(sys.argv) < 2:
        print("Usage: get_labels.py <validation_result.json>", file=sys.stderr)
        sys.exit(1)

    try:
        with open(sys.argv[1], 'r') as f:
            result = json.load(f)

        labels = result.get('labels', [])

        if labels:
            # Print labels comma-separated for gh CLI
            print(','.join(labels))
        # If no labels, print nothing (script returns successfully)

    except FileNotFoundError:
        print(f"Error: File not found: {sys.argv[1]}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error: Invalid JSON format", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
