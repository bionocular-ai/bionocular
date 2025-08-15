"""Tests for the core module."""

from app.core import Application, create_app


class TestApplication:
    """Test cases for Application class."""

    def test_application_creation(self) -> None:
        """Test creating an Application instance."""
        app = Application()

        assert app.name == "Bionocular"
        assert app.version == "0.1.0"
        assert app.is_healthy() is True

    def test_application_with_custom_name(self) -> None:
        """Test creating an Application with custom name."""
        app = Application(name="CustomApp")

        assert app.name == "CustomApp"
        assert app.version == "0.1.0"

    def test_get_info(self) -> None:
        """Test getting application information."""
        app = Application()
        info = app.get_info()

        expected_keys = ["name", "version", "description"]
        for key in expected_keys:
            assert key in info

        assert info["name"] == "Bionocular"
        assert info["version"] == "0.1.0"
        assert "melanoma treatments" in info["description"]


class TestFactoryFunction:
    """Test cases for the create_app factory function."""

    def test_create_app_default(self) -> None:
        """Test create_app with default parameters."""
        app = create_app()

        assert isinstance(app, Application)
        assert app.name == "Bionocular"

    def test_create_app_custom_name(self) -> None:
        """Test create_app with custom name."""
        app = create_app(name="TestApp")

        assert isinstance(app, Application)
        assert app.name == "TestApp"


class TestIntegration:
    """Integration test cases."""

    def test_basic_workflow(self) -> None:
        """Test basic application workflow."""
        # Create application
        app = create_app()

        # Verify it's working
        assert app.is_healthy() is True

        # Get info
        info = app.get_info()
        assert info["name"] == "Bionocular"
        assert info["version"] == "0.1.0"
