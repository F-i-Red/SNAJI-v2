# -*- coding: utf-8 -*-
"""Configuração comum dos testes do SNAJI.

Garante que cada bateria de testes começa com o estado persistido LIMPO:
os ficheiros de dados criados em execuções anteriores (processos, casos,
configuração) são removidos antes dos testes correrem, para as contagens e
o seed serem determinísticos. Em produção estes ficheiros persistem — é
precisamente esse o seu papel; nos testes, recomeça-se do zero.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

_DB = Path(__file__).parent.parent / "app" / "db"

# A limpeza corre NO IMPORT do conftest — antes de o pytest coletar os módulos
# de teste (que, ao serem importados, instanciam os repositórios singleton e
# carregariam ficheiros de execuções anteriores).
for _nome in ("processos.json", "casos.json", "config.json"):
    _f = _DB / _nome
    if _f.exists():
        _f.unlink()


@pytest.fixture(scope="session", autouse=True)
def estado_limpo():
    """A limpeza real acontece no import (acima); a fixture existe para clareza."""
    yield
