from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import FrameLocator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


ENV_FILE = Path(__file__).with_name(".env")


@dataclass(frozen=True)
class SiteConfig:
    login_url: str
    training_url: str
    open_lessons_button_index: int
    lesson_link_selector: str
    section_toggle_selector: str
    accordion_selector: str
    accordion_index: int
    # section_container_selector: str
    nested_accordion_selector: str
    nested_content_container_selector: str
    username_selector: str
    password_selector: str
    submit_selector: str


CONFIG = SiteConfig(
    login_url="https://computercenter.ops.education/login?returnUrl=%2f",
    training_url="https://computercenter.ops.education/training/trainee/training",
    open_lessons_button_index=3,
    lesson_link_selector='a[href="/Education/ViewLessonStructure.aspx?lang=el-GR&lessonID=18093&classID=25629"]',
    section_toggle_selector='a[href="#31538"]',
    accordion_selector='div.AccordionCard-header.AccordionLvl1 a[data-toggle="collapse"]',
    accordion_index=3,
    # section_container_selector='[id="31540"]',
    nested_accordion_selector='[id="31538"] div.AccordionCard-header.AccordionLvl2 a[data-toggle="collapse"]',
    nested_content_container_selector='[id="31545"]',
    username_selector='input[name="Input.Username"]',
    password_selector='input[name="Input.Password"]',
    submit_selector='button[type="submit"]',
)


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def is_login_page(page: Page, config: SiteConfig) -> bool:
    try:
        page.locator(config.username_selector).first.wait_for(state="visible", timeout=3_000)
        return True
    except PlaywrightTimeoutError:
        return "/login" in page.url.lower()


def perform_login(page: Page, config: SiteConfig, username: str, password: str) -> None:
    page.goto(config.login_url, wait_until="domcontentloaded")
    page.locator(config.username_selector).fill(username)
    page.locator(config.password_selector).fill(password)
    page.locator(config.submit_selector).click()
    page.wait_for_load_state("networkidle")


def click_accordion_card(page: Page, selector: str, index: int) -> None:
    accordion = page.locator(selector).nth(index)
    accordion.wait_for(state="visible", timeout=60_000)
    accordion.scroll_into_view_if_needed()
    accordion.click()


def click_first_nested_accordion(page: Page, selector: str) -> None:
    deadline = time.monotonic() + 60

    while time.monotonic() < deadline:
        accordion = page.locator(selector).nth(6)
        if accordion.count() > 0 and accordion.is_visible():
            accordion.scroll_into_view_if_needed()
            accordion.click()
            return

        page.wait_for_timeout(500)

    raise RuntimeError(
        f"Could not find a visible nested accordion for selector {selector} after waiting. "
        "Update the selector for this page structure."
    )


def click_first_content_link(page: Page, container_selector: str) -> None:
    deadline = time.monotonic() + 60

    while time.monotonic() < deadline:
        links = page.locator(f"{container_selector} a[href]")
        total_links = links.count()

        for index in range(total_links):
            link = links.nth(index)
            href = link.get_attribute("href") or ""

            if href.startswith("#") or href.lower().startswith("javascript:"):
                continue

            if link.is_visible():
                link.scroll_into_view_if_needed()
                link.click()
                return

        page.wait_for_timeout(500)

    raise RuntimeError(
        f"Could not find a visible content link inside {container_selector} after waiting. "
        "Update the selector for this page structure."
    )


def get_content_frame(page: Page) -> FrameLocator:
    content_frame = page.frame_locator("#ContentFrame")
    content_frame.locator("body").wait_for(state="visible", timeout=60_000)
    return content_frame


