from __future__ import annotations

import reflex as rx

from orcha_ui.components.common import empty_state, metric, section_card, tone_badge
from orcha_ui.components.layout import app_shell
from orcha_ui.state import KvdbState


def _entry_row(entry: dict) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading(entry["key"], size="4", color="#0f172a"),
                rx.spacer(),
                tone_badge(entry["row_tone"], entry["row_tone"]),
                width="100%",
                align="center",
            ),
            rx.text(entry["preview"], color="#475569", size="2"),
            rx.flex(
                metric("Type", entry["type"], "blue"),
                metric("Encrypted", entry["encrypted"], "slate"),
                metric("Size", entry["size"], "slate"),
                metric("Expiry", entry["expiry"], "slate"),
                metric("TTL", entry["ttl"], "slate"),
                wrap="wrap",
                gap="0.8rem",
                width="100%",
            ),
            rx.button("Select in Editor", on_click=KvdbState.select_key(entry["key"]), variant="soft", color_scheme="gray"),
            spacing="3",
            align_items="stretch",
            width="100%",
        ),
        width="100%",
        padding="1rem",
        border_radius="20px",
        border="1px solid rgba(148, 163, 184, 0.18)",
        background_color="rgba(255,255,255,0.9)",
    )


def _metadata_metric(item: dict) -> rx.Component:
    return metric(item["label"], item["value"], "slate")


def kvdb_page() -> rx.Component:
    content = rx.vstack(
        section_card(
            rx.flex(
                rx.box(
                    rx.text("Search", size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
                    rx.input(value=KvdbState.search_text, on_change=KvdbState.set_search_text, placeholder="partial_key", width="100%"),
                    flex="1",
                    min_width="18rem",
                ),
                rx.box(
                    rx.text("Limit", size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
                    rx.input(value=KvdbState.limit_text, on_change=KvdbState.set_limit_text, type="number", width="8rem"),
                ),
                rx.box(
                    rx.text("Flags", size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
                    rx.checkbox("Include expired", checked=KvdbState.include_expired, on_change=KvdbState.toggle_include_expired),
                ),
                wrap="wrap",
                gap="1rem",
                width="100%",
            ),
            title="KVDB Explorer",
            subtitle="Browse stored keys, inspect serialized values, and manage expiry or encryption settings.",
        ),
        rx.flex(
            section_card(
                rx.cond(
                    KvdbState.has_entries,
                    rx.box(
                        rx.vstack(
                            rx.foreach(KvdbState.entries, _entry_row),
                            spacing="3",
                            width="100%",
                            align_items="stretch",
                        ),
                        max_height="44rem",
                        overflow="auto",
                        width="100%",
                    ),
                    empty_state("No Keys Found", "No KVDB entries matched the current listing filters."),
                ),
                title="Stored Entries",
                subtitle="Current keys discovered from the backing KVDB store.",
            ),
            section_card(
                rx.box(
                    rx.text("Known Keys", size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
                    rx.select(KvdbState.key_items, value=KvdbState.selected_key, on_change=KvdbState.select_key, placeholder="Select a key", width="100%"),
                    width="100%",
                ),
                rx.box(
                    rx.text("Key", size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
                    rx.input(value=KvdbState.key_input, on_change=KvdbState.set_key_input, placeholder="my_key_identifier", width="100%"),
                    width="100%",
                ),
                rx.box(
                    rx.text("Value", size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
                    rx.text_area(value=KvdbState.value_text, on_change=KvdbState.set_value_text, min_height="18rem", resize="vertical", width="100%"),
                    width="100%",
                ),
                rx.flex(
                    rx.box(
                        rx.text("Value Format", size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
                        rx.select(["json", "string", "int", "float", "bool"], value=KvdbState.value_mode, on_change=KvdbState.set_value_mode, width="100%"),
                        flex="1",
                    ),
                    rx.box(
                        rx.text("Expiry Minutes", size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
                        rx.input(value=KvdbState.expiry_minutes_text, on_change=KvdbState.set_expiry_minutes_text, type="number", width="100%"),
                        flex="1",
                    ),
                    wrap="wrap",
                    gap="1rem",
                    width="100%",
                ),
                rx.box(
                    rx.text("Encryption Key", size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
                    rx.input(value=KvdbState.encryption_key, on_change=KvdbState.set_encryption_key, type="password", placeholder="Optional encryption key", width="100%"),
                    width="100%",
                ),
                rx.hstack(
                    rx.button("Load", on_click=KvdbState.load_entry, variant="soft", color_scheme="gray"),
                    rx.button("Save", on_click=KvdbState.save_entry, color_scheme="cyan"),
                    rx.button("Delete", on_click=KvdbState.delete_entry, color_scheme="red"),
                    spacing="3",
                ),
                rx.flex(
                    rx.foreach(KvdbState.metadata, _metadata_metric),
                    wrap="wrap",
                    gap="0.8rem",
                    width="100%",
                ),
                title="Entry Editor",
                subtitle="Load, edit, encrypt, expire, and delete a selected KVDB entry.",
            ),
            gap="1rem",
            wrap="wrap",
            width="100%",
            align="start",
        ),
        spacing="3",
        width="100%",
        align_items="stretch",
    )
    actions = rx.button("Refresh Listing", on_click=KvdbState.load, color_scheme="cyan", size="2")
    return app_shell(
        active_route="/kvdb",
        page_title="KVDB Explorer",
        page_description="Inspect persisted KVDB records, preview values, and manage key-level metadata.",
        content=content,
        actions=actions,
    )


__all__ = ["kvdb_page"]