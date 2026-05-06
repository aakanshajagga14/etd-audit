"""
licensing_audit.py
------------------
Phase 3: Licensing Gap Analysis.

For each audited ETD repository:
  - Records stated license type
  - Checks whether the license explicitly permits or prohibits AI training use
  - Classifies each institution as: permitted / prohibited / gap (vacuum)
  - Saves results to data/licenses/licensing_audit.csv
  - Prints a summary breakdown

Usage:
    python licensing_audit.py
    python licensing_audit.py --output results/licensing_gap.csv
"""
import argparse
import csv
from pathlib import Path

# ---------------------------------------------------------------------------
# License database
# Manually compiled from institutional ETD submission pages (Jan 2026).
# Fields:
#   license_type     — stated license
#   ai_training      — "permitted" | "prohibited" | "gap"
#   ai_policy_note   — explanation
#   source_url       — where license info was retrieved
# ---------------------------------------------------------------------------

LICENSE_DATA = {
    "shodhganga.inflibnet.ac.in": {
        "name": "Shodhganga (India)",
        "region": "Global South",
        "license_type": "CC-BY-NC",
        "ai_training": "gap",
        "ai_policy_note": (
            "CC-BY-NC prohibits commercial use but does not address AI training. "
            "No INFLIBNET or UGC policy statement covers ML/AI training use. "
            "Non-commercial AI training may be permitted under literal reading; "
            "commercial AI training likely prohibited — but unenforced."
        ),
        "source_url": "https://shodhganga.inflibnet.ac.in/about",
    },
    "etd.iisc.ac.in": {
        "name": "IISc Bangalore",
        "region": "Global South",
        "license_type": "Institutional",
        "ai_training": "gap",
        "ai_policy_note": (
            "Institutional deposit agreement grants IISc rights to distribute "
            "for educational/research purposes. No AI training clause. Gap."
        ),
        "source_url": "https://etd.iisc.ac.in/",
    },
    "eprint.iitd.ac.in": {
        "name": "IIT Delhi",
        "region": "Global South",
        "license_type": "Institutional",
        "ai_training": "gap",
        "ai_policy_note": "Institutional license; no AI training policy found.",
        "source_url": "https://eprint.iitd.ac.in/",
    },
    "etd.library.iitb.ac.in": {
        "name": "IIT Bombay",
        "region": "Global South",
        "license_type": "Institutional",
        "ai_training": "gap",
        "ai_policy_note": "Institutional license; no AI training policy found.",
        "source_url": "https://etd.library.iitb.ac.in/",
    },
    "archiweb.iitm.ac.in": {
        "name": "IIT Madras",
        "region": "Global South",
        "license_type": "Institutional",
        "ai_training": "gap",
        "ai_policy_note": "Institutional license; no AI training policy found.",
        "source_url": "https://archiweb.iitm.ac.in/",
    },
    "dspace.mit.edu": {
        "name": "MIT DSpace",
        "region": "Global North",
        "license_type": "CC-BY",
        "ai_training": "gap",
        "ai_policy_note": (
            "CC-BY 4.0 permits broad reuse including adaptation and redistribution. "
            "Does not explicitly address AI/ML training. "
            "MIT Libraries have no published AI training policy as of Jan 2026."
        ),
        "source_url": "https://dspace.mit.edu/",
    },
    "escholarship.org": {
        "name": "UCLA eScholarship",
        "region": "Global North",
        "license_type": "CC-BY",
        "ai_training": "gap",
        "ai_policy_note": (
            "CC-BY 4.0. UC system open access policy does not address AI training."
        ),
        "source_url": "https://escholarship.org/",
    },
    "vtechworks.lib.vt.edu": {
        "name": "Virginia Tech VTechWorks",
        "region": "Global North",
        "license_type": "CC-BY",
        "ai_training": "gap",
        "ai_policy_note": (
            "Virginia Tech ETD mandate requires open access deposit. "
            "CC-BY applied; no AI training restriction or permission stated."
        ),
        "source_url": "https://vtechworks.lib.vt.edu/",
    },
    "deepblue.lib.umich.edu": {
        "name": "University of Michigan Deep Blue",
        "region": "Global North",
        "license_type": "Mixed",
        "ai_training": "gap",
        "ai_policy_note": (
            "Licenses vary by submission: some CC-BY, some institutional. "
            "No repository-wide AI training policy."
        ),
        "source_url": "https://deepblue.lib.umich.edu/",
    },
    "openresearch-repository.anu.edu.au": {
        "name": "Australian National University",
        "region": "Global North",
        "license_type": "CC-BY",
        "ai_training": "gap",
        "ai_policy_note": "ANU open access mandate; CC-BY; no AI training policy.",
        "source_url": "https://openresearch-repository.anu.edu.au/",
    },
    "ethos.bl.uk": {
        "name": "EThOS (British Library)",
        "region": "Global North",
        "license_type": "Subscription/Restricted",
        "ai_training": "gap",
        "ai_policy_note": (
            "EThOS operates under British Library licensing terms. "
            "Bulk downloading is prohibited under terms of service. "
            "No explicit AI training permission. "
            "Presence in Common Crawl suggests ToS enforcement gap."
        ),
        "source_url": "https://ethos.bl.uk/",
    },
    "dart-europe.org": {
        "name": "DART Europe",
        "region": "Global North",
        "license_type": "Mixed",
        "ai_training": "gap",
        "ai_policy_note": (
            "DART Europe aggregates from member institutions with varying licenses. "
            "No consortium-level AI training policy."
        ),
        "source_url": "https://www.dart-europe.org/",
    },
    "ndltd.org": {
        "name": "NDLTD Union Catalog",
        "region": "Global",
        "license_type": "Mixed",
        "ai_training": "gap",
        "ai_policy_note": (
            "NDLTD aggregates metadata; individual ETDs governed by member institution licenses. "
            "No NDLTD-level AI training policy exists as of Jan 2026."
        ),
        "source_url": "https://ndltd.org/",
    },
    "oatd.org": {
        "name": "OATD",
        "region": "Global",
        "license_type": "Mixed",
        "ai_training": "gap",
        "ai_policy_note": (
            "OATD indexes metadata from many repositories. "
            "No OATD-level AI training policy."
        ),
        "source_url": "https://oatd.org/",
    },
    "proquest.com": {
        "name": "ProQuest Dissertations",
        "region": "Commercial",
        "license_type": "Subscription/Restricted",
        "ai_training": "gap",
        "ai_policy_note": (
            "ProQuest requires subscription; ToS prohibits bulk downloading and "
            "automated scraping. AI training use not explicitly addressed. "
            "Presence in Common Crawl likely violates ToS."
        ),
        "source_url": "https://proquest.com/",
    },
}

