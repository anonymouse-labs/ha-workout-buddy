<div align="center">

<img src="custom_components/workout_buddy/brand/icon.png" width="128" alt="Workout Buddy icon">

# Workout Buddy

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Anonymouse0104&repository=ha-workout-buddy&category=integration) [![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/anonymouse0501)

[Nederlands](#nederlands) | [English](#english)

</div>

## Nederlands

Home Assistant integratie die per persoon een dagoverzicht en na elke workout een samenvatting met vergelijking naar de vorige workout verstuurt, bijvoorbeeld naar een WhatsApp-groep via [WhatsApp Notifier](https://github.com/Anonymouse0104/ha-whatsapp-notifier) (inclusief grafiek als afbeelding).

De integratie is bron-onafhankelijk. De officiële Companion App heeft geen workout-sensor, dus je wijst zelf aan welke sensor, welk attribuut of welk event je workouts levert.

### Installatie

1. HACS, Integraties, menu, Aangepaste repository: `https://github.com/Anonymouse0104/ha-workout-buddy`, categorie Integratie.
2. Installeer Workout Buddy en herstart Home Assistant.
3. Instellingen, Apparaten en services, Integratie toevoegen, Workout Buddy.
4. Voeg via het menu van de integratie een **Persoon** toe en daarna een **Workout-bron** per persoon.

Vereist Home Assistant 2025.3 of nieuwer (subitems in de config flow).

### Instellingen (opties)

| Optie | Betekenis |
| --- | --- |
| Verzendservice | `script.whatsapp_melding` (standaard), een `notify.*` service, `notify.send_message` of `whatsapp_notifier.send_message` |
| Ontvanger | Chat-ID van de groep (`whatsapp_notifier.send_message`) of notify-entiteit (`notify.send_message`). Mag leeg bij een script. Is hij nodig en leeg, dan staat er een duidelijke fout in het log |
| Vertraging | Wachttijd na een nieuwe workout, standaard 60 s |
| Workouts bewaren | Per persoon en type, standaard 20 |
| Gemiddelde vergelijking | Vergelijk ook met het gemiddelde van de laatste 5 van dat type |
| Dagoverzicht | Per persoon op eigen tijd, één gezamenlijk bericht op vaste tijd, of gezamenlijk zodra iedereen gesynchroniseerd is (uiterlijk op de ingestelde tijd) |

Het script `script.whatsapp_melding` krijgt de velden `emoji`, `kop`, `tekst` en `voetnoot`. Andere kanalen krijgen één tekst: `emoji kop`, daarna de tekst.

Verzenden gebeurt in een try/except. Mislukt het, dan wordt de workout niet als verstuurd gemarkeerd. Elke 15 minuten wordt opnieuw geprobeerd, maximaal 3 pogingen in totaal.

### Workout-bronnen

| Type | Wanneer | Instellen |
| --- | --- | --- |
| Sensor met attributen | Een sensor waarvan state of attributen veranderen bij een nieuwe workout | Per veld de attribuutnaam. `state` verwijst naar de sensorstate. Alle velden optioneel |
| Event | Een event op de event bus, bijvoorbeeld uit een webhook-automation | Event-type en per veld de sleutel in de payload |
| Tekst-sensor | State is tekst, zoals `Outdoor Walk · 129 min · 10.52 km · 663 kcal · 97 bpm` | Alleen de sensor. Scheiders: `·`, `•`, `\|`, `;` of komma plus spatie |

Velden: type, start, einde, duur, afstand, kcal, gemiddelde en maximale hartslag. Eenheden stel je per bron in (s/min/h, m/km/mi, kcal/kJ). Staat er een eenheid achter de waarde (`3.1 mi`), dan gaat die voor. Uitkomst is altijd minuten, km en kcal. De waarden `unknown`, `unavailable`, `NaN` en leeg worden genegeerd. Dubbele workouts (zelfde type en start, of zonder start dezelfde waarden) geven één bericht.

**Niet zeker van de attribuutnamen van je app?** Roep `workout_buddy.dump_source` aan (met `source` of `entity_id`). De ruwe state en attributen komen in het log (waarschuwingsniveau) en in een melding.

Aanname: de attribuutnamen van apps als Halthy, HealthSync of Life Dashboard Companion zijn niet in deze repo vastgelegd. Lever een dump aan en ze kunnen als voorbeeld in deze README.

### Bekende bronnen voor dagsensoren

Entity-ID's kunnen per toestel een suffix hebben. Controleer de actuele Companion App documentatie.

| Platform | Stappen | Afstand | Hartslag | Rusthartslag | Actieve kcal |
| --- | --- | --- | --- | --- | --- |
| iPhone (Apple Health, aanzetten in de app) | `sensor.health_steps` of `sensor.steps` | `sensor.walking_running_distance` (km) of `sensor.distance` (m) | `sensor.heart_rate` | `sensor.resting_heart_rate` | `sensor.active_energy` |
| Android (Health Connect, ook Samsung Health) | `health_connect_daily_steps` | `health_connect_daily_distance` (m) | `health_connect_heart_rate` | `health_connect_resting_heart_rate` | `health_connect_active_calories_burned` |
| Samsung/Android via Google Health integratie | dagtotalen | dagtotalen | niet | alleen rusthartslag | niet |

Workouts: iPhone via apps die Apple Health Workouts doorsturen (zoals Halthy of HealthSync), Android via Health Connect `exercise` (zoals Life Dashboard Companion) of een eigen automation via MQTT of webhook. Deze bronnen zijn niet getest, gebruik `dump_source`.

### Dagoverzicht

Kies per persoon welke onderdelen meegaan en welke sensor erbij hoort: stappen, afstand, hartslag, rusthartslag, actieve kcal en slaap. De waarden worden gelezen op het moment van versturen, dus kies een tijd vóór middernacht. Een ontbrekende waarde wordt `-`. Eenheden komen uit de sensor (m, km en mi worden km). Bij "wacht tot gesynchroniseerd" geldt een sensor als gesynchroniseerd zodra hij sinds middernacht is bijgewerkt.

```
Dagoverzicht
Ruub: 8.420 stappen, 6,1 km, hartslag 73 bpm, rust 63 bpm
Demi: 7.903 stappen, 5,4 km, hartslag 65 bpm, rust -
```

```
Workout van Ruub: Outdoor Walk
129 min, 10,52 km, 663 kcal, gem. 97 bpm
Vorige keer: +1,2 km, +8 min, tempo 20 s/km sneller, gem. hartslag -3 bpm
```

(Waarden zijn een illustratie van de opmaak.) Hartslag wordt alleen als verschil getoond, nooit beoordeeld. De taal van de berichten volgt de taal van Home Assistant: Engels bij `en`, anders Nederlands.

### Grafiek als afbeelding

Alles hieronder stel je in bij de opties.

| Optie | Wat het doet |
| --- | --- |
| Stuur een grafiek als afbeelding | Aan of uit. Standaard uit |
| Stuur ook de tekst | Uit = alleen de grafiek (zonder tekst eronder). Een kanaal dat geen afbeeldingen aankan, krijgt altijd de tekst |
| Wat komt er in de grafiek | Kerncijfers, lijngrafieken en/of staafjes van de laatste workouts |
| Lijngrafieken in het dagoverzicht | Kies uit hartslag, stappen, afstand en actieve kcal. Elke keuze wordt een eigen lijngrafiek over de dag, een lijn per persoon |

- **Workout:** een samenvattingskaart in Strava-stijl. Bovenaan de kerncijfers (afstand, tijd, tempo, kcal, gemiddelde hartslag) met eronder het verschil met de vorige keer. Daaronder de hartslag tijdens de workout als lijn, met de vorige workout van hetzelfde type erachter in grijs, en onderaan staafjes van de laatste 6 workouts.
- **Dagoverzicht:** de cijfers per persoon en de gekozen lijngrafieken over de dag. Bij hartslag staan de **laagste en hoogste** hartslag van die dag (uit de geschiedenis), niet de laatste meting. Zonder geschiedenis staat er `-`.

De lijnen komen uit de geschiedenis (recorder) van je hartslagsensor. Daarvoor moet je bij de persoon een **hartslagsensor** hebben ingevuld. Zonder die sensor, of zonder recorder, blijven de kerncijfers en de staafjes en ontbreekt de lijn. De hartslagcurve van elke workout wordt bij het opslaan bewaard, dus de vergelijking met een vorige workout blijft werken ook als de recorder die data al heeft opgeruimd. Heeft je bron geen starttijd, dan wordt aangenomen dat de workout net klaar is.

De afbeeldingen komen in `/config/www/workout_buddy/` en worden steeds overschreven. Ze worden meegestuurd als:

- `whatsapp_notifier.send_message`: veld `image` (vereist ha-whatsapp-notifier 0.3.0 of nieuwer en de bridge-add-on 0.3.0);
- een script: veld `afbeelding` (pad), naast `emoji`, `kop`, `tekst` en `voetnoot`. Je script moet het zelf doorsturen;
- andere kanalen: alleen tekst.

Mislukt het tekenen of weigert het kanaal de afbeelding, dan gaat het bericht als tekst. Pillow zit al in Home Assistant.

### Entiteiten en services

Per persoon: sensor **Laatste workout** (state is het type, attributen zijn de velden, `key` en `vs_previous`), sensor **Laatste bericht verstuurd** en knop **Stuur dagoverzicht nu**.

| Service | Doel |
| --- | --- |
| `workout_buddy.send_daily_summary` | Dagoverzicht van een persoon, of van iedereen samen |
| `workout_buddy.send_workout_summary` | Een workout opnieuw versturen (`workout_key`, standaard de laatste) |
| `workout_buddy.clear_history` | Opgeslagen workouts wissen |
| `workout_buddy.dump_source` | Ruwe bron-data in log en melding |

Voorbeeld voor een groep via ha-whatsapp-notifier:

```yaml
send_service: whatsapp_notifier.send_message
recipient: "120363012345678901@g.us"
```

Een persoon hernoemen kan niet (de geschiedenis hangt aan de naam). Een bron wijzig je door hem te verwijderen en opnieuw toe te voegen.

### Tests

```bash
pip install -r requirements_test.txt
pytest
```

### Steun

Bespaart deze integratie je tijd, dan kun je me [steunen op Ko-fi](https://ko-fi.com/anonymouse0501). Het is helemaal optioneel en de integratie blijft in beide gevallen gratis.

---

## English

Home Assistant integration that sends, per person, a daily overview and, after each workout, a summary compared to the previous workout of the same type, for example to a WhatsApp group with [WhatsApp Notifier](https://github.com/Anonymouse0104/ha-whatsapp-notifier) (chart images included).

It is source-agnostic: the official Companion App has no workout sensor, so you point the integration at the sensor, attribute or event that delivers your workouts.

### Install

1. HACS, Integrations, menu, Custom repositories: `https://github.com/Anonymouse0104/ha-workout-buddy`, category Integration.
2. Install Workout Buddy and restart Home Assistant.
3. Settings, Devices & services, Add integration, Workout Buddy.
4. From the integration menu add a **Person**, then a **Workout source** per person.

Requires Home Assistant 2025.3 or newer (config subentries).

### Options

Send service (`script.whatsapp_melding` by default, any `notify.*`, `notify.send_message` or `whatsapp_notifier.send_message`), recipient (chat ID or notify entity, may be empty for scripts, a clear log error if it is needed and empty), delay (60 s), workouts kept per type (20), optional comparison with the average of the last 5, and the daily mode (per person, joint at a fixed time, or joint once everyone synced with a latest time). The script receives `emoji`, `kop`, `tekst`, `voetnoot`.

A failed send never marks a workout as sent. It is retried every 15 minutes, 3 attempts in total.

### Workout sources

| Type | Use | Setup |
| --- | --- | --- |
| Sensor with attributes | State or attributes change on a new workout | Attribute name per field; `state` means the sensor state |
| Event | Event on the bus (e.g. webhook automation) | Event type and payload key per field |
| Text sensor | State like `Outdoor Walk · 129 min · 10.52 km · 663 kcal · 97 bpm` | Only the sensor |

Output is always minutes, km, kcal and bpm. `unknown`, `unavailable`, `NaN` and empty values are ignored; duplicates (same type and start) are sent once. Not sure which attributes your app exposes? Call `workout_buddy.dump_source`. The attribute names of third-party apps are not assumed; they are configurable.

The tables in the Dutch section above list the known sources per platform. Messages are in Dutch, or English when Home Assistant's language is `en`.

### Chart image

Turn on **Send a chart image** in the options. A workout gets a summary card: key numbers with the difference from last time, the heart rate curve over the previous workout of the same type, and bars for the last 6. The daily overview shows the numbers per person and the heart rate over the day. The curves come from the recorder history of the heart rate sensor you set for the person, and each workout's curve is stored with it. Images are written to `/config/www/workout_buddy/` and go to `whatsapp_notifier.send_message` as `image` and to scripts as `afbeelding`; other channels get text only.

### Licentie / License

MIT, zie [LICENSE](LICENSE).

### Support

If this integration saves you some time, you can [support me on Ko-fi](https://ko-fi.com/anonymouse0501). It's entirely optional, and the integration stays free either way.
