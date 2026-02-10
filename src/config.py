"""
Configuration loader for the WP→PrestaShop migration tool.
Reads and validates a YAML configuration file.
"""

import os
import sys
from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class WordPressConfig:
    url: str
    username: str = ""
    app_password: str = ""

    @property
    def has_auth(self) -> bool:
        return bool(self.username and self.app_password)

    @property
    def api_base(self) -> str:
        return f"{self.url.rstrip('/')}/wp-json/wp/v2"


@dataclass
class PrestaShopConfig:
    url: str
    api_key: str
    default_lang_id: int = 1
    cms_category_id: int = 1

    @property
    def api_base(self) -> str:
        return f"{self.url.rstrip('/')}/api"


@dataclass
class MigrationConfig:
    dry_run: bool = False
    log_file: str = "migration.log"
    download_images: bool = True
    image_temp_dir: str = "temp_images"
    image_target_dir: str = ""


@dataclass
class MappingConfig:
    """Raw mapping configuration — parsed by MigrationRouter."""
    rules: list = field(default_factory=list)
    default: str = "skip"


@dataclass
class AppConfig:
    wordpress: WordPressConfig
    prestashop: PrestaShopConfig
    migration: MigrationConfig
    mapping: MappingConfig = field(default_factory=MappingConfig)


def load_config(config_path: str) -> AppConfig:
    """Load and validate configuration from a YAML file."""
    if not os.path.exists(config_path):
        print(f"❌ Configuration file not found: {config_path}")
        print("   Copy config.example.yaml to config.yaml and fill in your values.")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not raw:
        print("❌ Configuration file is empty.")
        sys.exit(1)

    # Validate required sections
    for section in ["wordpress", "prestashop"]:
        if section not in raw:
            print(f"❌ Missing required section '{section}' in config.")
            sys.exit(1)

    # Build WordPress config
    wp_raw = raw["wordpress"]
    if not wp_raw.get("url"):
        print("❌ wordpress.url is required.")
        sys.exit(1)
    wp_config = WordPressConfig(
        url=wp_raw["url"],
        username=wp_raw.get("username", ""),
        app_password=wp_raw.get("app_password", ""),
    )

    # Build PrestaShop config
    ps_raw = raw["prestashop"]
    if not ps_raw.get("url"):
        print("❌ prestashop.url is required.")
        sys.exit(1)
    if not ps_raw.get("api_key"):
        print("❌ prestashop.api_key is required.")
        sys.exit(1)
    ps_config = PrestaShopConfig(
        url=ps_raw["url"],
        api_key=ps_raw["api_key"],
        default_lang_id=ps_raw.get("default_lang_id", 1),
        cms_category_id=ps_raw.get("cms_category_id", 1),
    )

    # Build Migration config
    mig_raw = raw.get("migration", {})
    mig_config = MigrationConfig(
        dry_run=mig_raw.get("dry_run", False),
        log_file=mig_raw.get("log_file", "migration.log"),
        download_images=mig_raw.get("download_images", True),
        image_temp_dir=mig_raw.get("image_temp_dir", "temp_images"),
        image_target_dir=mig_raw.get("image_target_dir", ""),
    )

    # Build Mapping config
    map_raw = raw.get("mapping", {})
    map_config = MappingConfig(
        rules=map_raw.get("rules", []),
        default=map_raw.get("default", "skip"),
    )

    return AppConfig(
        wordpress=wp_config,
        prestashop=ps_config,
        migration=mig_config,
        mapping=map_config,
    )
