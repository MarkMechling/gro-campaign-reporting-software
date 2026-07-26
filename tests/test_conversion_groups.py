"""Tests fuer Conversion-Gruppen: Matching, Metrik-Wahl, Rundung, Report-Kontext."""

from datetime import date
from decimal import Decimal

from gro_reporting.config import ClientConfig, ConversionGroupConfig
from gro_reporting.models import (
    ChannelData,
    ChannelScope,
    ReportData,
    aggregate_conversion_groups,
)
from gro_reporting.report.builder import ReportBuilder


def _sums(**actions):
    """Kurzform: Name -> (conversions, all_conversions)."""
    return {
        name: {"conversions": Decimal(str(c)), "all_conversions": Decimal(str(a))}
        for name, (c, a) in actions.items()
    }


def test_exact_and_wildcard_matching():
    groups = [
        ConversionGroupConfig(label="Kontakte", actions=["Klick E-Mail", "Klick Tel"]),
        ConversionGroupConfig(label="Lead-Formulare", actions=["Lead Form* send", "Lead Form* sent"]),
    ]
    sums = _sums(**{
        "Klick E-Mail": (5, 5),
        "Klick Tel": (2, 2),
        "Lead Formular send": (3, 3),
        "Lead Form sent": (1, 1),
        "Lead Form open": (99, 99),  # darf NICHT matchen
        "File Download": (100, 100),  # nicht konfiguriert
    })
    result = aggregate_conversion_groups(sums, groups)
    assert result == {"Kontakte": 7, "Lead-Formulare": 4}


def test_metric_all_conversions_for_secondary_actions():
    # Sekundaere Actions (z.B. Newsletter) zaehlen nur in all_conversions
    groups = [
        ConversionGroupConfig(
            label="Newsletter", actions=["Anmeldung Newsletter*"], metric="all_conversions"
        ),
        ConversionGroupConfig(label="Anfragen", actions=["Anmeldung Newsletter*"]),
    ]
    sums = _sums(**{"Anmeldung Newsletter": (0, 16)})
    result = aggregate_conversion_groups(sums, groups)
    assert result == {"Newsletter": 16, "Anfragen": 0}


def test_fractional_sums_rounded_once_per_group():
    # 0.4 + 0.4 = 0.8 -> 1 (haette man pro Action gerundet: 0 + 0 = 0)
    groups = [ConversionGroupConfig(label="Downloads", actions=["Download*"])]
    sums = _sums(**{"Download A": (0.4, 0.4), "Download B": (0.4, 0.4)})
    assert aggregate_conversion_groups(sums, groups) == {"Downloads": 1}


def test_no_matching_actions_yields_zero():
    groups = [ConversionGroupConfig(label="Kontakte", actions=["Klick Tel"])]
    assert aggregate_conversion_groups({}, groups) == {"Kontakte": 0}


def _report_data() -> ReportData:
    return ReportData(
        client_name="Test",
        slug="test",
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        channels=[
            ChannelData(name="Suchanzeigen", groups={"Kontakte": 7, "Downloads": 100}),
            ChannelData(name="Google PMAX Kampagnen", groups={"Kontakte": 3, "Downloads": 50}),
            ChannelData(name="Meta Anzeigen", groups={"Kontakte": 2, "Downloads": 0}),
        ],
        group_labels=["Kontakte", "Downloads"],
    )


def test_total_groups_sums_channels():
    assert _report_data().total_groups == {"Kontakte": 12, "Downloads": 150}


def test_for_scope_keeps_group_labels_and_filters_channels():
    scoped = _report_data().for_scope(ChannelScope.GOOGLE)
    assert scoped.group_labels == ["Kontakte", "Downloads"]
    assert scoped.total_groups == {"Kontakte": 10, "Downloads": 150}


def test_builder_context_uses_groups_when_configured():
    config = ClientConfig.model_validate({
        "client": {"name": "Test", "slug": "test"},
        "conversion_groups": [
            {"label": "Kontakte", "actions": ["x"]},
            {"label": "Downloads", "actions": ["y"]},
        ],
    })
    context = ReportBuilder(config, _report_data())._build_context()
    assert context["conv_group_labels"] == ["Kontakte", "Downloads"]
    assert context["conv_group_rows"][0] == {"name": "Suchanzeigen", "cells": ["7", "100"]}
    # PMAX wird wie in der Purchase-Tabelle abgekuerzt
    assert context["conv_group_rows"][1]["name"] == "PMAX"
    assert context["conv_group_total"] == {"name": "GESAMT", "cells": ["12", "150"]}


def test_builder_context_without_groups_falls_back_to_purchases():
    config = ClientConfig.model_validate({"client": {"name": "Test", "slug": "test"}})
    data = _report_data().model_copy(update={"group_labels": []})
    context = ReportBuilder(config, data)._build_context()
    assert context["conv_group_labels"] == []
    assert context["conv_rows"]  # Purchase-Tabelle weiterhin im Kontext
