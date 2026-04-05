import logging
import os
import json
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN, CONF_DAYS, CONF_TV_IDS, CONF_SELECTION_MODE, CONF_LANGUAGES, CONF_PROVIDERS,
    SELECTION_MODE_LANGUAGE, SELECTION_MODE_PROVIDER, SELECTION_MODE_MANUAL,
    AVAILABLE_LANGUAGES, AVAILABLE_PROVIDERS, CHANNELS_PER_PAGE,
)

_LOGGER = logging.getLogger(__name__)


def load_channels():
    """Načte kanály z default_channels.json synchronně."""
    data_file = os.path.join(os.path.dirname(__file__), "default_channels.json")
    with open(data_file, "r", encoding="utf-8") as f:
        return json.load(f)


class EPGConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow pro EPG integraci."""

    VERSION = 1

    def __init__(self):
        self._all_channels = []
        self._filtered_channels = []
        self._selected_ids = set()
        self._current_page = 0
        self._days = 7

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EPGOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Krok 1: počet dní + režim výběru."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            self._days = user_input[CONF_DAYS]
            self._all_channels = await self.hass.async_add_executor_job(load_channels)
            mode = user_input[CONF_SELECTION_MODE]

            if mode == SELECTION_MODE_LANGUAGE:
                return await self.async_step_select_language()
            elif mode == SELECTION_MODE_PROVIDER:
                return await self.async_step_select_provider()
            else:
                self._filtered_channels = self._all_channels
                self._selected_ids = set()
                self._current_page = 0
                return await self.async_step_channel_page()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_DAYS, default=7): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=7)
                ),
                vol.Required(CONF_SELECTION_MODE, default=SELECTION_MODE_LANGUAGE): vol.In([
                    SELECTION_MODE_LANGUAGE,
                    SELECTION_MODE_PROVIDER,
                    SELECTION_MODE_MANUAL,
                ]),
            }),
        )

    async def async_step_select_language(self, user_input=None) -> FlowResult:
        """Krok 2A: výběr jazyků."""
        if user_input is not None:
            selected_langs = user_input.get(CONF_LANGUAGES, [])
            self._filtered_channels = [
                ch for ch in self._all_channels if ch["lang_code"] in selected_langs
            ]
            self._selected_ids = {ch["id"] for ch in self._filtered_channels}
            self._current_page = 0
            return await self.async_step_channel_page()

        return self.async_show_form(
            step_id="select_language",
            data_schema=vol.Schema({
                vol.Required(CONF_LANGUAGES, default=["CZ"]): cv.multi_select(
                    {lang: lang for lang in AVAILABLE_LANGUAGES}
                ),
            }),
        )

    async def async_step_select_provider(self, user_input=None) -> FlowResult:
        """Krok 2B: výběr providerů."""
        if user_input is not None:
            selected_providers = user_input.get(CONF_PROVIDERS, [])
            self._filtered_channels = [
                ch for ch in self._all_channels
                if any(p in ch.get("providers", []) for p in selected_providers)
            ]
            self._selected_ids = {ch["id"] for ch in self._filtered_channels}
            self._current_page = 0
            return await self.async_step_channel_page()

        return self.async_show_form(
            step_id="select_provider",
            data_schema=vol.Schema({
                vol.Required(CONF_PROVIDERS, default=["O2"]): cv.multi_select(
                    {p: p for p in AVAILABLE_PROVIDERS}
                ),
            }),
        )

    async def async_step_channel_page(self, user_input=None) -> FlowResult:
        """Krok 3: stránkovaný výběr kanálů."""
        if user_input is not None:
            page_selected = set(user_input.get(CONF_TV_IDS, []))
            page_all = {
                ch["id"]
                for ch in self._filtered_channels[
                    self._current_page * CHANNELS_PER_PAGE:
                    (self._current_page + 1) * CHANNELS_PER_PAGE
                ]
            }
            self._selected_ids -= page_all
            self._selected_ids |= page_selected
            self._current_page += 1

        total_pages = max(1, (len(self._filtered_channels) - 1) // CHANNELS_PER_PAGE + 1)
        start = self._current_page * CHANNELS_PER_PAGE
        page_channels = self._filtered_channels[start: start + CHANNELS_PER_PAGE]

        if not page_channels:
            return await self.async_step_confirm()

        page_dict = {ch["id"]: f"{ch['name']} ({ch['lang_code']})" for ch in page_channels}
        page_preselected = [ch["id"] for ch in page_channels if ch["id"] in self._selected_ids]

        return self.async_show_form(
            step_id="channel_page",
            data_schema=vol.Schema({
                vol.Optional(CONF_TV_IDS, default=page_preselected): cv.multi_select(page_dict),
            }),
            description_placeholders={
                "page": str(self._current_page + 1),
                "total": str(total_pages),
            },
        )

    async def async_step_confirm(self, user_input=None) -> FlowResult:
        """Krok 4: uložení."""
        return self.async_create_entry(
            title="EPG",
            data={
                CONF_TV_IDS: list(self._selected_ids),
                CONF_DAYS: self._days,
            },
        )


class EPGOptionsFlow(config_entries.OptionsFlow):
    """Options flow pro EPG integraci."""

    def __init__(self, config_entry):
        self._all_channels = []
        self._filtered_channels = []
        self._selected_ids = set(
            config_entry.options.get(CONF_TV_IDS,
            config_entry.data.get(CONF_TV_IDS, []))
        )
        self._current_page = 0
        self._days = config_entry.options.get(
            CONF_DAYS, config_entry.data.get(CONF_DAYS, 7)
        )
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Krok 1: počet dní + režim výběru."""
        if user_input is not None:
            self._days = user_input[CONF_DAYS]
            self._all_channels = await self.hass.async_add_executor_job(load_channels)
            mode = user_input[CONF_SELECTION_MODE]

            if mode == SELECTION_MODE_LANGUAGE:
                return await self.async_step_select_language()
            elif mode == SELECTION_MODE_PROVIDER:
                return await self.async_step_select_provider()
            else:
                self._filtered_channels = self._all_channels
                self._current_page = 0
                return await self.async_step_channel_page()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_DAYS, default=self._days): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=7)
                ),
                vol.Required(CONF_SELECTION_MODE, default=SELECTION_MODE_LANGUAGE): vol.In([
                    SELECTION_MODE_LANGUAGE,
                    SELECTION_MODE_PROVIDER,
                    SELECTION_MODE_MANUAL,
                ]),
            }),
        )

    async def async_step_select_language(self, user_input=None) -> FlowResult:
        if user_input is not None:
            selected_langs = user_input.get(CONF_LANGUAGES, [])
            self._filtered_channels = [
                ch for ch in self._all_channels if ch["lang_code"] in selected_langs
            ]
            self._selected_ids = {ch["id"] for ch in self._filtered_channels}
            self._current_page = 0
            return await self.async_step_channel_page()

        return self.async_show_form(
            step_id="select_language",
            data_schema=vol.Schema({
                vol.Required(CONF_LANGUAGES, default=["CZ"]): cv.multi_select(
                    {lang: lang for lang in AVAILABLE_LANGUAGES}
                ),
            }),
        )

    async def async_step_select_provider(self, user_input=None) -> FlowResult:
        if user_input is not None:
            selected_providers = user_input.get(CONF_PROVIDERS, [])
            self._filtered_channels = [
                ch for ch in self._all_channels
                if any(p in ch.get("providers", []) for p in selected_providers)
            ]
            self._selected_ids = {ch["id"] for ch in self._filtered_channels}
            self._current_page = 0
            return await self.async_step_channel_page()

        return self.async_show_form(
            step_id="select_provider",
            data_schema=vol.Schema({
                vol.Required(CONF_PROVIDERS, default=["O2"]): cv.multi_select(
                    {p: p for p in AVAILABLE_PROVIDERS}
                ),
            }),
        )

    async def async_step_channel_page(self, user_input=None) -> FlowResult:
        if user_input is not None:
            page_selected = set(user_input.get(CONF_TV_IDS, []))
            page_all = {
                ch["id"]
                for ch in self._filtered_channels[
                    self._current_page * CHANNELS_PER_PAGE:
                    (self._current_page + 1) * CHANNELS_PER_PAGE
                ]
            }
            self._selected_ids -= page_all
            self._selected_ids |= page_selected
            self._current_page += 1

        total_pages = max(1, (len(self._filtered_channels) - 1) // CHANNELS_PER_PAGE + 1)
        start = self._current_page * CHANNELS_PER_PAGE
        page_channels = self._filtered_channels[start: start + CHANNELS_PER_PAGE]

        if not page_channels:
            return self.async_create_entry(
                title="",
                data={
                    CONF_TV_IDS: list(self._selected_ids),
                    CONF_DAYS: self._days,
                },
            )

        page_dict = {ch["id"]: f"{ch['name']} ({ch['lang_code']})" for ch in page_channels}
        page_preselected = [ch["id"] for ch in page_channels if ch["id"] in self._selected_ids]

        return self.async_show_form(
            step_id="channel_page",
            data_schema=vol.Schema({
                vol.Optional(CONF_TV_IDS, default=page_preselected): cv.multi_select(page_dict),
            }),
            description_placeholders={
                "page": str(self._current_page + 1),
                "total": str(total_pages),
            },
        )