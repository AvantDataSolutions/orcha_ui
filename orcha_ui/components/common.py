from typing import Any

import reflex as rx


_TONE_STYLES = {
    "blue": {"background": "#dbeafe", "color": "#1d4ed8", "border": "#93c5fd"},
    "green": {"background": "#dcfce7", "color": "#166534", "border": "#86efac"},
    "red": {"background": "#fee2e2", "color": "#b91c1c", "border": "#fca5a5"},
    "amber": {"background": "#fef3c7", "color": "#b45309", "border": "#fcd34d"},
    "purple": {"background": "#ede9fe", "color": "#6d28d9", "border": "#c4b5fd"},
    "slate": {"background": "#e2e8f0", "color": "#334155", "border": "#cbd5e1"},
}


def section_card(
    *children: rx.Component,
    title: str,
    subtitle: str | rx.Var | None = None,
    actions: rx.Component | None = None,
) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.heading(title, size="4"),
                    rx.text(subtitle, color="#64748b", size="2") if subtitle is not None else rx.fragment(),
                    spacing="0",
                    align_items="start",
                ),
                rx.spacer(),
                actions if actions is not None else rx.fragment(),
                width="100%",
                align="start",
            ),
            *children,
            spacing="1",
            align_items="stretch",
            width="100%",
        ),
        background_color="white",
        border="1px solid rgba(148, 163, 184, 0.22)",
        border_radius="20px",
        box_shadow="0 16px 36px rgba(15, 23, 42, 0.06)",
        padding="0.95rem 1.05rem",
        width="100%",
    )


def tone_badge(text: str | rx.Var, tone: str = "slate") -> rx.Component:
    def _badge(current_tone: str) -> rx.Component:
        style = _TONE_STYLES.get(current_tone, _TONE_STYLES["slate"])
        return rx.badge(
            text,
            background_color=style["background"],
            color=style["color"],
            border=f"1px solid {style['border']}",
            border_radius="999px",
            padding="0.25rem 0.55rem",
        )

    r = rx.match(
        tone,
        ("blue", _badge("blue")),
        ("green", _badge("green")),
        ("red", _badge("red")),
        ("amber", _badge("amber")),
        ("purple", _badge("purple")),
        _badge("slate"),
    )
    if isinstance(r, rx.Component):
        return r
    raise ValueError(f"Invalid tone: {tone}")


def banner(message: str | rx.Var, tone: str = "blue") -> rx.Component:
    def _banner(current_tone: str) -> rx.Component:
        style = _TONE_STYLES.get(current_tone, _TONE_STYLES["blue"])
        return rx.box(
            rx.text(message, size="2", weight="medium"),
            background_color=style["background"],
            color=style["color"],
            border=f"1px solid {style['border']}",
            border_radius="16px",
            padding="0.7rem 0.9rem",
            width="100%",
        )

    r = rx.match(
        tone,
        ("green", _banner("green")),
        ("red", _banner("red")),
        ("amber", _banner("amber")),
        ("purple", _banner("purple")),
        ("slate", _banner("slate")),
        _banner("blue"),
    )

    if isinstance(r, rx.Component):
        return r
    raise ValueError(f"Invalid tone: {tone}")


def detail_field(label: str | rx.Var, value: str | rx.Var, tone: str = "slate", code: bool | rx.Var = False) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
        rx.cond(
            code,
            pre_block(value, min_height="6rem"),
            tone_badge(value, tone),
        ),
        spacing="2",
        width="100%",
        align_items="start",
    )


def metric(label: str | rx.Var, value: str | rx.Var, tone: str = "slate") -> rx.Component:
    return rx.vstack(
        rx.text(
            label,
            size="2",
            color="#64748b",
            text_transform="uppercase",
            letter_spacing="0.06em",
            margin="5px",
            line_height="1.1",
        ),
        tone_badge(value, tone),
        spacing="0",
        width="100%",
        align_items="start",
    )


def pre_block(text: str | rx.Var, *, min_height: str = "12rem") -> rx.Component:
    return rx.box(
        rx.text(
            text,
            margin="0",
            white_space="pre-wrap",
            font_family="'IBM Plex Mono', monospace",
            font_size="0.82rem",
            line_height="1.55",
        ),
        background_color="#f8fafc",
        border_radius="20px",
        border="1px solid rgba(148, 163, 184, 0.2)",
        padding="1rem",
        width="100%",
        min_height=min_height,
        max_height="36rem",
        overflow="auto",
    )


def empty_state(title: str, body: str) -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading(title, size="6"),
            rx.text(body, color="#64748b"),
            spacing="3",
            align="center",
        ),
        width="100%",
        min_height="14rem",
        border="1px dashed rgba(148, 163, 184, 0.5)",
        border_radius="22px",
        background_color="rgba(255, 255, 255, 0.75)",
    )


def legend_chip(label: str | rx.Var, color: str | rx.Var) -> rx.Component:
    return rx.hstack(
        rx.box(width="14px", height="14px", background_color=color, border_radius="4px", border="1px solid rgba(15,23,42,0.15)"),
        rx.text(label, size="2"),
        spacing="2",
        align="center",
        padding="0.15rem 0.25rem",
        border_radius="999px",
        background_color="rgba(255,255,255,0.55)",
    )


def filter_chip(label: str | rx.Var, active: bool | rx.Var, on_click: Any) -> rx.Component:
    return rx.button(
        label,
        on_click=on_click,
        size="2",
        variant=rx.cond(active, "solid", "soft"),
        color_scheme=rx.cond(active, "cyan", "gray"),
        border_radius="999px",
        cursor="pointer",
    )


def overlay_panel(
    *,
    is_open: bool | rx.Var,
    title: str,
    body: rx.Component,
    confirm_label: str,
    confirm_color: str,
    on_confirm: Any,
    on_cancel: Any,
) -> rx.Component:
    return rx.cond(
        is_open,
        rx.box(
            rx.center(
                rx.box(
                    rx.vstack(
                        rx.heading(title, size="6"),
                        body,
                        rx.hstack(
                            rx.spacer(),
                            rx.button("Cancel", variant="soft", color_scheme="gray", on_click=on_cancel),
                            rx.button(confirm_label, color_scheme=confirm_color, on_click=on_confirm),
                            width="100%",
                        ),
                        spacing="4",
                        align_items="stretch",
                    ),
                    background_color="white",
                    border_radius="24px",
                    border="1px solid rgba(148,163,184,0.25)",
                    box_shadow="0 32px 80px rgba(15, 23, 42, 0.22)",
                    padding="1.35rem",
                    max_width="32rem",
                    width="100%",
                ),
                min_height="100vh",
                padding="1.5rem",
            ),
            position="fixed",
            inset="0",
            background_color="rgba(15, 23, 42, 0.42)",
            backdrop_filter="blur(6px)",
            z_index="1000",
            width="100vw",
            height="100vh",
        ),
        rx.fragment(),
    )