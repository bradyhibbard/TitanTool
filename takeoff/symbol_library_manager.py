import json
from pathlib import Path
from typing import Optional

from .models import SymbolLibrary, SymbolTemplate
from .config import AppConfig


def load_symbol_library(config: AppConfig) -> SymbolLibrary:
    """
    Load the symbol library from disk if it exists.
    Otherwise create a new empty one.
    """
    config.symbol_library_dir.mkdir(parents=True, exist_ok=True)

    json_path = config.symbol_library_json_path

    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        library = SymbolLibrary.from_dict(data)
        print(f"Loaded symbol library with {len(library.symbols)} symbols.")
        return library

    print("No existing symbol library found. Creating a new one.")
    return SymbolLibrary(plan_name=config.plan_name)


def save_symbol_library(library: SymbolLibrary, config: AppConfig):
    """
    Save the symbol library to disk.
    """
    config.symbol_library_dir.mkdir(parents=True, exist_ok=True)

    json_path = config.symbol_library_json_path

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(library.to_dict(), f, indent=2)

    print(f"Saved symbol library to: {json_path}")


def ensure_symbol_in_library(
    library: SymbolLibrary,
    symbol_name: str,
) -> SymbolTemplate:
    """
    Ensure a symbol exists in the library.
    If it doesn't exist, create it.
    """
    symbol = library.get_symbol_by_name(symbol_name)

    if symbol is not None:
        return symbol

    symbol = SymbolTemplate.from_name(symbol_name)
    library.add_symbol(symbol)

    print(f"Added new symbol to library: {symbol.name}")

    return symbol


def symbol_template_exists(symbol: SymbolTemplate) -> bool:
    """
    Check if the symbol template image already exists on disk.
    """
    if symbol.template_path is None:
        return False

    return Path(symbol.template_path).exists()