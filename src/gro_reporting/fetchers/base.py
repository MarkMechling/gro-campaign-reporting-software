"""Abstrakte Basisklasse fuer alle Fetcher."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date


class BaseFetcher(ABC):
    @abstractmethod
    def fetch(self, date_from: date, date_to: date):
        ...
