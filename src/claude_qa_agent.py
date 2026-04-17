"""
Claude Autonomous QA Agent
Author: Muhammad Ammar Ahmed — Senior Test Automation Engineer

An autonomous AI agent that independently browses applications,
discovers test scenarios, executes them, and generates bug reports.
Uses Claude claude-opus-4-6 with tool use for browser automation.
"""

import anthropic
import base64
import json
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BugReport:
    title: str
    severity: str
    description: str
    steps_to_reproduce: list[str]
    expected: str
    actual: str
    url: str
    screenshot_path: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AgentSession:
    url: str
    module: str
    bugs_found: list[BugReport] = field(default_factory=list)
    scenarios_tested: list[str] = field(default_factory=list)
    pages_visited: list[str] = field(default_factory=list)
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())


class ClaudeQAAgent:
    """
    Autonomous QA agent powered by Claude claude-opus-4-6.
    Independently explores web applications to find bugs and generate test reports.
    """

    MODEL = "claude-opus-4-6"

    TOOLS = [
        {
            "name": "take_screenshot",
            "description": "Capture the current browser screen for analysis",
            "input_schema": {"type": "object", "properties": {}, "required": []}
        },
        {
            "name": "navigate_to",
            "description": "Navigate browser to a URL",
            "input_schema": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "URL to navigate to"}},
                "required": ["url"]
            }
        },
        {
            "name": "click_element",
            "description": "Click an element on the page",
            "input_schema": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector or XPath"},
                    "selector_type": {"type": "string", "enum": ["css", "xpath", "text"]}
                },
                "required": ["selector"]
            }
        },
        {
            "name": "type_text",
            "description": "Type text into an input field",
            "input_schema": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string"},
                    "text": {"type": "string"}
                },
                "required": ["selector", "text"]
            }
        },
        {
            "name": "report_bug",
            "description": "Report a discovered bug or issue",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                    "description": {"type": "string"},
                    "steps": {"type": "array", "items": {"type": "string"}},
                    "expected": {"type": "string"},
                    "actual": {"type": "string"}
                },
                "required": ["title", "severity", "description", "steps", "expected", "actual"]
            }
        },
        {
            "name": "get_page_content",
            "description": "Get the current page HTML and visible text",
            "input_schema": {"type": "object", "properties": {}, "required": []}
        }
    ]

    def __init__(self, api_key: Optional[str] = None, headless: bool = True):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.driver = self._init_driver(headless)
        self.wait = WebDriverWait(self.driver, 10)
        self.session: Optional[AgentSession] = None
        logger.info("ClaudeQAAgent initialized")

    def _init_driver(self, headless: bool) -> webdriver.Chrome:
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        return webdriver.Chrome(options=options)

    def explore(self, url: str, module: str = "general",
                 max_iterations: int = 20) -> AgentSession:
        """
        Autonomously explore an application to find bugs.

        Args:
            url: Starting URL for exploration
            module: Module/feature being tested
            max_iterations: Max agent action steps

        Returns:
            AgentSession with all findings
        """
        self.session = AgentSession(url=url, module=module)
        self.driver.get(url)
        logger.info(f"Agent starting exploration of: {url} (module: {module})")

        system = f"""You are an expert QA engineer autonomously testing a web application.
Your mission: explore the {module} module at {url}, find bugs, and test edge cases.

Strategy:
1. Start by taking a screenshot to understand the current state
2. Navigate through features systematically
3. Test positive flows, edge cases, and negative scenarios
4. Report any bugs or unexpected behavior immediately
5. Check for: broken links, UI glitches, validation errors, missing data

Be thorough. A real user would interact with all visible elements."""

        messages = [{"role": "user", "content": f"Start exploring: {url}. Module: {module}. Find bugs!"}]

        for i in range(max_iterations):
            logger.info(f"Agent iteration {i+1}/{max_iterations}")

            response = self.client.messages.create(
                model=self.MODEL,
                max_tokens=2048,
                system=system,
                tools=self.TOOLS,
                messages=messages
            )

            if response.stop_reason == "end_turn":
                logger.info("Agent completed exploration")
                break

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = self._execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result)
                    })

            messages.append({"role": "assistant", "content": response.content})
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

        logger.info(f"Exploration complete. Bugs found: {len(self.session.bugs_found)}")
        return self.session

    def _execute_tool(self, tool_name: str, tool_input: dict):
        """Execute a browser tool and return result."""
        try:
            if tool_name == "take_screenshot":
                screenshot = self.driver.get_screenshot_as_base64()
                return {"screenshot": screenshot[:100] + "...", "url": self.driver.current_url}

            elif tool_name == "navigate_to":
                url = tool_input["url"]
                self.driver.get(url)
                if self.session:
                    self.session.pages_visited.append(url)
                return {"status": "navigated", "url": url, "title": self.driver.title}

            elif tool_name == "click_element":
                selector = tool_input["selector"]
                stype = tool_input.get("selector_type", "css")
                by = By.CSS_SELECTOR if stype == "css" else By.XPATH if stype == "xpath" else By.LINK_TEXT
                el = self.wait.until(EC.element_to_be_clickable((by, selector)))
                el.click()
                return {"status": "clicked", "selector": selector}

            elif tool_name == "type_text":
                el = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, tool_input["selector"])))
                el.clear()
                el.send_keys(tool_input["text"])
                return {"status": "typed", "text": tool_input["text"]}

            elif tool_name == "report_bug":
                bug = BugReport(
                    title=tool_input["title"],
                    severity=tool_input["severity"],
                    description=tool_input["description"],
                    steps_to_reproduce=tool_input["steps"],
                    expected=tool_input["expected"],
                    actual=tool_input["actual"],
                    url=self.driver.current_url
                )
                if self.session:
                    self.session.bugs_found.append(bug)
                logger.warning(f"BUG [{bug.severity.upper()}]: {bug.title}")
                return {"status": "reported", "severity": bug.severity}

            elif tool_name == "get_page_content":
                body_text = self.driver.find_element(By.TAG_NAME, "body").text[:2000]
                return {"url": self.driver.current_url, "title": self.driver.title, "content": body_text}

        except Exception as e:
            return {"error": str(e), "tool": tool_name}

    def generate_report(self) -> str:
        """Generate a formatted bug report from the session."""
        if not self.session:
            return "No session data available."
        bugs = self.session.bugs_found
        report = [
            f"# 🤖 Claude QA Agent Report",
            f"**Module:** {self.session.module}",
            f"**URL:** {self.session.url}",
            f"**Date:** {self.session.start_time}",
            f"**Pages Visited:** {len(self.session.pages_visited)}",
            f"**Bugs Found:** {len(bugs)}",
            "---"
        ]
        for i, bug in enumerate(bugs, 1):
            report.extend([
                f"## Bug #{i}: {bug.title}",
                f"**Severity:** {bug.severity.upper()}",
                f"**Description:** {bug.description}",
                f"**Steps to Reproduce:**",
                *[f"  {j+1}. {s}" for j, s in enumerate(bug.steps_to_reproduce)],
                f"**Expected:** {bug.expected}",
                f"**Actual:** {bug.actual}",
                "---"
            ])
        return "\n".join(report)

    def close(self):
        self.driver.quit()
        logger.info("Agent session closed")


if __name__ == "__main__":
    agent = ClaudeQAAgent(headless=True)
    try:
        session = agent.explore(
            url="https://app.predict360.com",
            module="Compliance Alerts",
            max_iterations=15
        )
        print(agent.generate_report())
    finally:
        agent.close()
