"""
Code Review Agent - scans the codebase and provides structured
security, performance, and best-practice recommendations.

Can use Claude API (Anthropic) or OpenAI for LLM-powered analysis.
Falls back to rule-based checks if no API key is configured.
"""

import logging
import os
from dataclasses import dataclass, asdict
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).parent.parent


@dataclass
class ReviewIssue:
    file: str
    line: int | None
    severity: str  # "critical", "warning", "info"
    category: str  # "security", "performance", "scraping", "quality"
    issue: str
    recommendation: str


# Rule-based checks (always available, no API key needed)
SECURITY_PATTERNS = [
    {
        "pattern": "eval(",
        "issue": "Use of eval() is a code injection risk",
        "recommendation": "Remove eval() and use safe alternatives",
        "severity": "critical",
        "category": "security",
    },
    {
        "pattern": "shell=True",
        "issue": "subprocess with shell=True enables shell injection",
        "recommendation": "Use shell=False with argument list instead",
        "severity": "critical",
        "category": "security",
    },
    {
        "pattern": "nosec",
        "issue": "Security check suppressed with nosec comment",
        "recommendation": "Review whether the suppression is justified",
        "severity": "warning",
        "category": "security",
    },
    {
        "pattern": "password",
        "issue": "Potential hardcoded credential",
        "recommendation": "Use environment variables for secrets",
        "severity": "warning",
        "category": "security",
        "exclude_files": ["config.py", ".env", "reviewer.py"],
    },
]

PERFORMANCE_PATTERNS = [
    {
        "pattern": "select(*)",
        "issue": "SELECT * can be inefficient — only fetch needed columns",
        "recommendation": "Specify explicit columns in queries",
        "severity": "info",
        "category": "performance",
    },
    {
        "pattern": ".all()",
        "issue": "Unbounded query may load excessive data",
        "recommendation": "Add .limit() to prevent memory issues",
        "severity": "warning",
        "category": "performance",
        "exclude_files": ["reviewer.py"],
    },
]

SCRAPING_PATTERNS = [
    {
        "pattern": "time.sleep",
        "issue": "Blocking sleep in async context",
        "recommendation": "Use asyncio.sleep() instead",
        "severity": "warning",
        "category": "scraping",
    },
    {
        "pattern": "verify=False",
        "issue": "SSL verification disabled",
        "recommendation": "Enable SSL verification for security",
        "severity": "critical",
        "category": "security",
    },
    {
        "pattern": "timeout=None",
        "issue": "No request timeout — can hang indefinitely",
        "recommendation": "Set explicit timeout (e.g., timeout=30)",
        "severity": "warning",
        "category": "scraping",
    },
]


def scan_file_rules(filepath: Path, content: str) -> list[ReviewIssue]:
    """Scan a single file with rule-based checks."""
    issues = []
    fname = filepath.name

    all_patterns = SECURITY_PATTERNS + PERFORMANCE_PATTERNS + SCRAPING_PATTERNS

    for rule in all_patterns:
        exclude = rule.get("exclude_files", [])
        if fname in exclude:
            continue

        for i, line in enumerate(content.split("\n"), start=1):
            if rule["pattern"] in line and not line.strip().startswith("#"):
                issues.append(
                    ReviewIssue(
                        file=str(filepath.relative_to(BACKEND_ROOT)),
                        line=i,
                        severity=rule["severity"],
                        category=rule["category"],
                        issue=rule["issue"],
                        recommendation=rule["recommendation"],
                    )
                )

    return issues


def scan_codebase_rules() -> list[ReviewIssue]:
    """Scan entire backend codebase with rule-based checks."""
    issues = []

    for py_file in BACKEND_ROOT.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
            issues.extend(scan_file_rules(py_file, content))
        except Exception as e:
            logger.warning("Could not read %s: %s", py_file, e)

    return issues


async def review_with_llm(code_summary: str) -> list[dict] | None:
    """
    Use Claude API for deeper code review analysis.
    Returns None if no API key is configured.
    """
    if not settings.ANTHROPIC_API_KEY:
        return None

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        prompt = f"""You are a senior security engineer reviewing an OSINT intelligence dashboard.
Analyze this code summary and provide structured findings.

Focus on:
1. Security vulnerabilities (injection, auth, data exposure)
2. Inefficient database queries or missing indexes
3. Scraping best practices (rate limiting, error handling, robots.txt)
4. Data validation issues

Code summary:
{code_summary[:8000]}

Respond with a JSON array of objects with keys: file, severity, category, issue, recommendation.
Severity: critical, warning, info
Category: security, performance, scraping, quality"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        # Parse response - the LLM should return JSON
        import json

        text = response.content[0].text
        # Try to extract JSON from response
        if "[" in text:
            json_str = text[text.index("[") : text.rindex("]") + 1]
            return json.loads(json_str)
    except Exception as e:
        logger.warning("LLM review failed: %s", e)

    return None


async def run_full_review() -> dict:
    """
    Run complete code review: rule-based + optional LLM analysis.
    Returns structured report.
    """
    # Rule-based scan
    rule_issues = scan_codebase_rules()

    # Attempt LLM review
    llm_issues = []
    code_files = []
    for py_file in BACKEND_ROOT.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
            rel_path = str(py_file.relative_to(BACKEND_ROOT))
            code_files.append(f"--- {rel_path} ---\n{content[:500]}")
        except Exception:
            pass

    code_summary = "\n\n".join(code_files[:20])
    llm_results = await review_with_llm(code_summary)
    if llm_results:
        for r in llm_results:
            llm_issues.append(
                ReviewIssue(
                    file=r.get("file", "unknown"),
                    line=None,
                    severity=r.get("severity", "info"),
                    category=r.get("category", "quality"),
                    issue=r.get("issue", ""),
                    recommendation=r.get("recommendation", ""),
                )
            )

    all_issues = rule_issues + llm_issues

    # Build report
    critical = [i for i in all_issues if i.severity == "critical"]
    warnings = [i for i in all_issues if i.severity == "warning"]
    info = [i for i in all_issues if i.severity == "info"]

    return {
        "summary": {
            "total_issues": len(all_issues),
            "critical": len(critical),
            "warnings": len(warnings),
            "info": len(info),
            "llm_enabled": llm_results is not None,
        },
        "issues": [asdict(i) for i in all_issues],
    }
