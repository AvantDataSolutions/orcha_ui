from __future__ import annotations

import reflex as rx

from orcha_ui.constants import NAV_ITEMS, USER_LABEL


def app_shell(*, active_route: str, page_title: str, page_description: str, content: rx.Component) -> rx.Component:
    return rx.box(
        rx.hstack(
            _sidebar(active_route),
            rx.box(
                rx.vstack(
                    rx.box(
                        rx.heading(page_title, size="7", color="#0f172a"),
                        rx.text(page_description, color="#475569", size="2"),
                        background="linear-gradient(135deg, rgba(8,145,178,0.14), rgba(15,23,42,0.02))",
                        border="1px solid rgba(8,145,178,0.15)",
                        border_radius="24px",
                        padding="1.05rem 1.15rem",
                        width="100%",
                    ),
                    content,
                    spacing="4",
                    align_items="stretch",
                    width="100%",
                ),
                flex="1",
                padding="1rem 1.1rem 1.5rem 0.85rem",
                overflow="auto",
                min_height="100vh",
            ),
            spacing="0",
            width="100%",
            min_height="100vh",
            align="stretch",
        ),
        width="100%",
    )


def _sidebar(active_route: str) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.link(
                rx.hstack(
                    rx.image(src="/orcha-logo-round.png", width="58px", height="58px", object_fit="contain"),
                    rx.image(src="/orcha-font-black.png", width="138px", height="auto", object_fit="contain"),
                    spacing="3",
                    align="center",
                    width="100%",
                ),
                href="/overview",
                text_decoration="none",
            ),
            rx.text(USER_LABEL, color="#64748b", size="1"),
            rx.vstack(*[_nav_item(item, active_route) for item in NAV_ITEMS], spacing="1", width="100%"),
            rx.spacer(),
            rx.box(
                rx.text("Reflex Migration", size="2", color="#0891b2", text_transform="uppercase", letter_spacing="0.08em"),
                rx.text("Orcha operational UI rebuilt on Reflex.", color="#475569", size="2"),
                background_color="rgba(255,255,255,0.72)",
                border="1px solid rgba(148,163,184,0.22)",
                border_radius="18px",
                padding="0.85rem 0.9rem",
                width="100%",
            ),
            spacing="3",
            align_items="stretch",
            width="100%",
        ),
        width="248px",
        min_width="248px",
        min_height="100vh",
        padding="1rem 0.8rem",
        border_right="1px solid rgba(148,163,184,0.16)",
        background="linear-gradient(180deg, #ffffff 0%, #f8fafc 55%, #eff6ff 100%)",
        position="sticky",
        top="0",
    )


def _nav_item(item: dict[str, str], active_route: str) -> rx.Component:
    is_active = active_route == item["route"]
    return rx.link(
        rx.hstack(
            rx.image(src=item["image"], width="2rem", height="2rem", border_radius="12px"),
            rx.vstack(
                rx.text(item["name"], color="#0f172a", weight="medium", size="2"),
                rx.text(item["description"], color="#64748b", size="1"),
                spacing="0",
                align_items="start",
            ),
            spacing="2",
            width="100%",
            align="center",
        ),
        href=item["route"],
        text_decoration="none",
        background_color="#e0f2fe" if is_active else "transparent",
        border="1px solid rgba(14,165,233,0.24)" if is_active else "1px solid transparent",
        border_left="3px solid #0284c7" if is_active else "3px solid transparent",
        border_radius="16px",
        padding="0.55rem 0.65rem",
        width="100%",
        transition="all 0.18s ease",
        _hover={
            "background_color": "rgba(226, 232, 240, 0.55)",
            "border": "1px solid rgba(148,163,184,0.22)",
        },
    )