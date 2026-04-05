import logging
from datetime import datetime, timezone
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_TV_IDS, CONF_DAYS
from .coordinator import EPGCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Nastaví EPG sensory z config entry."""
    options = config_entry.options or config_entry.data
    id_tv_list = options.get(CONF_TV_IDS, [])

    coordinator = EPGCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    # Ulož coordinator do hass.data pro případný přístup z jiných míst
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["coordinator"] = coordinator

    entities = [EPGSensor(coordinator, ch_id) for ch_id in id_tv_list]
    async_add_entities(entities)

    _LOGGER.info("EPG: přidáno %d sensorů", len(entities))


class EPGSensor(CoordinatorEntity, SensorEntity):
    """Sensor pro jeden TV kanál – zobrazuje aktuální pořad."""

    def __init__(self, coordinator: EPGCoordinator, ch_id: str):
        super().__init__(coordinator)
        self._ch_id = ch_id
        ch_info = coordinator.get_channel_info(ch_id)
        self._channel_name = ch_info.get("name", ch_id)
        self._logo_url = ch_info.get("logo_url", "")

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._ch_id}"

    @property
    def name(self) -> str:
        return f"EPG {self._channel_name}"

    @property
    def icon(self) -> str:
        return "mdi:television-box"

    @property
    def state(self) -> str:
        """Název aktuálního pořadu jako stav sensoru."""
        current, _ = self.coordinator.get_current_and_next(self._ch_id)
        if current:
            return current.get("title", "Neznámý pořad")
        return "Není k dispozici"

    @property
    def extra_state_attributes(self) -> dict:
        """Minimální atributy – aktuální a příští pořad."""
        current, next_program = self.coordinator.get_current_and_next(self._ch_id)

        attrs = {
            "channel_name": self._channel_name,
            "logo_url": self._logo_url,
            "channel_id": self._ch_id,
        }

        if current:
            attrs.update({
                "current_title": current.get("title"),
                "current_start": current.get("start"),
                "current_stop": current.get("stop"),
                "current_description": current.get("description"),
                "current_genre": current.get("genre"),
            })

        if next_program:
            attrs.update({
                "next_title": next_program.get("title"),
                "next_start": next_program.get("start"),
                "next_stop": next_program.get("stop"),
            })

        return attrs