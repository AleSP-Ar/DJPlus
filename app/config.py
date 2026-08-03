"""Configuration compatibility facade for the canonical SettingsService API."""

from .services.settings_service import AppSettingsDTO, SettingsService

__all__ = ["AppSettingsDTO", "SettingsService"]
