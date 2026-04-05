import logging
import voluptuous as vol
from homeassistant.core import HomeAssistant, callback
from homeassistant.components import websocket_api

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup_websocket(hass: HomeAssistant) -> None:
    """Zaregistruj WebSocket handlery."""
    websocket_api.async_register_command(hass, handle_epg_search)
    websocket_api.async_register_command(hass, handle_epg_channel)
    websocket_api.async_register_command(hass, handle_epg_day)
    _LOGGER.debug("EPG WebSocket API zaregistrováno")


@websocket_api.websocket_command({
    vol.Required("type"): "epg/search",
    vol.Optional("query", default=""): str,
    vol.Optional("days", default=7): vol.All(vol.Coerce(int), vol.Range(min=1, max=8)),
    vol.Optional("channel_ids", default=[]): [str],
    vol.Optional("lang_code", default=""): str,
})
@callback
def handle_epg_search(hass, connection, msg):
    """Fulltext search přes všechna EPG data.
    
    Volání z Lovelace card:
    this.hass.callWS({ type: 'epg/search', query: 'Zprávy', days: 3 })
    """
    epg_data = hass.data.get(DOMAIN, {}).get("epg_data", {})
    query = msg.get("query", "").lower().strip()
    filter_channel_ids = msg.get("channel_ids", [])
    filter_lang = msg.get("lang_code", "").upper()
    days = msg.get("days", 7)

    results = []

    for ch_id, days_data in epg_data.items():
        # Filtr podle kanálu
        if filter_channel_ids and ch_id not in filter_channel_ids:
            continue

        for day_key, programs in days_data.items():
            # Filtr podle počtu dní (day_1=včera, day_2=dnes, ...)
            try:
                day_num = int(day_key.split("_")[1])
                if day_num > days + 1:
                    continue
            except (ValueError, IndexError):
                continue

            for program in programs:
                # Filtr podle jazyka
                if filter_lang and program.get("lang_code", "") != filter_lang:
                    continue

                # Fulltext search v názvu a popisu
                if query:
                    searchable = (
                        program.get("title", "") + " " +
                        program.get("description", "")
                    ).lower()
                    if query not in searchable:
                        continue

                results.append({
                    "channel_id": ch_id,
                    "channel_name": program.get("channel_name"),
                    "logo_url": program.get("logo_url"),
                    "day": day_key,
                    "title": program.get("title"),
                    "start": program.get("start"),
                    "stop": program.get("stop"),
                    "description": program.get("description"),
                    "genre": program.get("genre"),
                })

    # Seřaď podle dne a času
    results.sort(key=lambda x: (x["day"], x["start"]))

    connection.send_result(msg["id"], {
        "count": len(results),
        "results": results,
    })


@websocket_api.websocket_command({
    vol.Required("type"): "epg/channel",
    vol.Required("channel_id"): str,
    vol.Optional("days", default=7): vol.All(vol.Coerce(int), vol.Range(min=1, max=8)),
})
@callback
def handle_epg_channel(hass, connection, msg):
    """Vrátí všechna EPG data pro jeden kanál.
    
    Volání z Lovelace card:
    this.hass.callWS({ type: 'epg/channel', channel_id: '2', days: 3 })
    """
    epg_data = hass.data.get(DOMAIN, {}).get("epg_data", {})
    ch_id = msg["channel_id"]
    days = msg.get("days", 7)

    channel_data = epg_data.get(ch_id, {})
    result = {}

    for day_key, programs in channel_data.items():
        try:
            day_num = int(day_key.split("_")[1])
            if day_num > days + 1:
                continue
        except (ValueError, IndexError):
            continue
        result[day_key] = programs

    connection.send_result(msg["id"], {
        "channel_id": ch_id,
        "data": result,
    })


@websocket_api.websocket_command({
    vol.Required("type"): "epg/day",
    vol.Required("day_offset"): vol.All(vol.Coerce(int), vol.Range(min=-1, max=6)),
    vol.Optional("channel_ids", default=[]): [str],
})
@callback
def handle_epg_day(hass, connection, msg):
    """Vrátí EPG program pro konkrétní den napříč kanály.
    
    day_offset: -1=včera, 0=dnes, 1=zítra, ...
    Volání z Lovelace card:
    this.hass.callWS({ type: 'epg/day', day_offset: 0 })
    """
    epg_data = hass.data.get(DOMAIN, {}).get("epg_data", {})
    day_offset = msg["day_offset"]
    filter_channel_ids = msg.get("channel_ids", [])

    # day_key: day_1=včera(offset -1), day_2=dnes(offset 0), ...
    day_key = f"day_{day_offset + 2}"

    results = {}

    for ch_id, days_data in epg_data.items():
        if filter_channel_ids and ch_id not in filter_channel_ids:
            continue

        programs = days_data.get(day_key, [])
        if programs:
            results[ch_id] = programs

    connection.send_result(msg["id"], {
        "day_offset": day_offset,
        "day_key": day_key,
        "data": results,
    })