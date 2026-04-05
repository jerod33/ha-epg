import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, CONF_DAYS, CONF_TV_IDS
from .websocket import async_setup_websocket

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EPG from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["epg_data"] = {}

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    async_setup_websocket(hass)

    _LOGGER.info("EPG integration setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload EPG config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    if unload_ok:
        hass.data[DOMAIN].pop("epg_data", None)
    return unload_ok