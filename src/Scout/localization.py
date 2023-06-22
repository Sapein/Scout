""" This module contains the i18n and l10n logic for Scout.

This module contains the two classes we use to glue together discord.py and fluent.runtime so we can translate responses
and the like with Scout.
"""
import pathlib
from typing import Optional, Any, cast

from discord import Locale
from discord.app_commands import locale_str, Translator, TranslationContextTypes, TranslationContext, \
    TranslationContextLocation, TranslationError
from fluent.runtime import FluentLocalization, FluentResourceLoader, FluentBundle


class FluentScout(FluentLocalization):
    """ This handles the interactions with Project Fluent/Fluent.Runtime and the discord.py translation features.

    Attributes:
            fallback_locale (str): The locale to use if the default locale has no information.
    """
    fallback_locale: str
    _locale_bundles: dict[str, FluentBundle]
    _error_on_missing: bool

    def __init__(self, *args, fallback_locale: Optional[str] = None, error_on_missing=False, **kwargs):
        """ Initializes FluentScout with the additional options necessary for our operation.

        Args:
            fallback_locale: The locale to use if the default locale has no information
            error_on_missing: If this is set NotImplementedError will be thrown if there is no available translation
              for a message.
        """
        super().__init__(*args, **kwargs)
        self.fallback_locale = fallback_locale
        self._locale_bundles = {}
        self._setup_bundles()
        self._error_on_missing = False

    def format_value(self, msg_id: str, args: Optional[dict[str, Any]] = None,
                     *, locale: Optional[str] = None) -> Optional[str]:
        """Gets the translated message from the message_id and also adds in any additional information/arguments for it.

        Args:
            msg_id: The message-id in the .ftl file to use
            args: The additional arguments to pass to the message to fill variables and the like.
            locale: The locale to use, if not provided it will use the fallback_locale

        Returns:
            The translated and filled message from the .ftl file for the specified or fallback locale. If no translation
            is found and the user did not opt-into error on missing, then it will return None.

        Raises:
            TranslationError: If enabled, it will be thrown if msg-id is not found in the specified or fallback locale.
        """
        locale = locale if locale is not None else self.fallback_locale
        locale_is_fallback = locale == self.fallback_locale
        if locale not in self._locale_bundles or not self._locale_bundles[locale].has_message(msg_id):
            if self._error_on_missing:
                raise TranslationError(
                    "Can not find msg_id {} in fallback locale or requested locale".format(msg_id))

            notfound = self.fallback_locale is None or locale_is_fallback
            notfound = notfound or self._locale_bundles[self.fallback_locale].has_message(msg_id)
            if notfound:
                return None

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
    """The discord.py Translator implementation for scout that bridges the rest of the functionality we need."""
    _localization: FluentScout | FluentLocalization

    async def load(self):
        """This will do the loading of the translation information.

        This is required by Translator for this to work.
        """
        loader = FluentResourceLoader("translations/{locale}")
        discord_locales = dict(Locale).values()
        extra_locales = (d.name for d in pathlib.Path("translations").iterdir() if d.name not in discord_locales)
        self._localization = FluentScout([*discord_locales, *extra_locales],
                                         ["commands.ftl", "responses.ftl"], loader,
                                         fallback_locale='en-US')

    async def unload(self):
        """This will unload any of the translation files that was loaded that needs to be unloaded by the class itself.

        This is required by Translator for this to work.
        """
        pass

    async def translate(self, string: locale_str, locale: Locale, context: TranslationContextTypes) -> Optional[str]:
        """Translates the given string with the additional information into the version for the locale provided.

        Arguments:
            string: The locale_str to translate.
            locale: The locale to use to translate the string.
            context: The additional translation context to provide.

        Returns:
            The string for the translated message, if it is not found it will return None.

        Raises:
            TranslationError: TranslationError is thrown if an error is encountered.
        """
        if "…" in string.message:
            return "…"
        return self._localization.format_value(string.message, locale=str(locale), args=string.extras)

    async def translate_response(self, string: str, locale: Optional[Locale] = None, **kwargs) -> Optional[str]:
        """Translates the given string for a Discord message response.

        Arguments:
            string: The string message-id to translate.
            locale: The locale to use for the string, if not provided it will use the fallback locale.
            **kwargs: The additional information for the translation string for any variables in the string.

        Returns:
            The string for the translated message, if it is not found it will return None.

        Raises:
            TranslationError: TranslationError is thrown if an error is encountered.
        """
        lstr = locale_str(string, **kwargs)
        context = TranslationContext(TranslationContextLocation.other, None)
        return await self.translate(lstr, locale, context)
