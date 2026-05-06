"""
robots_audit.py
---------------
Validation: robots.txt CCBot Audit

Checks the robots.txt file for each audited domain to determine whether
any repository explicitly disallows Common Crawl's crawler (CCBot).

This constitutes the secondary validation described in paper Section 3.4:
  - Absence of CCBot exclusion = technical access was available
  - Confirms governance vacuum is a POLICY failure, not technical

Usage:
    python scripts/robots_audit.py

Output:
    results/robots_audit.csv   — per-institution robots.txt findings
"""
import os
import time
import requests
import pandas as pd
from tqdm import tqdm

INSTITUTIONS_CSV = "data/institutions.csv"
OUTPUT_CSV       = "results/robots_audit.csv"
REQUEST_DELAY    = 1.0
TIMEOUT          = 15


def fetch_robots(domain: str) -> dict:
    """
    Fetch and parse robots.txt for a domain.

    Returns dict:
        fetched          — bool, whether robots.txt was retrieved
        blocks_all       — bool, User-agent: * Disallow: /
        blocks_ccbot     — bool, User-agent: CCBot explicitly blocked
        allows_ccbot     — bool, User-agent: CCBot explicitly allowed
        raw_text         — first 2000 chars of robots.txt or error message
    """
    url = f"https://{domain}/robots.txt"
    result = {
        "fetched":       False,
        "blocks_all":    False,
        "blocks_ccbot":  False,
        "allows_ccbot":  False,
        "raw_text":      "",
        "error":         None,
    }

    try:
        resp = requests.get(url, timeout=TIMEOUT,
                            headers={"User-Agent": "Mozilla/5.0 (research audit)"})

        if resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code}"
            return result

        result["fetched"]   = True
        text                = resp.text
        result["raw_text"]  = text[:2000]
        lines               = [l.strip().lower() for l in text.splitlines()]

        # Parse rules
        current_agent = None
        for line in lines:
            if line.startswith("user-agent:"):
                current_agent = line.split(":", 1)[1].strip()
            elif line.startswith("disallow:") and current_agent is not None:
                disallow_path = line.split(":", 1)[1].strip()
                if current_agent == "*" and disallow_path == "/":
                    result["blocks_all"] = True
                if current_agent == "ccbot" and disallow_path in ("/", "/*"):
                    result["blocks_ccbot"] = True
            elif line.startswith("allow:") and current_agent == "ccbot":
                result["allows_ccbot"] = True

    except Exception as exc:
        result["error"] = str(exc)

    return result


def run_robots_audit(dry_run: bool = False) -> pd.DataFrame:
    os.makedirs("results", exist_ok=True)

    institutions = pd.read_csv(INSTITUTIONS_CSV)
    records = []

    for _, row in tqdm(institutions.iterrows(), total=len(institutions),
                       desc="Checking robots.txt"):
        domain      = row["domain"]
        institution = row["institution"]

        if dry_run:
            rb = {"fetched": False, "blocks_all": False, "blocks_ccbot": False,
                  "allows_ccbot": False, "raw_text": "", "error": "dry_run"}
        else:
            rb = fetch_robots(domain)
            time.sleep(REQUEST_DELAY)

        # Interpretation
        if rb["blocks_ccbot"]:
            interpretation = "PROTECTED — CCBot explicitly blocked"
        elif rb["blocks_all"]:
            interpretation = "PROTECTED — all crawlers blocked (Disallow: /)"
        elif rb["fetched"]:
            interpretation = "UNPROTECTED — no CCBot exclusion found"
        else:
            interpretation = f"UNKNOWN — could not fetch ({rb['error']})"

        records.append({
            "institution":    institution,
            "domain":         domain,
            "robots_fetched": rb["fetched"],
            "blocks_all":     rb["blocks_all"],
            "blocks_ccbot":   rb["blocks_ccbot"],
            "allows_ccbot":   rb["allows_ccbot"],
            "interpretation": interpretation,
            "error":          rb["error"] or "",
        })

    df = pd.DataFrame(records)
    df.to_csv(OUTPUT_CSV, index=False)

    print(f"\n✓ robots.txt audit complete → {OUTPUT_CSV}")
    print("\nKey findings:")
    for _, r in df.iterrows():
        print(f"  {r['institution']:<40} {r['interpretation']}")

    n_protected   = df["blocks_ccbot"].sum() + df["blocks_all"].sum()
    n_unprotected = (df["robots_fetched"] & ~df["blocks_ccbot"] & ~df["blocks_all"]).sum()
    print(f"\nSummary: {n_protected} protected, {n_unprotected} unprotected, "
          f"{(~df['robots_fetched']).sum()} unknown/unreachable")

    return df


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="robots.txt CCBot audit for ETD repositories")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    run_robots_audit(dry_run=args.dry_run)
