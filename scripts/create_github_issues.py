"""
create_github_issues.py

Parses issues.txt and creates GitHub Issues + Milestones + Labels
via the GitHub REST API.

Usage:
    python scripts/create_github_issues.py \
        --repo owner/repo-name \
        --token ghp_xxxxxxxxxxxx \
        --issues-file issues.txt \
        [--dry-run]

Environment variable alternative (preferred for CI):
    GITHUB_TOKEN=ghp_xxx
    GITHUB_REPOSITORY=owner/repo-name

Flags:
    --dry-run       Print what would be created without calling the API.
    --skip-existing Skip issues whose title already exists in the repo.
"""

import argparse
import os
import sys
import time
import re
import json
import logging
from dataclasses import dataclass, field
from typing import Optional
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("create_github_issues")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    id: int
    title: str
    labels: list[str]
    milestone: str
    description: str
    body: str = field(init=False)

    def __post_init__(self) -> None:
        self.body = self.description.strip()


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_issues_file(path: str) -> list[Issue]:
    """Parse the structured issues.txt file into a list of Issue objects."""
    with open(path, encoding="utf-8") as fh:
        content = fh.read()

    raw_blocks = re.split(r"--- ISSUE START ---", content)
    issues: list[Issue] = []

    for block in raw_blocks:
        end_idx = block.find("--- ISSUE END ---")
        if end_idx == -1:
            continue
        block = block[:end_idx].strip()
        if not block:
            continue

        def extract(field_name: str) -> str:
            pattern = rf"^{field_name}:\s*(.+)$"
            match = re.search(pattern, block, re.MULTILINE)
            return match.group(1).strip() if match else ""

        issue_id_str = extract("ID")
        title = extract("TITLE")
        labels_str = extract("LABELS")
        milestone = extract("MILESTONE")

        # Description is everything after the MILESTONE line
        desc_match = re.search(r"^DESCRIPTION:\s*\n(.*)", block, re.DOTALL | re.MULTILINE)
        description = desc_match.group(1).strip() if desc_match else ""

        if not title:
            log.warning("Skipping block with no TITLE: %s", block[:80])
            continue

        labels = [lb.strip() for lb in labels_str.split(",") if lb.strip()]

        try:
            issue_id = int(issue_id_str)
        except ValueError:
            issue_id = 0

        issues.append(Issue(
            id=issue_id,
            title=title,
            labels=labels,
            milestone=milestone,
            description=description,
        ))

    log.info("Parsed %d issues from %s", len(issues), path)
    return issues


# ---------------------------------------------------------------------------
# GitHub API client (stdlib only — no third-party deps required)
# ---------------------------------------------------------------------------

class GitHubClient:
    BASE = "https://api.github.com"

    def __init__(self, token: str, repo: str) -> None:
        self.token = token
        self.repo = repo  # "owner/name"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[dict] = None,
        expected_status: int = 200,
    ) -> dict:
        url = f"{self.BASE}{path}"
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode()
            log.error("HTTP %s %s -> %d: %s", method, url, exc.code, error_body)
            if exc.code == 422:
                # Resource may already exist; return the error body so caller can decide
                return json.loads(error_body) if error_body else {}
            raise

    # -- Milestones ----------------------------------------------------------

    def list_milestones(self) -> dict[str, int]:
        """Return {title: number} for all open milestones."""
        result = self._request("GET", f"/repos/{self.repo}/milestones?state=all&per_page=100")
        if isinstance(result, list):
            return {m["title"]: m["number"] for m in result}
        return {}

    def create_milestone(self, title: str) -> int:
        log.info("  Creating milestone: %s", title)
        resp = self._request("POST", f"/repos/{self.repo}/milestones", {"title": title})
        return resp.get("number", 0)

    def ensure_milestones(self, titles: set[str]) -> dict[str, int]:
        existing = self.list_milestones()
        for title in sorted(titles):
            if title and title not in existing:
                number = self.create_milestone(title)
                existing[title] = number
                time.sleep(0.3)
        return existing

    # -- Labels --------------------------------------------------------------

    def list_labels(self) -> set[str]:
        result = self._request("GET", f"/repos/{self.repo}/labels?per_page=100")
        if isinstance(result, list):
            return {lb["name"] for lb in result}
        return set()

    def create_label(self, name: str) -> None:
        color = _label_color(name)
        log.info("  Creating label: %s (%s)", name, color)
        self._request("POST", f"/repos/{self.repo}/labels", {"name": name, "color": color})

    def ensure_labels(self, names: set[str]) -> None:
        existing = self.list_labels()
        for name in sorted(names):
            if name and name not in existing:
                self.create_label(name)
                time.sleep(0.3)

    # -- Issues --------------------------------------------------------------

    def list_issue_titles(self) -> set[str]:
        """Fetch all open + closed issue titles to detect duplicates."""
        titles: set[str] = set()
        for state in ("open", "closed"):
            page = 1
            while True:
                result = self._request(
                    "GET",
                    f"/repos/{self.repo}/issues?state={state}&per_page=100&page={page}",
                )
                if not isinstance(result, list) or not result:
                    break
                for issue in result:
                    if "pull_request" not in issue:
                        titles.add(issue["title"])
                page += 1
        return titles

    def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str],
        milestone_number: Optional[int],
    ) -> int:
        payload: dict = {"title": title, "body": body, "labels": labels}
        if milestone_number:
            payload["milestone"] = milestone_number
        log.info("  Creating issue: %s", title)
        resp = self._request("POST", f"/repos/{self.repo}/issues", payload)
        return resp.get("number", 0)


