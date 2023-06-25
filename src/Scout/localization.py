""" This module contains the i18n and l10n logic for Scout.

This module contains the two classes we use to glue together discord.py and `fluent.runtime` so we can translate
responses and the like with Scout.
"""
import pathlib
from collections.abc import Sequence, MutableMapping, Callable, Mapping
from typing import Optional, Any, cast, Generator, Iterable, Self

from discord import Locale
from discord.app_commands import locale_str, Translator, TranslationContextTypes, TranslationContext, \
    TranslationContextLocation, TranslationError
from fluent.runtime import FluentBundle, AbstractResourceLoader
from fluent.runtime.types import FluentType
from fluent.syntax import FluentParser
from fluent.syntax.ast import Resource


class ScoutResourceLoader(AbstractResourceLoader):
    """A Personality-Aware FluentResourceLoader Implementation"""
    base_path: str
    personality: str = ""

    def __init__(self, base_path: str):
        """
        Create a resource loader. The roots may be a string for a single
        location on disk, or a list of strings.
        """
        self.base_path = base_path

    def supported_locales(self) -> Generator[str, None, None]:
        return (d.name for d in pathlib.Path(self.base_path
                                             .split("{locale}")[0][:-1]
                                             .format(personality=self.personality)
                                             ).iterdir())

    def resources(self, locale: str, resource_ids: Sequence[str]) -> Sequence['Resource']:
        base_path = self.base_path.format(locale=locale, personality=self.personality)
        resources = []

        for resource_id in resource_ids:
            path = pathlib.Path(base_path).joinpath(resource_id)
            if not path.is_file():
                continue
            with open(path, 'r', encoding='utf-8') as f:
                resources.append(FluentParser().parse(f.read()))

        if resources:
            return resources


class PersonalityBundle:
    """ A bundle implementation that supports personalities. """
    personality: str
    _locales: MutableMapping[str, FluentBundle]

    def __init__(self, personality: str, loader: ScoutResourceLoader, resource_ids: Sequence[str], bundle_class,
                 *args, **kwargs):
        self.personality = personality
        self._locales = {}
        self._create_bundles(loader, bundle_class, resource_ids, *args, **kwargs)

    def supports(self, locale: str) -> bool:
        return locale in self._locales.keys()

    def supported_locales(self) -> Iterable[str]:
        return self._locales.keys()

    def has_message(self, locale: str, msg_id: str):
        return self._locales[locale].has_message(msg_id)

    def get_message(self, locale: str, msg_id: str):
        return self._locales[locale].get_message(msg_id)

    def format_pattern(self, locale: str, *args, **kwargs):
        return self._locales[locale].format_pattern(*args, **kwargs)

    def _create_bundles(self, loader: ScoutResourceLoader, bundle_class, resource_ids: Sequence[str], *args, **kwargs):
        loader.personality = self.personality
        for locale in loader.supported_locales():
            resources = loader.resources(locale, resource_ids)
            bundle = bundle_class([locale], *args, **kwargs)
            for resource in resources:
                bundle.add_resource(resource)
            self._locales[locale] = bundle


