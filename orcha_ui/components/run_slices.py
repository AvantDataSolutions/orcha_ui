from typing import Any

import reflex as rx


def compact_run_strip(data: Any) -> rx.Component:
    return rx.cond(
        data["has_segments"],
        rx.box(
            rx.flex(
                rx.foreach(data["segments"], _render_segment),
                wrap="nowrap",
                spacing="0",
                width="100%",
                height="100%",
                align="stretch",
            ),
            width="100%",
            height="1.85rem",
            border="1px solid rgba(148, 163, 184, 0.22)",
            border_radius="16px",
            overflow="hidden",
            background="linear-gradient(180deg, rgba(248,250,252,0.98), rgba(226,232,240,0.65))",
            box_shadow="inset 0 1px 0 rgba(255,255,255,0.85), 0 4px 12px rgba(15,23,42,0.05)",
        ),
        _empty_strip(data["empty_text"]),
    )


def timeline_strip(data: Any) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            _timeline_label(data["start_label"]),
            rx.spacer(),
            _timeline_label(data["end_label"]),
            width="100%",
            align="center",
        ),
        rx.cond(
            data["has_segments"],
            rx.box(
                rx.flex(
                    rx.foreach(data["segments"], _render_segment),
                    wrap="nowrap",
                    spacing="0",
                    width="100%",
                    height="100%",
                    align="stretch",
                ),
                width="100%",
                height="2rem",
                border="1px solid rgba(15,23,42,0.12)",
                border_radius="18px",
                overflow="hidden",
                background="linear-gradient(180deg, rgba(248,250,252,0.96), rgba(226,232,240,0.58))",
                box_shadow="inset 0 1px 0 rgba(255,255,255,0.8), 0 10px 22px rgba(15,23,42,0.05)",
            ),
            _empty_strip(data["empty_text"]),
        ),
        spacing="1",
        width="100%",
    )


def _render_segment(segment: Any) -> rx.Component:
    # Run segments always have both a tooltip and an href; gap segments have neither.
    # So checking tooltip presence is sufficient to distinguish them.
    #
    # The width/min-width MUST live on the flex item itself. For a run segment the
    # flex item is the <a> the hover-card trigger renders via `as_child` — not the
    # inner box. Sizing the nested box makes its width resolve against an auto-width
    # parent and collapse to min-content, which is why the strips looked empty and
    # the timeline runs sat in the wrong place. So the link carries the size and the
    # box just fills it.
    run_box = rx.box(
        width="100%",
        height="100%",
        background_color=segment["color"],
        border_right="1px solid rgba(255,255,255,0.32)",
        box_shadow="inset 0 1px 0 rgba(255,255,255,0.22)",
        cursor="pointer",
        transition="filter 0.15s ease",
        _hover={"filter": "brightness(1.12) saturate(1.05)"},
    )

    gap_box = rx.box(
        width=segment["width"],
        min_width=segment["min_width"],
        height="100%",
        background_color=segment["color"],
        flex_shrink="0",
    )

    return rx.cond(
        segment["tooltip"] != "",
        rx.hover_card.root(
            rx.hover_card.trigger(
                rx.link(
                    run_box,
                    href=segment["href"],
                    text_decoration="none",
                    display="block",
                    width=segment["width"],
                    min_width=segment["min_width"],
                    height="100%",
                    flex_shrink="0",
                ),
                as_child=True,
                height="100%",
                display="block",
            ),
            rx.hover_card.content(
                rx.text(
                    segment["tooltip"],
                    size="1",
                    color="#1e293b",
                    white_space="pre-line",
                    font_family="'IBM Plex Mono', monospace",
                    line_height="1.7",
                ),
                side="top",
                side_offset=7,
                background_color="white",
                border="1px solid rgba(148,163,184,0.22)",
                border_radius="14px",
                box_shadow="0 16px 40px rgba(15,23,42,0.13), 0 2px 8px rgba(15,23,42,0.06)",
                padding="0.65rem 0.85rem",
                max_width="26rem",
            ),
        ),
        gap_box,
    )


def _empty_strip(text: str | rx.Var) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.box(
                width="0.45rem",
                height="0.45rem",
                border_radius="999px",
                background="linear-gradient(180deg, #cbd5e1, #94a3b8)",
                flex_shrink="0",
            ),
            rx.text(text, color="#94a3b8", size="2", margin="0"),
            spacing="2",
            align="center",
        ),
        width="100%",
        padding="0.35rem 0.55rem",
        border="1px dashed rgba(148, 163, 184, 0.32)",
        border_radius="14px",
        background="linear-gradient(180deg, rgba(248,250,252,0.92), rgba(241,245,249,0.78))",
    )


def _timeline_label(text: str | rx.Var) -> rx.Component:
    return rx.box(
        rx.text(text, size="1", color="#475569", margin="0"),
        padding="0.12rem 0.45rem",
        border_radius="999px",
        background_color="rgba(255,255,255,0.75)",
        border="1px solid rgba(148,163,184,0.2)",
        box_shadow="0 2px 10px rgba(15,23,42,0.04)",
    )