# ---------------------------------------------------------------------------
# Label color palette by prefix
# ---------------------------------------------------------------------------

_COLOR_MAP = {
    "phase:foundations": "0075ca",
    "phase:auth":        "e4e669",
    "phase:crm":         "a2eeef",
    "phase:workshop":    "d93f0b",
    "phase:inventory":   "0e8a16",
    "phase:commercial":  "1d76db",
    "phase:finance":     "5319e7",
    "phase:purchasing":  "e99695",
    "phase:notifications":"f9d0c4",
    "phase:inspection":  "c5def5",
    "phase:reporting":   "bfd4f2",
    "phase:ged":         "fef2c0",
    "phase:hardening":   "b60205",
    "type:feat":         "0075ca",
    "type:chore":        "e4e669",
    "type:docs":         "cfd3d7",
    "type:test":         "d4c5f9",
    "type:perf":         "0e8a16",
    "type:security":     "b60205",
    "priority:critical": "b60205",
    "priority:high":     "d93f0b",
    "priority:medium":   "e4e669",
    "priority:low":      "0e8a16",
}

def _label_color(name: str) -> str:
    return _COLOR_MAP.get(name, "ededed")


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def run(
    issues_file: str,
    repo: str,
    token: str,
    dry_run: bool,
    skip_existing: bool,
) -> None:
    issues = parse_issues_file(issues_file)
    if not issues:
        log.error("No issues parsed from %s — aborting.", issues_file)
        sys.exit(1)

    if dry_run:
        log.info("DRY RUN — no API calls will be made.")
        for issue in issues:
            print(f"  [{issue.id:03d}] {issue.title}")
            print(f"         labels:    {', '.join(issue.labels)}")
            print(f"         milestone: {issue.milestone}")
            print()
        return

    client = GitHubClient(token=token, repo=repo)

    # 1. Collect all unique milestones and labels
    all_milestones = {i.milestone for i in issues if i.milestone}
    all_labels = {lb for i in issues for lb in i.labels}

    log.info("Ensuring %d milestones...", len(all_milestones))
    milestone_map = client.ensure_milestones(all_milestones)

    log.info("Ensuring %d labels...", len(all_labels))
    client.ensure_labels(all_labels)

    # 2. Optionally fetch existing titles to skip duplicates
    existing_titles: set[str] = set()
    if skip_existing:
        log.info("Fetching existing issue titles to detect duplicates...")
        existing_titles = client.list_issue_titles()
        log.info("Found %d existing issues.", len(existing_titles))

    # 3. Create issues
    created = 0
    skipped = 0
    for issue in issues:
        if skip_existing and issue.title in existing_titles:
            log.info("  SKIP (already exists): %s", issue.title)
            skipped += 1
            continue

        milestone_number = milestone_map.get(issue.milestone)
        issue_number = client.create_issue(
            title=issue.title,
            body=issue.body,
            labels=issue.labels,
            milestone_number=milestone_number,
        )
        if issue_number:
            log.info("    -> Created #%d", issue_number)
            created += 1
        # Respect GitHub secondary rate limit (avoid burst)
        time.sleep(0.8)

    log.info("Done. Created: %d | Skipped: %d | Total parsed: %d", created, skipped, len(issues))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Create GitHub Issues from issues.txt")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""), help="owner/repo")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""), help="GitHub personal access token")
    parser.add_argument("--issues-file", default="issues.txt", help="Path to issues.txt (default: issues.txt)")
    parser.add_argument("--dry-run", action="store_true", help="Print issues without creating them")
    parser.add_argument("--skip-existing", action="store_true", default=True, help="Skip issues whose title already exists (default: True)")
    args = parser.parse_args()

    if not args.dry_run:
        if not args.repo:
            log.error("--repo or GITHUB_REPOSITORY env var is required.")
            sys.exit(1)
        if not args.token:
            log.error("--token or GITHUB_TOKEN env var is required.")
            sys.exit(1)

    run(
        issues_file=args.issues_file,
        repo=args.repo,
        token=args.token,
        dry_run=args.dry_run,
        skip_existing=args.skip_existing,
    )


if __name__ == "__main__":
    main()
