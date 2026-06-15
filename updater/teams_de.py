#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deutsche Team-Namen.

Die Spielplan-Quelle (football-data.org) liefert National-Mannschaften auf
Englisch ("Germany", "Ivory Coast"). Für den (älteren, deutschsprachigen) Nutzer
übersetzen wir sie in geläufige deutsche Namen. Vereinsnamen (Bundesliga/CL) sind
dort meist schon deutsch und bleiben unverändert (Fallback: Originalname).
"""

TEAM_DE = {
    # Europa
    "Germany": "Deutschland", "Switzerland": "Schweiz", "Austria": "Österreich",
    "Bosnia-Herzegovina": "Bosnien und Herzegowina", "Bosnia and Herzegovina": "Bosnien und Herzegowina",
    "Spain": "Spanien", "France": "Frankreich", "Italy": "Italien", "England": "England",
    "Netherlands": "Niederlande", "Belgium": "Belgien", "Portugal": "Portugal",
    "Croatia": "Kroatien", "Serbia": "Serbien", "Poland": "Polen", "Sweden": "Schweden",
    "Norway": "Norwegen", "Denmark": "Dänemark", "Finland": "Finnland", "Iceland": "Island",
    "Ireland": "Irland", "Republic of Ireland": "Irland", "Scotland": "Schottland", "Wales": "Wales",
    "Turkey": "Türkei", "Türkiye": "Türkei", "Greece": "Griechenland",
    "Czech Republic": "Tschechien", "Czechia": "Tschechien", "Slovakia": "Slowakei",
    "Slovenia": "Slowenien", "Hungary": "Ungarn", "Romania": "Rumänien", "Bulgaria": "Bulgarien",
    "Ukraine": "Ukraine", "Russia": "Russland", "Albania": "Albanien",
    "North Macedonia": "Nordmazedonien", "Montenegro": "Montenegro", "Kosovo": "Kosovo",
    "Georgia": "Georgien", "Luxembourg": "Luxemburg", "Northern Ireland": "Nordirland",
    # Süd-/Nordamerika
    "Brazil": "Brasilien", "Argentina": "Argentinien", "Uruguay": "Uruguay",
    "Colombia": "Kolumbien", "Chile": "Chile", "Peru": "Peru", "Ecuador": "Ecuador",
    "Paraguay": "Paraguay", "Bolivia": "Bolivien", "Venezuela": "Venezuela",
    "Mexico": "Mexiko", "United States": "USA", "USA": "USA", "Canada": "Kanada",
    "Costa Rica": "Costa Rica", "Panama": "Panama", "Honduras": "Honduras", "Jamaica": "Jamaika",
    # Asien/Ozeanien
    "Japan": "Japan", "South Korea": "Südkorea", "Korea Republic": "Südkorea",
    "Australia": "Australien", "Iran": "Iran", "Saudi Arabia": "Saudi-Arabien",
    "Qatar": "Katar", "Iraq": "Irak", "United Arab Emirates": "Vereinigte Arabische Emirate",
    "China": "China", "China PR": "China", "Uzbekistan": "Usbekistan", "New Zealand": "Neuseeland",
    # Afrika
    "Morocco": "Marokko", "Egypt": "Ägypten", "Tunisia": "Tunesien", "Algeria": "Algerien",
    "Senegal": "Senegal", "Nigeria": "Nigeria", "Ghana": "Ghana", "Cameroon": "Kamerun",
    "Ivory Coast": "Elfenbeinküste", "Côte d'Ivoire": "Elfenbeinküste", "Cote d'Ivoire": "Elfenbeinküste",
    "South Africa": "Südafrika", "Mali": "Mali",
    "Cape Verde": "Kap Verde", "Cape Verde Islands": "Kap Verde",
    "Congo DR": "DR Kongo", "DR Congo": "DR Kongo", "Congo": "Kongo",
    "Jordan": "Jordanien", "Bahrain": "Bahrain", "Oman": "Oman", "Kuwait": "Kuwait",
}

# Case-insensitiver Index für robustes Nachschlagen
_CI = {k.lower(): v for k, v in TEAM_DE.items()}


def de_name(name):
    if not name:
        return name
    n = name.strip()
    return TEAM_DE.get(n) or _CI.get(n.lower()) or name
