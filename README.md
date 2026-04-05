# ha-epg

Custom integrace pro Home Assistant zobrazující TV program (EPG) pro české, slovenské, polské a další kanály.

## Funkce

- 📺 TV program pro až 783 kanálů (CZ, SK, PL, DE, EN, FR, HU, IT, RU, ES)
- 📅 Program až 7 dní dopředu + včerejšek
- 🔍 Fulltext vyhledávání přes WebSocket API
- ⚙️ Snadné nastavení přes UI wizard
- 🔄 Automatická aktualizace každé 4 hodiny

## Instalace

### Pomocí HACS (doporučeno)

1. HACS → Integrace → ⋮ → **Custom repositories**
2. URL: `https://github.com/jerod33/ha-epg`, kategorie: **Integration**
3. Vyhledej „EPG" a nainstaluj
4. Restartuj Home Assistant

### Ručně

1. Stáhni repozitář
2. Zkopíruj složku `custom_components/epg` do `/config/custom_components/epg`
3. Restartuj Home Assistant

## Nastavení

1. Nastavení → Zařízení a služby → **Přidat integraci** → hledej „EPG"
2. Zvol počet dní a způsob výběru kanálů:
   - **Podle jazyka** – vyber jazyky (CZ, SK, PL, DE, ...)
   - **Podle providera** – vyber poskytovatele (O2, Skylink, Skylink SK)
   - **Ruční výběr** – vyber kanály ručně ze seznamu
3. Na dalších stránkách upřesni výběr kanálů (20 kanálů na stránku)

## Vytvořené entity

Pro každý vybraný kanál vznikne sensor:
```yaml
sensor.epg_ct1:
  state: "Název aktuálního pořadu"
  attributes:
    channel_name: "ČT1"
    logo_url: "ct1.png"
    current_title: "Zprávy"
    current_start: "18:00"
    current_stop: "18:30"
    next_title: "Sama doma"
    next_start: "18:30"
```

## WebSocket API

Pro custom Lovelace karty je k dispozici WebSocket API:
```javascript
// Fulltext vyhledávání
this.hass.callWS({ type: "epg/search", query: "Zprávy", days: 3 })

// Program jednoho kanálu
this.hass.callWS({ type: "epg/channel", channel_id: "2", days: 7 })

// Program pro konkrétní den
this.hass.callWS({ type: "epg/day", day_offset: 0 }) // 0=dnes, 1=zítra
```

## Zdroj dat

Data jsou stahována z `programandroid.365dni.cz` – stejný zdroj jako mobilní aplikace.
Aktualizace probíhá automaticky každé 4 hodiny.

## Podporované jazyky / kanály

| Jazyk | Počet kanálů |
|-------|-------------|
| CZ | 185 |
| PL | 159 |
| SK | 85 |
| EN | 130 |
| HU | 69 |
| DE | 47 |
| IT | 30 |
| FR | 25 |
| RU | 28 |
| ES | 25 |

## Změny

### 1.0.1
- Oprava zobrazení stránkování při výběru kanálů

### 1.0.0
- První verze
- Config flow wizard s výběrem podle jazyka / providera / ručně
- Stránkovaný výběr kanálů
- WebSocket API pro vyhledávání
- Centrální EPG cache v paměti