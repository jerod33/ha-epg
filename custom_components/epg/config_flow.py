import logging
import os
import json
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN, CONF_DAYS, CONF_TV_IDS, CONF_SELECTION_MODE, CONF_LANGUAGES, CONF_PROVIDERS,
    SELECTION_MODE_LANGUAGE, SELECTION_MODE_PROVIDER, SELECTION_MODE_MANUAL,
    AVAILABLE_LANGUAGES, AVAILABLE_PROVIDERS,
)

_LOGGER = logging.getLogger(__name__)


def load_channels():
    """Načte kanály z default_channels.json synchronně."""
    data_file = os.path.join(os.path.dirname(__file__), "default_channels.json")
    with open(data_file, "r", encoding="utf-8") as f:
        return json.load(f)


def build_channel_selector(channels: list) -> selector.SelectSelector:
    """Vytvoří SelectSelector pro výběr kanálů."""
    options = [
        selector.SelectOptionDict(value=ch["id"], label=f"{ch['name']} ({ch['lang_code']})")
        for ch in channels
    ]
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            multiple=True,
            mode=selector.SelectSelectorMode.LIST,
        )
    )


class EPGConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow pro EPG integraci."""

    VERSION = 1

    def __init__(self):
        self._all_channels = []
        self._filtered_channels = []
        self._days = 7

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EPGOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Krok 1: počet dní + režim výběru."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            self._days = int(user_input[CONF_DAYS])
            self._all_channels = await self.hass.async_add_executor_job(load_channels)
            mode = user_input[CONF_SELECTION_MODE]

            if mode == SELECTION_MODE_LANGUAGE:
                return await self.async_step_select_language()
            elif mode == SELECTION_MODE_PROVIDER:
                return await self.async_step_select_provider()
            else:
                self._filtered_channels = self._all_channels
                return await self.async_step_select_channels()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_DAYS, default=7): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=7, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_SELECTION_MODE, default=SELECTION_MODE_LANGUAGE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=SELECTION_MODE_LANGUAGE, label="Podle jazyka"),
                            selector.SelectOptionDict(value=SELECTION_MODE_PROVIDER, label="Podle poskytovatele"),
                            selector.SelectOptionDict(value=SELECTION_MODE_MANUAL, label="Ruční výběr"),
                        ],
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }),
        )

    async def async_step_select_language(self, user_input=None):
        """Krok 2A: výběr jazyků."""
        if user_input is not None:
            selected_langs = user_input.get(CONF_LANGUAGES, [])
            self._filtered_channels = [
                ch for ch in self._all_channels if ch["lang_code"] in selected_langs
            ]
            return await self.async_step_select_channels()

        return self.async_show_form(
            step_id="select_language",
            data_schema=vol.Schema({
                vol.Required(CONF_LANGUAGES): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=lang, label=lang)
                            for lang in AVAILABLE_LANGUAGES
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }),
        )

    async def async_step_select_provider(self, user_input=None):
        """Krok 2B: výběr providerů."""
        if user_input is not None:
            selected_providers = user_input.get(CONF_PROVIDERS, [])
            self._filtered_channels = [
                ch for ch in self._all_channels
                if any(p in ch.get("providers", []) for p in selected_providers)
            ]
            return await self.async_step_select_channels()

        return self.async_show_form(
            step_id="select_provider",
            data_schema=vol.Schema({
                vol.Required(CONF_PROVIDERS): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=p, label=p)
                            for p in AVAILABLE_PROVIDERS
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }),
        )

    async def async_step_select_channels(self, user_input=None):
        """Krok 3: výběr kanálů ze seznamu."""
        if user_input is not None:
            selected_ids = user_input.get(CONF_TV_IDS, [])
            return self.async_create_entry(
                title="EPG",
                data={
                    CONF_TV_IDS: selected_ids,
                    CONF_DAYS: self._days,
                },
            )

        return self.async_show_form(
            step_id="select_channels",
            data_schema=vol.Schema({
                vol.Required(CONF_TV_IDS, default=[]): build_channel_selector(
                    self._filtered_channels
                ),
            }),
            description_placeholders={
                "count": str(len(self._filtered_channels)),
            },
        )


class EPGOptionsFlow(config_entries.OptionsFlow):
    """Options flow pro EPG integraci."""

    def __init__(self, config_entry):
        self._all_channels = []
        self._filtered_channels = []
        self._current_ids = list(
            config_entry.options.get(CONF_TV_IDS,
            config_entry.data.get(CONF_TV_IDS, []))
        )
        self._days = config_entry.options.get(
            CONF_DAYS, config_entry.data.get(CONF_DAYS, 7)
        )

    async def async_step_init(self, user_input=None):
        """Krok 1: počet dní + režim výběru."""
        if user_input is not None:
            self._days = int(user_input[CONF_DAYS])
            self._all_channels = await self.hass.async_add_executor_job(load_channels)
            mode = user_input[CONF_SELECTION_MODE]

            if mode == SELECTION_MODE_LANGUAGE:
                return await self.async_step_select_language()
            elif mode == SELECTION_MODE_PROVIDER:
                return await self.async_step_select_provider()
            else:
                self._filtered_channels = self._all_channels
                return await self.async_step_select_channels()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_DAYS, default=self._days): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=7, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_SELECTION_MODE, default=SELECTION_MODE_LANGUAGE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=SELECTION_MODE_LANGUAGE, label="Podle jazyka"),
                            selector.SelectOptionDict(value=SELECTION_MODE_PROVIDER, label="Podle poskytovatele"),
                            selector.SelectOptionDict(value=SELECTION_MODE_MANUAL, label="Ruční výběr"),
                        ],
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }),
        )

    async def async_step_select_language(self, user_input=None):
        if user_input is not None:
            selected_langs = user_input.get(CONF_LANGUAGES, [])
            self._filtered_channels = [
                ch for ch in self._all_channels if ch["lang_code"] in selected_langs
            ]
            return await self.async_step_select_channels()

        return self.async_show_form(
            step_id="select_language",
            data_schema=vol.Schema({
                vol.Required(CONF_LANGUAGES): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=lang, label=lang)
                            for lang in AVAILABLE_LANGUAGES
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }),
        )

    async def async_step_select_provider(self, user_input=None):
        if user_input is not None:
            selected_providers = user_input.get(CONF_PROVIDERS, [])
            self._filtered_channels = [
                ch for ch in self._all_channels
                if any(p in ch.get("providers", []) for p in selected_providers)
            ]
            return await self.async_step_select_channels()

        return self.async_show_form(
            step_id="select_provider",
            data_schema=vol.Schema({
                vol.Required(CONF_PROVIDERS): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=p, label=p)
                            for p in AVAILABLE_PROVIDERS
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }),
        )

    async def async_step_select_channels(self, user_input=None):
        if user_input is not None:
            selected_ids = user_input.get(CONF_TV_IDS, [])
            return self.async_create_entry(
                title="",
                data={
                    CONF_TV_IDS: selected_ids,
                    CONF_DAYS: self._days,
                },
            )

        current_in_filter = [
            ch_id for ch_id in self._current_ids
            if any(ch["id"] == ch_id for ch in self._filtered_channels)
        ]

        return self.async_show_form(
            step_id="select_channels",
            data_schema=vol.Schema({
                vol.Required(CONF_TV_IDS, default=current_in_filter): build_channel_selector(
                    self._filtered_channels
                ),
            }),
            description_placeholders={
                "count": str(len(self._filtered_channels)),
            },
        )