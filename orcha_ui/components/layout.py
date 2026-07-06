from __future__ import annotations

import reflex as rx

from orcha_ui.constants import APP_VERSION, APP_VERSION_TONE, NAV_ITEMS, USER_LABEL


def app_shell(
    *,
    active_route: str,
    page_title: str,
    page_description: str,
    content: rx.Component,
    actions: rx.Component | None = None,
) -> rx.Component:
    return rx.box(
        rx.hstack(
            _sidebar(active_route),
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.vstack(
                            rx.heading(page_title, size="6", color="#0f172a", weight="bold"),
                            rx.text(page_description, color="#64748b", size="2"),
                            spacing="1",
                            align_items="start",
                        ),
                        rx.spacer(),
                        actions if actions is not None else rx.fragment(),
                        width="100%",
                        align="center",
                        padding_bottom="0.6rem",
                        border_bottom="1px solid rgba(148,163,184,0.2)",
                    ),
                    content,
                    spacing="3",
                    align_items="stretch",
                    width="100%",
                ),
                flex="1",
                padding="1.1rem 1.1rem 1.5rem 1rem",
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


def _version_badge() -> rx.Component:
    return rx.hstack(
        rx.text(APP_VERSION, color="#475569", weight="bold", size="1"),
        rx.cond(
            APP_VERSION_TONE != "",
            rx.text(APP_VERSION_TONE, color="#b45309", weight="medium", size="1"),
            rx.fragment(),
        ),
        spacing="2",
        align="baseline",
    )


def _sidebar(active_route: str) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.link(
                rx.hstack(
                    rx.image(src="/orcha-logo-round.png", width="52px", height="52px", object_fit="contain"),
                    rx.image(src="/orcha-font-black.png", width="130px", height="auto", object_fit="contain"),
                    spacing="3",
                    align="center",
                    width="100%",
                ),
                href="/overview",
                text_decoration="none",
            ),
            rx.vstack(*[_nav_item(item, active_route) for item in NAV_ITEMS], spacing="1", width="100%"),
            rx.spacer(),
            rx.box(
                rx.text(USER_LABEL, color="#94a3b8", size="1"),
                border_top="1px solid rgba(148,163,184,0.18)",
                padding_top="0.65rem",
                width="100%",
            ),
            _version_badge(),
            spacing="4",
            align_items="stretch",
            width="100%",
        ),
        width="220px",
        min_width="220px",
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
            rx.image(src=item["image"], width="1.4rem", height="1.4rem", border_radius="8px"),
            rx.text(item["name"], color="#0f172a", weight="medium", size="2"),
            spacing="2",
            width="100%",
            align="center",
        ),
        href=item["route"],
        text_decoration="none",
        custom_attrs={"title": item["description"]},
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