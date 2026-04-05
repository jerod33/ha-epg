import logging
import os
import json
from datetime import datetime, timedelta
import aiofiles
import xmltodict
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, USER_AGENT, BASE_URL, SCAN_INTERVAL, CONF_TV_IDS, CONF_DAYS

_LOGGER = logging.getLogger(__name__)

TIMEOUT = 30


class EPGCoordinator(DataUpdateCoordinator):
    """Koordinátor který stahuje EPG data pro všechny vybrané kanály."""

    def __init__(self, hass, config_entry):
        self.config_entry = config_entry
        self._channels_info = {}

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_load_channels_info(self) -> dict:
        """Načte info o kanálech z default_channels.json."""
        data_file = os.path.join(os.path.dirname(__file__), "default_channels.json")
        async with aiofiles.open(data_file, "r", encoding="utf-8") as f:
            raw = await f.read()
        channels = json.loads(raw)
        return {ch["id"]: ch for ch in channels}

    async def _async_fetch_day(self, session, id_tv: str, date_str: str) -> list:
        """Stáhne EPG data pro daný den a kanály."""
        url = f"{BASE_URL}?datum={date_str}&id_tv={id_tv}"
        headers = {"User-Agent": USER_AGENT}

        try:
            async with session.get(url, headers=headers, timeout=TIMEOUT) as response:
                response.raise_for_status()
                data = await response.text()
        except Exception as e:
            _LOGGER.warning("Chyba při stahování EPG pro %s (%s): %s", date_str, id_tv, e)
            return []

        try:
            parsed = xmltodict.parse(data)
            programs = parsed.get("a", {}).get("p", [])
            if isinstance(programs, dict):
                programs = [programs]
            return programs or []
        except Exception as e:
            _LOGGER.warning("Chyba při parsování EPG XML (%s): %s", date_str, e)
            return []

    async def _async_update_data(self) -> dict:
        """Stáhne EPG pro všechny vybrané kanály a dny, uloží do hass.data."""
        options = self.config_entry.options or self.config_entry.data
        id_tv_list: list = options.get(CONF_TV_IDS, [])
        days: int = options.get(CONF_DAYS, 7)

        if not id_tv_list:
            _LOGGER.warning("Žádné kanály nejsou vybrány.")
            return {}

        # Načti info o kanálech (jednou za update)
        self._channels_info = await self._async_load_channels_info()

        session = async_get_clientsession(self.hass)
        id_tv_str = ",".join(id_tv_list)

        # Stáhni data pro včerejšek + dnešek + N dní dopředu
        day_offsets = list(range(-1, days))
        epg_data: dict = {ch_id: {} for ch_id in id_tv_list}

        for offset in day_offsets:
            date = datetime.now() + timedelta(days=offset)
            date_str = date.strftime("%Y-%m-%d")
            day_key = f"day_{offset + 2}"  # day_1 = včerejšek, day_2 = dnes, ...

            programs = await self._async_fetch_day(session, id_tv_str, date_str)

            # Roztřiď programy podle kanálu
            for program in programs:
                ch_id = program.get("@id_tv")
                if ch_id not in epg_data:
                    continue

                title_data = program.get("n", "")
                title = (
                    title_data.get("#text", "") if isinstance(title_data, dict) else title_data
                )
                url_link = title_data.get("@u") if isinstance(title_data, dict) else None

                entry = {
                    "id_tv": ch_id,
                    "start": program.get("@o", ""),
                    "stop": program.get("@d", ""),
                    "title": title,
                    "title_url": url_link,
                    "description": program.get("k", ""),
                    "genre": program.get("t", ""),
                    "channel_name": self._channels_info.get(ch_id, {}).get("name", ""),
                    "logo_url": self._channels_info.get(ch_id, {}).get("logo_url", ""),
                }

                epg_data[ch_id].setdefault(day_key, []).append(entry)

        # Ulož do centrální cache
        self.hass.data[DOMAIN]["epg_data"] = epg_data
        _LOGGER.debug("EPG cache aktualizována: %d kanálů", len(epg_data))

        return epg_data

    def get_channel_info(self, ch_id: str) -> dict:
        """Vrátí info o kanálu (name, logo_url)."""
        return self._channels_info.get(ch_id, {})

    def get_current_and_next(self, ch_id: str) -> tuple[dict | None, dict | None]:
        """Vrátí aktuální a příští pořad pro daný kanál."""
        epg_data = self.hass.data.get(DOMAIN, {}).get("epg_data", {})
        today_programs = epg_data.get(ch_id, {}).get("day_2", [])  # day_2 = dnes

        now = datetime.now()
        current = None
        next_program = None

        for i, program in enumerate(today_programs):
            try:
                start = datetime.strptime(program["start"], "%H:%M")
                start = start.replace(year=now.year, month=now.month, day=now.day)
                stop = datetime.strptime(program["stop"], "%H:%M")
                stop = stop.replace(year=now.year, month=now.month, day=now.day)

                # Přes půlnoc
                if stop < start:
                    stop += timedelta(days=1)

                if start <= now < stop:
                    current = program
                    if i + 1 < len(today_programs):
                        next_program = today_programs[i + 1]
                    break
            except (ValueError, KeyError):
                continue

        return current, next_program