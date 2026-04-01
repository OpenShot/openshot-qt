"""Map between UI track labels (Track 1 = bottom) and OpenShot layer numbers."""

from __future__ import annotations


def layers_sorted_by_number(layers):
    """Ascending by layer number; bottom UI track is first (lowest number)."""
    if not layers:
        return []
    return sorted(layers, key=lambda L: int(L.get("number") or 0))


def display_index_to_layer_number(display_1based: int, layers) -> int:
    """1-based UI index: Track 1 = lowest layer number (bottom row)."""
    asc = layers_sorted_by_number(layers)
    if not asc or not (1 <= display_1based <= len(asc)):
        raise ValueError(f"display track index {display_1based} out of range")
    return int(asc[display_1based - 1].get("number") or 0)


def layer_number_to_display_index(layer_num: int, layers) -> int | None:
    """Return 1-based UI track index for this layer number, or None if unknown."""
    asc = layers_sorted_by_number(layers)
    try:
        idx = next(
            i
            for i, L in enumerate(asc)
            if int(L.get("number") or 0) == int(layer_num)
        )
    except StopIteration:
        return None
    return idx + 1


def normalize_track_or_layer_arg(raw: str, layers) -> tuple[int | None, str | None]:
    """
    Resolve user/LLM track input to storage layer number.
    Returns (layer_number, None) on success; filter omitted when raw is "" -> (None, None).
    On failure returns (None, error_message).
    If raw matches both a layer number and a display index, the layer number wins.
    """
    raw = (raw or "").strip()
    if not raw:
        return None, None
    layers = layers or []
    try:
        n = int(float(raw))
    except ValueError:
        return None, f"Error: Invalid track/layer value {raw!r}."
    numbers = {int(L.get("number") or 0) for L in layers}
    if n in numbers:
        return n, None
    if layers and 1 <= n <= len(layers):
        try:
            return display_index_to_layer_number(n, layers), None
        except ValueError:
            return None, f"Error: Unknown track index {n}."
    if not layers:
        return None, "Error: No tracks in project."
    return (
        None,
        f"Error: Unknown track or layer {raw!r}. Call list_layers_tool for id/number/ui_track mapping.",
    )


def format_track_label_for_llm(layer_num: int, layers) -> str:
    """e.g. '1000000 (UI: Track 1)' or plain number if unmapped."""
    ui = layer_number_to_display_index(layer_num, layers)
    if ui is not None:
        return f"{layer_num} (UI: Track {ui})"
    return str(layer_num)
