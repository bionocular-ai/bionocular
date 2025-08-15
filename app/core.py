"""Core functionality for the Bionocular melanoma treatment analysis system."""

from typing import Any


class Application:
    """Main application class for Bionocular."""

    def __init__(self, name: str = "Bionocular") -> None:
        """Initialize the application."""
        self.name = name
        self.version = "0.1.0"

    def get_info(self) -> dict[str, Any]:
        """Get basic application information."""
        return {
            "name": self.name,
            "version": self.version,
            "description": "A Python backend for processing scientific PDFs about melanoma treatments",
        }

    def is_healthy(self) -> bool:
        """Check if the application is healthy."""
        return True


def create_app(name: str = "Bionocular") -> Application:
    """Factory function to create an application instance."""
    return Application(name=name)
