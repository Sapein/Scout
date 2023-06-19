import pathlib
from typing import Optional, Generator, Union, Any, cast

from discord.app_commands import locale_str, Translator, TranslationContextTypes
from discord import Locale
from fluent.runtime import FluentLocalization, FluentResourceLoader, FluentBundle


class FluentScout(FluentLocalization):
    """
    This is a custom implementation of the FluentLocalization Class to allow us to use a specific language.
    """
    fallback_locale: str
    _locale_bundles: dict[str, FluentBundle]
    _error_on_missing: bool

    def __init__(self, *args, fallback_locale: Optional[str] = None, error_on_missing = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fallback_locale = fallback_locale
        self._locale_bundles = {}
        self._setup_bundles()
        self._error_on_missing = False

    def format_value(self, msg_id: str, args: Optional[dict[str, Any]] = None, *, locale: Optional[str] = None) -> str:
        locale = locale if locale is not None else self.fallback_locale
        locale_is_fallback = locale == self.fallback_locale
        if locale not in self._locale_bundles or not self._locale_bundles[locale].has_message(msg_id):
            if self._error_on_missing:
                raise NotImplementedError("Can not find msg_id {} in fallback locale or requested locale".format(msg_id))
            if self.fallback_locale is None or locale_is_fallback or not self._locale_bundles[self.fallback_locale].has_message(msg_id):
                return msg_id
            locale = self.fallback_locale
        msg = self._locale_bundles[locale].get_message(msg_id)
        if not msg.value:
            raise NotImplementedError("msg.value is none!")
        val, _errors = self._locale_bundles[locale].format_pattern(msg.value, args)
        return cast(str, val)

    def _setup_bundles(self):
        for locale in self.locales:
            for resources in self.resource_loader.resources(locale, self.resource_ids):
                bundle = self.bundle_class([locale], functions=self.functions, use_isolating=self.use_isolating)
                for resource in resources:
                    bundle.add_resource(resource)
                self._locale_bundles[locale] = bundle


class ScoutTranslator(Translator):
    """ The Base translator for Scout."""
    _localization: FluentScout | FluentLocalization

    async def load(self):
        loader = FluentResourceLoader("translations/{locale}")
        discord_locales = dict(Locale).values()
        extra_locales = (d.name for d in pathlib.Path("translations").iterdir() if d.name not in discord_locales)
        self._localization = FluentScout([*discord_locales, *extra_locales],
                                         ["main.ftl", "commands.ftl", "responses.ftl"], loader,
                                         fallback_locale='en-US')

    async def unload(self):
        pass

    def translate_response(self, string: str, locale: Optional[Locale] = None, **kwargs) -> Optional[str]:
        return self._localization.format_value(string, args=kwargs, locale=locale)

    async def translate(self, string: locale_str, locale: Locale, context: TranslationContextTypes) -> Optional[str]:
        if "…" in string.message:
            return "…"
        return self._localization.format_value(string.message, locale=str(locale))
