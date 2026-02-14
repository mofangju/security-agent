"""Traffic generator CLI.

Usage:
    python -m security_agent.traffic --mode client    # Legitimate browsing
    python -m security_agent.traffic --mode attacker  # Attack payloads
    python -m security_agent.traffic --mode both      # Combined
"""

from __future__ import annotations

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Security Agent Traffic Generator")
    parser.add_argument(
        "--mode",
        choices=["client", "attacker", "both"],
        default="both",
        help="Traffic mode: client (legitimate), attacker (attacks), or both",
    )
    parser.add_argument(
        "--target",
        default="http://localhost:8080",
        help="Target URL (default: http://localhost:8080)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=1,
        help="Number of traffic rounds (default: 1)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between requests in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--category",
        nargs="*",
        choices=["sqli", "xss", "traversal", "cmdi"],
        help="Attack categories to include (default: all)",
    )
    args = parser.parse_args()

    print(f"🚦 Security Agent Traffic Generator")
    print(f"   Target: {args.target}")
    print(f"   Mode:   {args.mode}")
    print()

    if args.mode in ("client", "both"):
        from security_agent.traffic.client import generate_client_traffic

        print("═" * 50)
        print("  Phase: Legitimate Client Traffic")
        print("═" * 50)
        generate_client_traffic(
            base_url=args.target,
            rounds=args.rounds,
            delay_range=(args.delay, args.delay * 3),
        )
        print()

    if args.mode in ("attacker", "both"):
        from security_agent.traffic.attacker import generate_attacker_traffic

        print("═" * 50)
        print("  Phase: Attacker Traffic")
        print("═" * 50)
        generate_attacker_traffic(
            base_url=args.target,
            delay=args.delay,
            categories=args.category,
        )


if __name__ == "__main__":
    main()