class FluentScout:
    """ This handles the interactions with Project Fluent/Fluent.Runtime and the discord.py translation features.

    Attributes:
            fallback_locale (str): The locale to use if the default locale has no information.
    """
    fallback_locale: str
    fallback_personality: str
    _allowed_personalities: Iterable[str]
    _personalities: MutableMapping[str, PersonalityBundle]
    resource_loader: ScoutResourceLoader

    def __init__(self,
                 supported_personalities: Sequence[str],
                 resource_ids: Sequence[str],
                 resource_loader: ScoutResourceLoader,
                 fallback_personality: str = "scout", fallback_locale: Optional[str] = None,
                 bundle_class: type[FluentBundle] = FluentBundle,
                 functions: Optional[Mapping[str, Callable[[Any], FluentType]]] = None,
                 use_isolating: bool = False
                 ):
        """ Initializes FluentScout with the additional options necessary for our operation.

        Args:
            fallback_locale: The locale to use if the default locale has no information
            fallback_personality: The personality to fall back to if the locale isn't supported.
        """
        self.resource_loader = resource_loader
        self.use_isolating = use_isolating
        self.functions = functions
        self.bundle_class = bundle_class
        self.resource_ids = resource_ids
        self.fallback_locale = fallback_locale
        self._personalities = {}
        self.fallback_personality = fallback_personality
        self._allowed_personalities = supported_personalities if supported_personalities is not None else ["scout"]
        self._setup_bundles()

    def format_value(self, msg_id: str, args: Optional[dict[str, Any]] = None,
                     *, locale: str = None, personality: str = None) -> Optional[str]:
        """Gets the translated message from the message_id and also adds in any additional information/arguments for it.

        Args:
            msg_id: The message-id in the .ftl file to use
            args: The additional arguments to pass to the message to fill variables and the like.
            locale: The locale to use, if not provided it will use the fallback_locale
            personality: The personality to use for the message.

        Returns:
            The translated and filled message from the .ftl file for the specified or fallback locale. If no translation
            is found it will return none.
        """
        if personality is None or locale is None:
            raise TranslationError(context=TranslationContext(location=TranslationContextLocation.other,
                                                              data="Translation is messed up."))

        supported = self._personalities[personality].supports(locale)
        supported = supported and self._personalities[personality].has_message(locale, msg_id)
        if supported:
            msg = self._personalities[personality].get_message(locale, msg_id)
            val, _errors = self._personalities[personality].format_pattern(locale, msg.value, args)
            return cast(str, val)

        supported = self._personalities[self.fallback_personality].supports(locale)
        supported = supported and self._personalities[self.fallback_personality].has_message(locale, msg_id)
        if supported:
            msg = self._personalities[self.fallback_personality].get_message(locale, msg_id)
            val, _errors = self._personalities[self.fallback_personality].format_pattern(locale, msg.value, args)
            return cast(str, val)

        supported = self._personalities[personality].supports(self.fallback_locale)
        supported = supported and self._personalities[personality].has_message(self.fallback_locale, msg_id)
        if supported:
            msg = self._personalities[personality].get_message(self.fallback_locale, msg_id)
            val, _errors = self._personalities[personality].format_pattern(self.fallback_locale, msg.value, args)
            return cast(str, val)

        supported = self._personalities[self.fallback_personality].supports(self.fallback_locale)
        supported = supported and self._personalities[self.fallback_personality].has_message(self.fallback_locale,
                                                                                             msg_id)
        if supported:
            msg = self._personalities[self.fallback_personality].get_message(self.fallback_locale, msg_id)
            val, _errors = self._personalities[self.fallback_personality].format_pattern(self.fallback_locale,
                                                                                         msg.value, args)
            return cast(str, val)

        return None

    def _setup_bundles(self):
        for personality in self._allowed_personalities:
            self._personalities[personality] = PersonalityBundle(personality,
                                                                 self.resource_loader,
                                                                 self.resource_ids,
                                                                 self.bundle_class,
                                                                 functions=self.functions,
                                                                 use_isolating=self.use_isolating)


class ScoutTranslator(Translator):
    """The discord.py Translator implementation for scout that bridges the rest of the functionality we need."""
    _localization: FluentScout
    _personality: str

    def __init__(self, personality):
        self._personality = personality

    async def load(self):
        """This will do the loading of the translation information.

        This is required by Translator for this to work.
        """
        loader = ScoutResourceLoader("translations/{personality}/{locale}")
        self._localization = FluentScout([d.name for d in pathlib.Path("translations").iterdir()],
                                         ["commands.ftl", "responses.ftl"], loader,
                                         fallback_locale='en-US')

    async def unload(self):
        """This will unload any of the translation files that was loaded that needs to be unloaded by the class itself.

        This is required by Translator for this to work.
        """
        pass

    def set_personality(self, personality: str) -> Self:
        self._personality = personality
        return self

    @staticmethod
    def _locale_generator() -> Generator[str, Any, Any]:
        return (d.name for d in pathlib.Path("translations").iterdir())

    async def translate(self, string: locale_str, locale: Locale, context: TranslationContextTypes,
                        *, personality: Optional[str] = None) -> Optional[str]:
        """Translates the given string with the additional information into the version for the locale provided.

        Arguments:
            string: The locale_str to translate.
            locale: The locale to use to translate the string.
            context: The additional translation context to provide.
            personality: The personality to use, if not passed, it will just use the set personality.

        Returns:
            The string for the translated message, if it is not found it will return None.

        Raises:
            TranslationError: TranslationError is thrown if an error is encountered.
        """
        if "…" in string.message:
            return "…"
        personality = personality if personality is not None else self._personality
        return self._localization.format_value(string.message, locale=str(locale), personality=personality,
                                               args=string.extras)

    async def translate_response(self, string: str, locale: Optional[Locale] = None, personality: Optional[str] = None,
                                 **kwargs) -> Optional[str]:
        """Translates the given string for a Discord message response.

        Arguments:
            string: The string message-id to translate.
            locale: The locale to use for the string, if not provided it will use the fallback locale.
            personality: The personality to use.
            **kwargs: The additional information for the translation string for any variables in the string.

        Returns:
            The string for the translated message, if it is not found it will return None.

        Raises:
            TranslationError: TranslationError is thrown if an error is encountered.
        """
        lstr = locale_str(string, **kwargs)
        context = TranslationContext(TranslationContextLocation.other, None)
        return await self.translate(lstr, locale, context, personality=personality)
