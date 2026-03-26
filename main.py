from openai import OpenAI
from key import OPENAI_API_KEY

from takeoff.config import AppConfig
from takeoff.pipeline import run_symbol_detection_for_page, prepare_page_shared_assets
from takeoff.symbol_library_manager import (
    load_symbol_library,
    save_symbol_library,
    ensure_symbol_in_library,
)


def main():
    client = OpenAI(api_key=OPENAI_API_KEY)

    config = AppConfig(
        pdf_path="house_plans.pdf",
        page_index=4,
        model_name="gpt-5.4",
        plan_name="default_plan",
        symbol_name="Bath Fan",
    )

    # Load existing library
    library = load_symbol_library(config)

    # Ensure symbols from the electrical legend exist
    bath_fan = ensure_symbol_in_library(library, "Bath Fan")
    light_flush_mount = ensure_symbol_in_library(library, "Light Flush Mount")
    light_recessed = ensure_symbol_in_library(library, "Light Recessed")
    light_strip = ensure_symbol_in_library(library, "Light Strip")
    light_wall_mount = ensure_symbol_in_library(library, "Light Wall Mount")
    plug_110 = ensure_symbol_in_library(library, "Plug 110")
    plug_220 = ensure_symbol_in_library(library, "Plug 220")
    switch = ensure_symbol_in_library(library, "Switch")

    # ------------------------------------------------------------
    # Symbol-specific detection overrides
    # ------------------------------------------------------------

    # Plug 110 can appear rotated on the plan, so allow 4 rotations
    # and make proposal generation more aggressive.
    plug_110.metadata["detection_overrides"] = {
        "template_rotations": [0, 90, 180, 270],
        "edge_proposal_threshold": 0.24,
        "max_edge_proposals_per_scale": 120,
        "proposal_scales": (0.80, 0.90, 1.00, 1.10, 1.20),
        "final_scales": (0.85, 1.00, 1.15),
    }

    # Switch is simple/small, so also allow rotations and loosen proposals.
    switch.metadata["detection_overrides"] = {
        "template_rotations": [0, 90, 180, 270],
        "edge_proposal_threshold": 0.22,
        "max_edge_proposals_per_scale": 140,
        "proposal_scales": (0.80, 0.90, 1.00, 1.10, 1.20),
        "final_scales": (0.85, 1.00, 1.15),
    }

    # Light wall mount gave a false positive, so keep it conservative for now.
    light_wall_mount.metadata["detection_overrides"] = {
        "template_rotations": [0],
        "edge_proposal_threshold": 0.34,
        "max_edge_proposals_per_scale": 50,
    }

    # Save library in case symbols were added or metadata changed
    save_symbol_library(library, config)

    # Prepare shared page assets ONCE
    shared_page_assets = prepare_page_shared_assets(client, config)

    results = []

    print("\nRunning symbol detection...\n")

    for symbol in library.enabled_symbols():
        print(f"\n==============================")
        print(f"Processing symbol: {symbol.name}")
        print(f"==============================")

        result = run_symbol_detection_for_page(
            client=client,
            config=config,
            symbol=symbol,
            shared_page_assets=shared_page_assets,
        )

        results.append(result)

    # Save library again in case templates were created or metadata updated
    save_symbol_library(library, config)

    print("\n========== PAGE SUMMARY ==========")

    for r in results:
        print(f'{r["symbol_name"]}: {r["match_count_inside_plan_outside_legend"]}')

    print("==================================\n")
    print("Done.")


if __name__ == "__main__":
    main()