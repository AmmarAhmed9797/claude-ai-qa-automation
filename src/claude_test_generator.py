"""
Claude AI Test Generator
Author: Muhammad Ammar Ahmed — Senior Test Automation Engineer

Generates production-ready test cases from natural language requirements
using Anthropic Claude claude-opus-4-6. Supports Cypress, Selenium, Playwright,
RestAssured and Postman formats.
"""

import anthropic
import json
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestFramework(Enum):
    CYPRESS     = "cypress"
    SELENIUM    = "selenium"
    PLAYWRIGHT  = "playwright"
    REST_ASSURED = "rest_assured"
    POSTMAN     = "postman"


class TestType(Enum):
    FUNCTIONAL   = "functional"
    REGRESSION   = "regression"
    SMOKE        = "smoke"
    API          = "api"
    E2E          = "e2e"
    PERFORMANCE  = "performance"
    SECURITY     = "security"


@dataclass
class GenerationConfig:
    framework:    TestFramework = TestFramework.CYPRESS
    test_type:    TestType      = TestType.FUNCTIONAL
    include_edge_cases: bool    = True
    include_negative:   bool    = True
    include_data_driven: bool   = False
    max_tests:    int           = 10
    language:     str           = "javascript"
    module:       str           = "general"


class ClaudeTestGenerator:
    """
    AI-powered test case generator using Anthropic Claude.
    Transforms plain English requirements into complete test suites.
    """

    MODEL = "claude-opus-4-6"
    MAX_TOKENS = 4096

    FRAMEWORK_INSTRUCTIONS = {
        TestFramework.CYPRESS: "Use Cypress with JavaScript. Include describe/it blocks, cy.get(), cy.visit(), .should() assertions, beforeEach hooks, and Page Object Model pattern.",
        TestFramework.SELENIUM: "Use Selenium WebDriver with Java. Include TestNG annotations, Page Object Model, explicit waits, and proper assertions.",
        TestFramework.PLAYWRIGHT: "Use Playwright with TypeScript. Include test.describe(), test(), expect() assertions, and fixtures.",
        TestFramework.REST_ASSURED: "Use REST Assured with Java. Include given/when/then BDD style, proper request specs, and response assertions.",
        TestFramework.POSTMAN: "Generate Postman Collection JSON with test scripts, environment variables, and pre-request scripts.",
    }

    def __init__(self, api_key: Optional[str] = None):
        self.client = anthropic.Anthropic(api_key=api_key)
        logger.info(f"ClaudeTestGenerator initialized with model: {self.MODEL}")

    def generate(self, requirement: str, config: Optional[GenerationConfig] = None) -> str:
        """
        Generate test cases from a natural language requirement.

        Args:
            requirement: Plain English description of feature/requirement
            config: Generation configuration options

        Returns:
            Complete test code as string
        """
        if config is None:
            config = GenerationConfig()

        prompt = self._build_prompt(requirement, config)
        logger.info(f"Generating {config.framework.value} tests for: {requirement[:80]}...")

        response = self.client.messages.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            system=self._system_prompt(config),
            messages=[{"role": "user", "content": prompt}]
        )

        generated = response.content[0].text
        logger.info(f"Generated {len(generated.splitlines())} lines of test code")
        return generated

    def generate_from_user_story(self, user_story: str, acceptance_criteria: list[str],
                                  config: Optional[GenerationConfig] = None) -> str:
        """Generate tests from Agile user story + acceptance criteria."""
        requirement = f"""
User Story: {user_story}

Acceptance Criteria:
{chr(10).join(f'- {c}' for c in acceptance_criteria)}
"""
        return self.generate(requirement, config)

    def generate_bdd_feature(self, feature_name: str, description: str) -> str:
        """Generate Gherkin BDD feature file from description."""
        response = self.client.messages.create(
            model=self.MODEL,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": f"""Generate a complete Gherkin BDD feature file for:
Feature: {feature_name}
Description: {description}

Include:
- Feature description
- Background (if applicable)
- At least 5 diverse Scenarios (happy path, edge cases, negative)
- Scenario Outlines with Examples tables where appropriate
- Clear Given/When/Then steps

Return ONLY the .feature file content."""
            }]
        )
        return response.content[0].text

    def generate_api_test_suite(self, api_spec: dict) -> str:
        """Generate comprehensive API test suite from OpenAPI/Swagger spec."""
        spec_json = json.dumps(api_spec, indent=2)
        response = self.client.messages.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            messages=[{
                "role": "user",
                "content": f"""Generate a complete REST Assured API test suite from this API spec:

{spec_json}

Include tests for:
- All endpoints (GET, POST, PUT, DELETE)
- Valid and invalid inputs
- Authentication scenarios
- Response schema validation
- Status code assertions
- Error handling

Use Java with REST Assured, TestNG, and proper test organization."""
            }]
        )
        return response.content[0].text

    def analyze_and_improve(self, existing_tests: str) -> str:
        """Analyze existing tests and suggest improvements."""
        response = self.client.messages.create(
            model=self.MODEL,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": f"""Analyze these existing tests and provide:
1. Issues and anti-patterns detected
2. Missing test scenarios
3. Improved version with fixes applied
4. Coverage gaps analysis

Existing Tests:
{existing_tests}"""
            }]
        )
        return response.content[0].text

    def _system_prompt(self, config: GenerationConfig) -> str:
        return f"""You are a world-class QA automation engineer with 10+ years of experience.
You specialize in {config.framework.value} test automation for enterprise applications.
Generate production-ready, clean, well-documented test code.
Framework instructions: {self.FRAMEWORK_INSTRUCTIONS[config.framework]}
Always follow best practices: DRY principle, meaningful test names, proper assertions."""

    def _build_prompt(self, requirement: str, config: GenerationConfig) -> str:
        parts = [f"Generate {config.test_type.value} tests for:\n{requirement}\n"]
        parts.append(f"\nRequirements:")
        parts.append(f"- Framework: {config.framework.value}")
        parts.append(f"- Max tests: {config.max_tests}")
        if config.include_edge_cases:
            parts.append("- Include edge case tests")
        if config.include_negative:
            parts.append("- Include negative/error scenario tests")
        if config.include_data_driven:
            parts.append("- Include data-driven tests with multiple datasets")
        parts.append(f"- Module/Context: {config.module}")
        parts.append("\nReturn ONLY the test code, no explanations.")
        return "\n".join(parts)


if __name__ == "__main__":
    gen = ClaudeTestGenerator()
    config = GenerationConfig(
        framework=TestFramework.CYPRESS,
        test_type=TestType.E2E,
        include_edge_cases=True,
        include_negative=True,
        module="Compliance Alerts"
    )
    tests = gen.generate(
        "User can create, view, filter and export compliance alerts in Predict360 GRC platform",
        config
    )
    print(tests)
