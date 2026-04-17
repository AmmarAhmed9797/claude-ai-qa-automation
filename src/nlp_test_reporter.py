"""
NLP Test Reporter — AI-Powered Test Report Generator
Author: Muhammad Ammar Ahmed — Senior Test Automation Engineer

Transforms raw test results (JUnit XML, JSON, Allure) into
beautiful, human-readable reports using Claude claude-opus-4-6.
Generates reports for different audiences: executives, developers, QA teams.
"""

import anthropic
import json
import xml.etree.ElementTree as ET
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReportAudience(Enum):
    EXECUTIVE   = "executive"      # High-level KPIs, business impact
    DEVELOPER   = "developer"      # Technical details, stack traces, fix hints
    QA_TEAM     = "qa_team"        # Test coverage, gaps, recommendations
    STAKEHOLDER = "stakeholder"    # Plain English, no jargon


class ReportFormat(Enum):
    MARKDOWN   = "markdown"
    HTML       = "html"
    PLAIN_TEXT = "plain_text"
    JIRA       = "jira"


@dataclass
class TestSummary:
    total:    int = 0
    passed:   int = 0
    failed:   int = 0
    skipped:  int = 0
    duration: float = 0.0
    suite:    str = ""
    failures: list = None

    def __post_init__(self):
        if self.failures is None:
            self.failures = []

    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total * 100) if self.total > 0 else 0

    @property
    def status(self) -> str:
        if self.failed == 0:
            return "PASSED"
        elif self.failed <= self.total * 0.1:
            return "UNSTABLE"
        return "FAILED"


class NLPTestReporter:
    """
    AI-powered test report generator.
    Converts raw test data into intelligent, actionable reports.
    """

    MODEL = "claude-opus-4-6"

    def __init__(self, api_key: Optional[str] = None):
        self.client = anthropic.Anthropic(api_key=api_key)
        logger.info("NLPTestReporter initialized")

    def parse_junit_xml(self, xml_path: str) -> TestSummary:
        """Parse JUnit XML results file into TestSummary."""
        tree = ET.parse(xml_path)
        root = tree.getroot()
        summary = TestSummary(suite=root.get("name", "Test Suite"))

        for testsuite in root.iter("testsuite"):
            summary.total   += int(testsuite.get("tests", 0))
            summary.failed  += int(testsuite.get("failures", 0)) + int(testsuite.get("errors", 0))
            summary.skipped += int(testsuite.get("skipped", 0))
            summary.duration += float(testsuite.get("time", 0))

        summary.passed = summary.total - summary.failed - summary.skipped

        for failure in root.iter("failure"):
            tc = failure.getparent()
            summary.failures.append({
                "test": tc.get("name", "Unknown") if tc is not None else "Unknown",
                "message": failure.get("message", ""),
                "details": failure.text or ""
            })
        return summary

    def parse_json_results(self, results: dict) -> TestSummary:
        """Parse JSON test results into TestSummary."""
        summary = TestSummary(
            total   = results.get("total", 0),
            passed  = results.get("passed", 0),
            failed  = results.get("failed", 0),
            skipped = results.get("skipped", 0),
            duration= results.get("duration", 0.0),
            suite   = results.get("suite", "Test Suite"),
            failures= results.get("failures", [])
        )
        return summary

    def generate_report(self, summary: TestSummary,
                         audience: ReportAudience = ReportAudience.QA_TEAM,
                         fmt: ReportFormat = ReportFormat.MARKDOWN,
                         context: str = "") -> str:
        """
        Generate an intelligent test report using Claude.

        Args:
            summary: Parsed test results summary
            audience: Target audience for the report
            fmt: Output format
            context: Additional context (module name, sprint, etc.)

        Returns:
            Formatted report string
        """
        prompt = self._build_prompt(summary, audience, fmt, context)
        logger.info(f"Generating {audience.value} report for {summary.suite}...")

        response = self.client.messages.create(
            model=self.MODEL,
            max_tokens=2048,
            system=self._system_prompt(audience, fmt),
            messages=[{"role": "user", "content": prompt}]
        )

        report = response.content[0].text
        logger.info(f"Report generated: {len(report)} characters")
        return report

    def analyze_failures(self, failures: list[dict]) -> str:
        """Use Claude to analyze test failures and suggest fixes."""
        if not failures:
            return "No failures to analyze."

        failures_text = json.dumps(failures, indent=2)
        response = self.client.messages.create(
            model=self.MODEL,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": f"""Analyze these test failures and provide:
1. Root cause for each failure
2. Suggested code fix
3. Whether it's a test bug or product bug
4. Priority for fixing (Critical/High/Medium/Low)

Failures:
{failures_text}

Format as a structured analysis with clear sections per failure."""
            }]
        )
        return response.content[0].text

    def generate_trend_analysis(self, historical_results: list[dict]) -> str:
        """Analyze test trends over multiple runs."""
        data = json.dumps(historical_results, indent=2)
        response = self.client.messages.create(
            model=self.MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": f"""Analyze these test run trends and provide:
1. Pass rate trend (improving/declining/stable)
2. Flaky tests identification
3. Areas of concern
4. Recommendations for improvement

Historical data (most recent last):
{data}"""
            }]
        )
        return response.content[0].text

    def _system_prompt(self, audience: ReportAudience, fmt: ReportFormat) -> str:
        audience_guides = {
            ReportAudience.EXECUTIVE:
                "Write for C-suite executives. Focus on business impact, risk, and KPIs. No technical jargon. Use percentages and business outcomes.",
            ReportAudience.DEVELOPER:
                "Write for software developers. Include technical details, error messages, root causes, and code-level fix suggestions.",
            ReportAudience.QA_TEAM:
                "Write for QA engineers. Include coverage analysis, test gaps, flaky test patterns, and testing recommendations.",
            ReportAudience.STAKEHOLDER:
                "Write in plain English for non-technical stakeholders. Explain what passed/failed in business terms.",
        }
        fmt_guide = "Use Markdown formatting with headers, tables, and bullet points." if fmt == ReportFormat.MARKDOWN else "Use plain text."
        return f"You are an expert QA report writer. {audience_guides[audience]} {fmt_guide}"

    def _build_prompt(self, s: TestSummary, audience: ReportAudience,
                       fmt: ReportFormat, context: str) -> str:
        return f"""Generate a test execution report from these results:

Suite: {s.suite}
Status: {s.status}
Results: {s.passed}/{s.total} passed ({s.pass_rate:.1f}%)
Failed: {s.failed} | Skipped: {s.skipped}
Duration: {s.duration:.1f}s
Context: {context or 'General regression run'}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Failures ({len(s.failures)}):
{json.dumps(s.failures[:5], indent=2) if s.failures else 'None'}

Generate a complete {audience.value} report in {fmt.value} format."""


if __name__ == "__main__":
    reporter = NLPTestReporter()

    summary = TestSummary(
        suite="Predict360 GRC — Compliance Module",
        total=150, passed=142, failed=5, skipped=3,
        duration=245.3,
        failures=[
            {"test": "testCreateComplianceAlert", "message": "Timeout after 30s", "details": "Element not found"},
            {"test": "testExportToCsv", "message": "500 Internal Server Error", "details": "Download failed"},
        ]
    )

    for audience in ReportAudience:
        print(f"\n{'='*60}")
        print(f"REPORT FOR: {audience.value.upper()}")
        print('='*60)
        report = reporter.generate_report(summary, audience, context="Sprint 42 Regression")
        print(report)
