"""Configuration loader for RAG query templates.

This module provides utilities to load and manage RAG query templates
from external configuration files, enabling easy customization without
code changes.
"""

import logging
from pathlib import Path

import yaml

from ..domain.extraction_models import AttributeType

logger = logging.getLogger(__name__)


class RAGConfigLoader:
    """Loads and manages RAG configuration from YAML files."""

    def __init__(self, config_path: str = None):
        """Initialize RAG config loader.

        Args:
            config_path: Path to YAML configuration file.
                        If None, uses default path.
        """
        if config_path is None:
            # YAML lives in domain/resources — domain owns the query vocabulary
            base_dir = Path(__file__).parent.parent.parent
            config_path = (
                base_dir / "src" / "domain" / "resources" / "rag_query_templates.yaml"
            )

        self.config_path = Path(config_path)
        self._query_templates: dict[AttributeType, list[str]] = {}

        # Load configuration
        self._load_config()

    def _load_config(self) -> None:
        """Load query templates from YAML configuration file."""
        try:
            if not self.config_path.exists():
                logger.warning(
                    "Config file not found at %s, using defaults", self.config_path
                )
                return

            with open(self.config_path) as f:
                config_data = yaml.safe_load(f)

            if not config_data:
                logger.warning("Empty configuration file")
                return

            # Parse configuration and map to AttributeType enum
            for key, queries in config_data.items():
                try:
                    # Convert key to AttributeType
                    attr_type = AttributeType(key)

                    # Validate queries
                    if isinstance(queries, list) and all(
                        isinstance(q, str) for q in queries
                    ):
                        self._query_templates[attr_type] = queries
                    else:
                        logger.warning("Invalid queries for %s: %s", key, queries)

                except ValueError:
                    logger.debug("Skipping unknown attribute type: %s", key)
                    continue

            logger.info(
                "Loaded query templates for %d attribute types from %s",
                len(self._query_templates),
                self.config_path,
            )

        except Exception as e:
            logger.error("Failed to load RAG configuration: %s", e)

    def get_query_templates(self, attribute_type: AttributeType) -> list[str]:
        """Get query templates for an attribute type.

        Args:
            attribute_type: Type of attribute

        Returns:
            List of query template strings
        """
        return self._query_templates.get(attribute_type, [])

    def get_all_templates(self) -> dict[AttributeType, list[str]]:
        """Get all query templates.

        Returns:
            Dictionary mapping attribute types to query templates
        """
        return self._query_templates.copy()

    def reload_config(self) -> None:
        """Reload configuration from file.

        This allows dynamic updates to query templates without
        restarting the application.
        """
        self._query_templates.clear()
        self._load_config()
        logger.info("Configuration reloaded")

    def has_templates_for(self, attribute_type: AttributeType) -> bool:
        """Check if templates exist for an attribute type.

        Args:
            attribute_type: Type of attribute

        Returns:
            True if templates exist, False otherwise
        """
        return attribute_type in self._query_templates

    def get_template_count(self) -> int:
        """Get total number of configured attribute types.

        Returns:
            Number of attribute types with templates
        """
        return len(self._query_templates)
