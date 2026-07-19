import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_index_links_manifest_and_mobile_viewport_for_clock_subpath():
    html = read_text("index.html")

    assert '<link rel="manifest" href="/clock/manifest.json">' in html
    assert re.search(
        r'<meta\s+name="viewport"\s+content="[^"]*width=device-width[^"]*initial-scale=1[^"]*viewport-fit=cover[^"]*"',
        html,
    )
    assert '<meta name="mobile-web-app-capable" content="yes">' in html
    assert '<meta name="apple-mobile-web-app-title" content="Literature Clock">' in html


def test_manifest_is_installable_under_clock_path_with_png_icons_and_screenshots():
    manifest = json.loads(read_text("manifest.json"))

    assert manifest["id"] == "/clock/"
    assert manifest["start_url"] == "/clock/"
    assert manifest["scope"] == "/clock/"
    assert manifest["display"] == "standalone"
    assert manifest["theme_color"] == "#000000"
    assert manifest["background_color"] == "#000000"

    icons = manifest.get("icons", [])
    assert any(icon.get("src") == "/clock/docs/app-icon-512.png" and icon.get("sizes") == "512x512" for icon in icons)
    assert any("maskable" in icon.get("purpose", "") for icon in icons)
    assert all(icon.get("src", "").startswith("/clock/") for icon in icons)
    assert any(s.get("src") == "/clock/docs/screenshot-pwa-android.jpg" for s in manifest.get("screenshots", []))


def test_clock_registers_service_worker_for_clock_scope_after_dom_ready():
    js = read_text("js/clock.js")

    assert "navigator.serviceWorker.register('/clock/sw.js', { scope: '/clock/' })" in js
    assert js.index("serviceWorker") > js.index("async function init")


def test_service_worker_precaches_clock_assets_and_serves_offline_fallback():
    sw = read_text("sw.js")

    assert "'/clock/'" in sw
    assert "'/clock/index.html'" in sw
    assert "'/clock/css/style.css'" in sw
    assert "'/clock/js/clock.js'" in sw
    assert "'/clock/data/quotes.json'" in sw
    assert "'/clock/manifest.json'" in sw
    assert "'/clock/docs/app-icon-512.png'" in sw
    assert "event.request.mode === 'navigate'" in sw
    assert "caches.match('/clock/index.html')" in sw
    assert "cache.addAll(PRECACHE_URLS)" in sw


def test_mobile_css_uses_safe_areas_dynamic_viewport_and_touch_targets():
    css = read_text("css/style.css")

    assert "100dvh" in css
    assert "env(safe-area-inset-top)" in css
    assert "env(safe-area-inset-bottom)" in css
    assert "@media (max-width: 480px)" in css
    assert "overflow-y: auto" in css
    assert re.search(r"blockquote\s*\{[^}]*font-size:\s*clamp\(", css, re.S)
    assert re.search(r"blockquote\.long\s*\{[^}]*font-size:\s*clamp\(", css, re.S)
    assert re.search(r"footer\s+(?:a|button)|footer a,\s*#theme-toggle", css)
    assert "min-height: 44px" in css
    assert "flex-wrap: wrap" in css
