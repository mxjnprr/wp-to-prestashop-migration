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
        raise ValueError(f"Fichier de configuration introuvable : {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not raw:
        raise ValueError("Le fichier de configuration est vide.")

    # Validate required sections
    for section in ["wordpress", "prestashop"]:
        if section not in raw:
            raise ValueError(f"Section '{section}' manquante dans la configuration.")

    # Build WordPress config
    wp_raw = raw["wordpress"]
    if not wp_raw.get("url"):
        raise ValueError("wordpress.url est requis — configurez l'URL WordPress.")
    wp_config = WordPressConfig(
        url=wp_raw["url"],
        username=wp_raw.get("username", ""),
        app_password=wp_raw.get("app_password", ""),
    )

    # Build PrestaShop config
    ps_raw = raw["prestashop"]
    if not ps_raw.get("url"):
        raise ValueError("prestashop.url est requis — configurez l'URL PrestaShop.")
    if not ps_raw.get("api_key"):
        raise ValueError("prestashop.api_key est requis — configurez la clé API PrestaShop.")
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
