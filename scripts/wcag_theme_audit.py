import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from gui.theme_tokens import THEME_TOKENS


def parse_rgba(value):
    v = value.strip().lower()
    if v.startswith("#"):
        s = v[1:]
        if len(s) == 3:
            r = int(s[0] * 2, 16)
            g = int(s[1] * 2, 16)
            b = int(s[2] * 2, 16)
            return r, g, b, 1.0
        if len(s) == 6:
            r = int(s[0:2], 16)
            g = int(s[2:4], 16)
            b = int(s[4:6], 16)
            return r, g, b, 1.0
    if v.startswith("rgba(") and v.endswith(")"):
        parts = [p.strip() for p in v[5:-1].split(",")]
        return int(parts[0]), int(parts[1]), int(parts[2]), float(parts[3])
    raise ValueError(value)


def srgb_to_linear(c):
    x = c / 255.0
    if x <= 0.04045:
        return x / 12.92
    return ((x + 0.055) / 1.055) ** 2.4


def luminance(rgb):
    r, g, b = rgb
    return 0.2126 * srgb_to_linear(r) + 0.7152 * srgb_to_linear(g) + 0.0722 * srgb_to_linear(b)


def contrast_ratio(c1, c2):
    l1 = luminance(c1)
    l2 = luminance(c2)
    light = max(l1, l2)
    dark = min(l1, l2)
    return (light + 0.05) / (dark + 0.05)


def blend(fg_rgba, bg_rgb):
    fr, fg, fb, fa = fg_rgba
    br, bg, bb = bg_rgb
    r = int(round(fr * fa + br * (1.0 - fa)))
    g = int(round(fg * fa + bg * (1.0 - fa)))
    b = int(round(fb * fa + bb * (1.0 - fa)))
    return r, g, b


def audit_theme(theme_name, backdrop):
    t = THEME_TOKENS[theme_name]
    rows = []
    checks = [
        ("panel-default", "text_primary", "bg_panel"),
        ("panel-hover", "text_primary", "bg_panel_hover"),
        ("panel-focus", "text_primary", "bg_panel_focus"),
        ("panel-disabled", "text_muted", "bg_panel_disabled"),
        ("button-default", "text_button", "bg_button"),
        ("button-hover", "text_button", "bg_button_hover"),
        ("button-focus", "text_button", "bg_button_focus"),
        ("button-disabled", "text_muted", "bg_button_disabled"),
    ]
    for name, fg_key, bg_key in checks:
        fg = parse_rgba(t[fg_key])
        bg = parse_rgba(t[bg_key])
        blended_bg = blend(bg, backdrop)
        ratio = contrast_ratio((fg[0], fg[1], fg[2]), blended_bg)
        rows.append((name, fg_key, t[fg_key], bg_key, t[bg_key], ratio, "PASS" if ratio >= 4.5 else "FAIL"))
    return rows


def write_report(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    backdrops = {"light": (243, 244, 246), "dark": (15, 23, 42)}
    lines = []
    lines.append("# Translucent Theme Tokens and WCAG Audit")
    lines.append("")
    for theme_name in ("light", "dark"):
        lines.append(f"## Theme: {theme_name}")
        lines.append("")
        lines.append("| State | Foreground Token | Foreground | Background Token | Background | Contrast | WCAG AA |")
        lines.append("|---|---|---|---|---|---:|---|")
        for row in audit_theme(theme_name, backdrops[theme_name]):
            state, fg_key, fg_val, bg_key, bg_val, ratio, status = row
            lines.append(f"| {state} | {fg_key} | `{fg_val}` | {bg_key} | `{bg_val}` | {ratio:.2f}:1 | {status} |")
        lines.append("")
        lines.append("### Token Table")
        lines.append("")
        lines.append("| Token | Value |")
        lines.append("|---|---|")
        for k, v in THEME_TOKENS[theme_name].items():
            lines.append(f"| {k} | `{v}` |")
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    base_dir = BASE_DIR
    out_file = os.path.join(base_dir, "artifacts", "theme", "wcag_report.md")
    write_report(out_file)
