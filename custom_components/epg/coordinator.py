import logging
import os
import json
from datetime import datetime, timedelta
import aiofiles
import xmltodict
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
            # API vrací JSON-like strukturu přes xmltodict
            # Zkusíme nejdřív JSON parse
        except Exception as e:
            _LOGGER.warning("Chyba při parsování EPG XML (%s): %s", date_str, e)
            return []

        try:
            # Data jsou ve skutečnosti JSON
            data_json = json.loads(data)
            programs = data_json.get("a", {}).get("p", [])
            if isinstance(programs, dict):
                programs = [programs]
            return programs or []
        except Exception:
            pass

        # Fallback na xmltodict
        try:
            programs = parsed.get("a", {}).get("p", [])
            if isinstance(programs, dict):
                programs = [programs]
            return programs or []
        except Exception as e:
            _LOGGER.warning("Chyba při zpracování EPG dat (%s): %s", date_str, e)
            return []

    async def _async_update_data(self) -> dict:
        """Stáhne EPG pro všechny vybrané kanály a dny, uloží do hass.data."""
        options = self.config_entry.options or self.config_entry.data
        id_tv_list: list = options.get(CONF_TV_IDS, [])
        days: int = options.get(CONF_DAYS, 7)

        if not id_tv_list:
            _LOGGER.warning("Žádné kanály nejsou vybrány.")
            return {}

        # Načti info o kanálech
        self._channels_info = await self._async_load_channels_info()

        session = async_get_clientsession(self.hass)
        id_tv_str = ",".join(id_tv_list)

        # Včerejšek + dnes + N dní dopředu
        day_offsets = list(range(-1, days))
        epg_data: dict = {ch_id: {} for ch_id in id_tv_list}

        for offset in day_offsets:
            date = datetime.now() + timedelta(days=offset)
            date_str = date.strftime("%Y-%m-%d")
            day_key = f"day_{offset + 2}"  # day_1=včera, day_2=dnes

            programs = await self._async_fetch_day(session, id_tv_str, date_str)

            _LOGGER.debug(
                "Staženo %d pořadů pro %s (offset %d, key %s)",
                len(programs), date_str, offset, day_key
            )

            for program in programs:
                # Nová struktura – data jsou v "text" klíči
                prog_text = program.get("text", {})
                ch_id = prog_text.get("id_tv")

                if not ch_id or ch_id not in epg_data:
                    continue

                # Parsování názvu – může být string, dict nebo list
                title_data = program.get("n", "")
                if isinstance(title_data, list):
                    first = title_data[0]
                    if isinstance(first, dict):
                        title = first.get("_", first.get("#text", ""))
                    else:
                        title = str(first)
                elif isinstance(title_data, dict):
                    title = title_data.get("_", title_data.get("#text", ""))
                else:
                    title = str(title_data) if title_data else ""

                # Parsování popisu
                desc_data = program.get("k", "")
                if isinstance(desc_data, list):
                    description = desc_data[0] if desc_data else ""
                else:
                    description = str(desc_data) if desc_data else ""

                # Parsování žánru
                genre_data = program.get("t", "")
                if isinstance(genre_data, list):
                    genre = genre_data[0] if genre_data else ""
                else:
                    genre = str(genre_data) if genre_data else ""

                entry = {
                    "id_tv": ch_id,
                    "start": prog_text.get("o", ""),   # formát: "2026-04-07 05:12:00"
                    "stop": prog_text.get("d", ""),    # formát: "2026-04-07 05:40:00"
                    "title": title,
                    "description": description,
                    "genre": genre,
                    "channel_name": self._channels_info.get(ch_id, {}).get("name", ""),
                    "logo_url": self._channels_info.get(ch_id, {}).get("logo_url", ""),
                }

                epg_data[ch_id].setdefault(day_key, []).append(entry)

        # Ulož do centrální cache
        self.hass.data[DOMAIN]["epg_data"] = epg_data
        _LOGGER.info("EPG cache aktualizována: %d kanálů", len(epg_data))

        return epg_data

    def get_channel_info(self, ch_id: str) -> dict:
        """Vrátí info o kanálu (name, logo_url)."""
        return self._channels_info.get(ch_id, {})

    def get_current_and_next(self, ch_id: str) -> tuple[dict | None, dict | None]:
        """Vrátí aktuální a příští pořad pro daný kanál."""
        epg_data = self.hass.data.get(DOMAIN, {}).get("epg_data", {})
        today_programs = epg_data.get(ch_id, {}).get("day_2", [])

        now = datetime.now()
        current = None
        next_program = None

        for i, program in enumerate(today_programs):
            try:
                start = datetime.strptime(program["start"], "%Y-%m-%d %H:%M:%S")
                stop = datetime.strptime(program["stop"], "%Y-%m-%d %H:%M:%S")

                if start <= now < stop:
                    current = program
                    if i + 1 < len(today_programs):
                        next_program = today_programs[i + 1]
                    break

            except (ValueError, KeyError):
                continue

        return current, next_program