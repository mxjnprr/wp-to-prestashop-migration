"""
Migration router.
Determines where each WordPress page should go in PrestaShop:
  - "cms"     → CMS page
  - "product" → Product description update
  - "skip"    → Ignore
"""

import fnmatch
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("wp2presta")


@dataclass
class RouteResult:
    """Result of routing a WordPress page."""
    target: str  # "cms", "product", "skip"
    slug: str  # WP slug
    title: str  # WP title

    # CMS-specific
    cms_category_id: Optional[int] = None

    # Product-specific
    match_by: str = "name"  # "name", "reference", or "id"
    product_id: Optional[int] = None  # Direct PS product ID
    product_reference: Optional[str] = None  # PS product reference

    # Which rule matched
    rule_name: str = ""


@dataclass
class MappingRule:
    """A single routing rule from config."""
    target: str  # "cms", "product", "skip"
    slugs: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    cms_category_id: Optional[int] = None
    match_by: str = "name"  # for product target
    product_map: dict[str, Any] = field(default_factory=dict)  # slug → PS ref/id
    name: str = ""


class MigrationRouter:
    """Routes WordPress pages to their PrestaShop destination."""

    def __init__(self, rules: list[MappingRule], default: str = "skip"):
        self.rules = rules
        self.default = default

    def route(self, slug: str, title: str = "") -> RouteResult:
        """Determine the destination for a WordPress page."""
        for rule in self.rules:
            if self._matches(slug, rule):
                result = RouteResult(
                    target=rule.target,
                    slug=slug,
                    title=title,
                    rule_name=rule.name,
                )
                if rule.target == "cms":
                    result.cms_category_id = rule.cms_category_id
                elif rule.target == "product":
                    result.match_by = rule.match_by
                    # Check if there's a specific mapping for this slug
                    if slug in rule.product_map:
                        mapping = rule.product_map[slug]
                        if isinstance(mapping, int):
                            result.product_id = mapping
                            result.match_by = "id"
                        elif isinstance(mapping, str):
                            result.product_reference = mapping
                            result.match_by = "reference"
                return result

        # Default
        return RouteResult(
            target=self.default,
            slug=slug,
            title=title,
            rule_name="(default)",
        )

    def _matches(self, slug: str, rule: MappingRule) -> bool:
        """Check if a slug matches a rule."""
        # Exact match in slugs list
        if slug in rule.slugs:
            return True

        # Glob pattern match
        for pattern in rule.patterns:
            if fnmatch.fnmatch(slug, pattern):
                return True

        # Check product_map keys
        if rule.target == "product" and slug in rule.product_map:
            return True

        return False

    def get_summary(self) -> dict[str, int]:
        """Return summary of rules configured."""
        return {
            "total_rules": len(self.rules),
            "cms_rules": sum(1 for r in self.rules if r.target == "cms"),
            "product_rules": sum(1 for r in self.rules if r.target == "product"),
            "skip_rules": sum(1 for r in self.rules if r.target == "skip"),
            "default": self.default,
        }


def build_router_from_config(mapping_config: dict) -> MigrationRouter:
    """Build a MigrationRouter from the 'mapping' section of config.yaml."""
    rules_raw = mapping_config.get("rules", [])
    default = mapping_config.get("default", "skip")

    rules = []
    for i, rule_raw in enumerate(rules_raw):
        target = rule_raw.get("target", "skip")
        name = rule_raw.get("name", f"rule_{i}")

        rule = MappingRule(
            target=target,
            name=name,
            slugs=rule_raw.get("slugs", []),
            patterns=rule_raw.get("patterns", []),
            cms_category_id=rule_raw.get("cms_category_id"),
            match_by=rule_raw.get("match_by", "name"),
            product_map=rule_raw.get("product_map", {}),
        )
        rules.append(rule)
        logger.debug(
            f"Rule '{name}': {target} — "
            f"{len(rule.slugs)} slugs, {len(rule.patterns)} patterns"
        )

    logger.info(
        f"Router: {len(rules)} rules, default={default}"
    )
    return MigrationRouter(rules, default)
