"""Attribute validation implementation.

This module implements validation logic for extracted attributes
using the validation rules from the database.
"""

import logging
import re
from typing import Any, Optional

from ..domain.extraction_interfaces import AttributeValidator
from ..domain.extraction_models import (
    AttributeType,
    ExtractedAttribute,
    ValidationRule,
    ValidationStatus,
)

logger = logging.getLogger(__name__)


class AttributeValidatorImpl(AttributeValidator):
    """Implementation of attribute validator using validation rules.

    This validator applies business rules to validate extracted
    attributes and updates their validation status.
    """

    def __init__(self):
        """Initialize attribute validator."""
        self.custom_validators = self._initialize_custom_validators()
        logger.info("Attribute validator initialized")

    def validate(
        self, attribute: ExtractedAttribute, attribute_type: AttributeType
    ) -> ExtractedAttribute:
        """Simple validation method for demos.

        Args:
            attribute: Attribute to validate
            attribute_type: Type of attribute

        Returns:
            Validated attribute (basic validation for demos)
        """
        try:
            logger.info(f"Validating {attribute_type} with simple validation")

            # Basic validation - just update status
            if attribute.value and attribute.value != "N/A":
                attribute.validation_status = ValidationStatus.VALID
                logger.info(f"Attribute {attribute_type} validated successfully")
            else:
                attribute.validation_status = ValidationStatus.INVALID
                logger.info(f"Attribute {attribute_type} not found")

            return attribute

        except Exception as e:
            logger.error(f"Simple validation failed for {attribute_type}: {e}")
            attribute.validation_status = ValidationStatus.INVALID
            return attribute

    async def validate_attribute(
        self, attribute: ExtractedAttribute, validation_rules: list[ValidationRule]
    ) -> ExtractedAttribute:
        """Validate an extracted attribute.

        Args:
            attribute: Attribute to validate
            validation_rules: Rules to apply for validation

        Returns:
            Validated attribute with updated status
        """
        try:
            logger.info(
                f"Validating {attribute.attribute_type} with {len(validation_rules)} rules"
            )

            validation_errors = []
            validation_status = ValidationStatus.VALID

            # Apply each validation rule
            for rule in validation_rules:
                rule_errors = await self._apply_validation_rule(attribute, rule)
                validation_errors.extend(rule_errors)

            # Determine overall validation status
            if validation_errors:
                if any("critical" in error.lower() for error in validation_errors):
                    validation_status = ValidationStatus.INVALID
                else:
                    validation_status = ValidationStatus.WARNING

            # Update attribute with validation results
            attribute.validation_status = validation_status
            attribute.validation_errors = validation_errors

            logger.info(
                f"Validation completed for {attribute.attribute_type}: {validation_status}"
            )
            return attribute

        except Exception as e:
            logger.error(f"Validation failed for {attribute.attribute_type}: {e}")
            # Mark as invalid if validation fails
            attribute.validation_status = ValidationStatus.INVALID
            attribute.validation_errors = [f"Validation error: {str(e)}"]
            return attribute

    async def _apply_validation_rule(
        self, attribute: ExtractedAttribute, rule: ValidationRule
    ) -> list[str]:
        """Apply a single validation rule to an attribute.

        Args:
            attribute: Attribute to validate
            rule: Validation rule to apply

        Returns:
            List of validation errors
        """
        errors = []

        try:
            # Check if attribute is required
            if rule.required and (attribute.value is None or attribute.value == ""):
                errors.append(
                    f"{attribute.attribute_type.value} is required but not found"
                )
                return errors

            # Skip other validations if value is empty and not required
            if attribute.value is None or attribute.value == "":
                return errors

            # Pattern validation
            if rule.pattern:
                if not self._validate_pattern(attribute.value, rule.pattern):
                    errors.append(
                        f"{attribute.attribute_type.value} does not match required pattern"
                    )

            # Numeric range validation
            if rule.min_value is not None or rule.max_value is not None:
                if not self._validate_numeric_range(
                    attribute.value, rule.min_value, rule.max_value
                ):
                    min_str = f"≥{rule.min_value}" if rule.min_value else ""
                    max_str = f"≤{rule.max_value}" if rule.max_value else ""
                    range_str = f"{min_str}{max_str}".replace("≥", "").replace("≤", "")
                    errors.append(
                        f"{attribute.attribute_type.value} must be in range {range_str}"
                    )

            # Allowed values validation
            if rule.allowed_values:
                if not self._validate_allowed_values(
                    attribute.value, rule.allowed_values
                ):
                    allowed_str = ", ".join(rule.allowed_values)
                    errors.append(
                        f"{attribute.attribute_type.value} must be one of: {allowed_str}"
                    )

            # Custom validator
            if (
                rule.custom_validator
                and rule.custom_validator in self.custom_validators
            ):
                custom_errors = await self.custom_validators[rule.custom_validator](
                    attribute
                )
                errors.extend(custom_errors)

        except Exception as e:
            errors.append(f"Validation rule error: {str(e)}")

        return errors

    def _validate_pattern(self, value: Any, pattern: str) -> bool:
        """Validate value against regex pattern.

        Args:
            value: Value to validate
            pattern: Regex pattern

        Returns:
            True if pattern matches
        """
        try:
            if not isinstance(value, str):
                value = str(value)
            return bool(re.match(pattern, value))
        except Exception:
            return False

    def _validate_numeric_range(
        self, value: Any, min_value: Optional[float], max_value: Optional[float]
    ) -> bool:
        """Validate numeric value is within range.

        Args:
            value: Value to validate
            min_value: Minimum allowed value
            max_value: Maximum allowed value

        Returns:
            True if value is within range
        """
        try:
            if isinstance(value, str):
                # Try to convert to float
                numeric_value = float(value)
            else:
                numeric_value = float(value)

            if min_value is not None and numeric_value < min_value:
                return False
            if max_value is not None and numeric_value > max_value:
                return False

            return True
        except (ValueError, TypeError):
            return False

    def _validate_allowed_values(self, value: Any, allowed_values: list[str]) -> bool:
        """Validate value is in allowed values list.

        Args:
            value: Value to validate
            allowed_values: List of allowed values

        Returns:
            True if value is allowed
        """
        try:
            if isinstance(value, str):
                return value in allowed_values
            else:
                return str(value) in allowed_values
        except Exception:
            return False

    def _initialize_custom_validators(self) -> dict[str, callable]:
        """Initialize custom validation functions.

        Returns:
            Dictionary of custom validator functions
        """
        return {
            "validate_nct_format": self._validate_nct_format,
            "validate_percentage": self._validate_percentage,
            "validate_p_value": self._validate_p_value,
            "validate_drug_name": self._validate_drug_name,
        }

    async def _validate_nct_format(self, attribute: ExtractedAttribute) -> list[str]:
        """Custom validator for NCT number format.

        Args:
            attribute: Attribute to validate

        Returns:
            List of validation errors
        """
        errors = []

        if attribute.value and isinstance(attribute.value, str):
            if not re.match(r"^NCT\d{8}$", attribute.value):
                errors.append("NCT number must be in format NCT########")

        return errors

    async def _validate_percentage(self, attribute: ExtractedAttribute) -> list[str]:
        """Custom validator for percentage values.

        Args:
            attribute: Attribute to validate

        Returns:
            List of validation errors
        """
        errors = []

        if attribute.value is not None:
            try:
                if isinstance(attribute.value, str):
                    percentage = float(attribute.value)
                else:
                    percentage = float(attribute.value)

                if not 0 <= percentage <= 100:
                    errors.append("Percentage must be between 0 and 100")
            except (ValueError, TypeError):
                errors.append("Percentage must be a valid number")

        return errors

    async def _validate_p_value(self, attribute: ExtractedAttribute) -> list[str]:
        """Custom validator for p-values.

        Args:
            attribute: Attribute to validate

        Returns:
            List of validation errors
        """
        errors = []

        if attribute.value is not None:
            if isinstance(attribute.value, str):
                if attribute.value not in [
                    "Non-Significant",
                    "Significant",
                    "Highly Significant",
                ]:
                    errors.append("P-value must be numeric or valid significance level")
            else:
                try:
                    p_value = float(attribute.value)
                    if not 0 <= p_value <= 1:
                        errors.append("P-value must be between 0 and 1")
                except (ValueError, TypeError):
                    errors.append("P-value must be a valid number")

        return errors

    async def _validate_drug_name(self, attribute: ExtractedAttribute) -> list[str]:
        """Custom validator for drug names.

        Args:
            attribute: Attribute to validate

        Returns:
            List of validation errors
        """
        errors = []

        if attribute.value and isinstance(attribute.value, str):
            # Check for common drug name patterns
            if len(attribute.value.strip()) < 2:
                errors.append("Drug name must be at least 2 characters")

            # Check for invalid characters
            if re.search(r"[<>{}[\]\\|`~]", attribute.value):
                errors.append("Drug name contains invalid characters")

        return errors