def click_button_in_content_frame(
    page: Page,
    selectors: tuple[str, ...],
    description: str,
    timeout_ms: int = 60_000,
) -> None:
    content_frame = get_content_frame(page)
    deadline = time.monotonic() + (timeout_ms / 1000)

    while time.monotonic() < deadline:
        for selector in selectors:
            locator = content_frame.locator(selector)
            count = locator.count()

            for index in range(count):
                candidate = locator.nth(index)
                if not candidate.is_visible():
                    continue

                candidate.scroll_into_view_if_needed()
                candidate.click(timeout=5_000)
                return

        page.wait_for_timeout(500)

    raise RuntimeError(f'Could not find a visible {description} button inside #ContentFrame.')


def main() -> None:
    load_env_file(ENV_FILE)

    username = os.getenv("SITE_USERNAME")
    password = os.getenv("SITE_PASSWORD")

    if not username or not password:
        raise RuntimeError(
            "Missing credentials. Set SITE_USERNAME and SITE_PASSWORD in the environment "
            "or in a local .env file."
        )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=False,
            args=[
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows",
                "--disable-background-media-suspend",
                "--no-default-browser-check",
                "--disable-dev-shm-usage",
            ],
        )
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        page.add_init_script(
            """
            Object.defineProperty(document, 'visibilityState', { get: () => 'visible' });
            Object.defineProperty(document, 'hidden', { get: () => false });
            document.hasFocus = () => true;
            document.addEventListener('visibilitychange', (e) => e.stopImmediatePropagation(), true);
            const originalRAF = window.requestAnimationFrame.bind(window);
            window.requestAnimationFrame = (cb) => originalRAF(cb);
            """
        )
        client = page.context.new_cdp_session(page)
        client.send("Emulation.setFocusEmulationEnabled", {"enabled": True})

        page.goto(CONFIG.training_url, wait_until="domcontentloaded")

        if is_login_page(page, CONFIG):
            print("Not logged in. Attempting login...")
            perform_login(page, CONFIG, username, password)

            if is_login_page(page, CONFIG):
                raise RuntimeError(
                    "Login attempt finished, but the page still looks like the login form. "
                    "Double-check your credentials or update the selectors."
                )
            print("Login successful.")
        else:
            print("Already logged in.")

        page.goto(CONFIG.training_url, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        print(f"Navigated to training page: {CONFIG.training_url}")

        page.locator("button").nth(CONFIG.open_lessons_button_index).click()
        page.wait_for_load_state("networkidle")
        print("Clicked the open lessons button.")
    
        page.locator(CONFIG.lesson_link_selector).click()
        page.wait_for_load_state("networkidle")
        print("Opened the lesson structure page.")

        page.locator(CONFIG.section_toggle_selector).click()
        page.wait_for_load_state("networkidle")
        print("Expanded the lesson section.")

        click_accordion_card(page, CONFIG.accordion_selector, CONFIG.accordion_index)
        page.wait_for_load_state("networkidle")
        print("Clicked the target accordion card.")

        click_first_nested_accordion(page, CONFIG.nested_accordion_selector)
        page.wait_for_load_state("networkidle")
        print("Clicked the first nested accordion card.")

        click_first_content_link(page, CONFIG.nested_content_container_selector)
        page.wait_for_load_state("networkidle")
        print("Clicked the first content link under the nested accordion.")

 
        for step in range(5):
            click_button_in_content_frame(
                page,
                (
                    'button.navigation-controls__button_next:has-text("Next")',
                    'button.uikit-primary-button_next:has-text("Next")',
                    'button:has-text("Next")',
                ),
                "Next",
            )
            page.wait_for_load_state("networkidle")
            print(f"Clicked Next button {step + 1}/5.")

            if step < 5:
                page.wait_for_timeout(3_600_000)

        page.locator('a.nav-link.nav-pill.avatar').click()
        page.wait_for_load_state("networkidle")
        print("Opened the avatar dropdown menu.")

        page.locator('a#ctl00_lnkbtnLogout').click()
        page.wait_for_load_state("networkidle")
        print("Clicked Logout.")

        page.wait_for_timeout(5_000)

        browser.close()


if __name__ == "__main__":
    main()