# Classification labels
AI_TRAINING_LABELS = {
    "permitted":  "Explicitly permitted — license or policy statement allows AI training",
    "prohibited": "Explicitly prohibited — license or policy statement disallows AI training",
    "gap":        "Governance gap — neither permitted nor prohibited; vacuum",
}

RESULTS_DIR = Path("results")
LICENSE_DIR = Path("data/licenses")
RESULTS_DIR.mkdir(exist_ok=True)
LICENSE_DIR.mkdir(parents=True, exist_ok=True)


def run_licensing_audit() -> list:
    rows = []
    gap_count = 0
    permitted_count = 0
    prohibited_count = 0

    for domain, data in LICENSE_DATA.items():
        row = {
            "domain": domain,
            "name": data["name"],
            "region": data["region"],
            "license_type": data["license_type"],
            "ai_training": data["ai_training"],
            "ai_policy_note": data["ai_policy_note"],
            "source_url": data["source_url"],
        }
        rows.append(row)

        if data["ai_training"] == "gap":
            gap_count += 1
        elif data["ai_training"] == "permitted":
            permitted_count += 1
        elif data["ai_training"] == "prohibited":
            prohibited_count += 1

    total = len(rows)
    print(f"\nLicensing Audit Summary")
    print(f"{'─' * 50}")
    print(f"Total institutions audited : {total}")
    print(f"Governance gap (vacuum)    : {gap_count} ({gap_count/total*100:.1f}%)")
    print(f"Explicitly permitted       : {permitted_count} ({permitted_count/total*100:.1f}%)")
    print(f"Explicitly prohibited      : {prohibited_count} ({prohibited_count/total*100:.1f}%)")
    print()

    # License type breakdown
    license_counts = {}
    for row in rows:
        lt = row["license_type"]
        license_counts[lt] = license_counts.get(lt, 0) + 1

    print("License type breakdown:")
    for lt, count in sorted(license_counts.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        print(f"  {lt:<30} {count:>3} ({pct:.1f}%)")

    return rows


def write_licensing_csv(rows: list, path: Path):
    fieldnames = ["domain", "name", "region", "license_type",
                  "ai_training", "ai_policy_note", "source_url"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nLicensing audit saved to {path}")


def main():
    parser = argparse.ArgumentParser(description="ETD Licensing Gap Analysis")
    parser.add_argument(
        "--output",
        default="results/licensing_audit.csv",
        help="Output CSV path",
    )
    args = parser.parse_args()

    rows = run_licensing_audit()
    write_licensing_csv(rows, Path(args.output))

    # Also save to data/licenses for archival
    write_licensing_csv(rows, LICENSE_DIR / "licensing_audit.csv")


if __name__ == "__main__":
    main()
