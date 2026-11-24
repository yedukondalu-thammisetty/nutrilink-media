"""Find the 3D Fluent emoji image (tools/icons/fluent3d) for an emoji character."""
import base64
import pathlib

DIR = pathlib.Path(__file__).resolve().parent / "icons" / "fluent3d"
FALLBACK = "1f33f"  # 🌿 herb


def _candidates(emoji):
    cps = [f"{ord(ch):x}" for ch in emoji]
    yield "-".join(cps)
    no_vs = [c for c in cps if c != "fe0f"]
    yield "-".join(no_vs)
    # some files keep fe0f only after the first code point (e.g. 1f3cb-fe0f-200d-2640-fe0f)
    if no_vs:
        yield "-".join([no_vs[0], "fe0f"] + no_vs[1:])
        yield "-".join([no_vs[0], "fe0f"] + [x for c in no_vs[1:] for x in ([c, "fe0f"] if c in ("2640", "2642") else [c])])
    yield no_vs[0] if no_vs else FALLBACK


def icon_path(emoji):
    """Return (path, found) for an emoji. found is False when the fallback herb icon is used."""
    for name in _candidates(emoji.strip()):
        p = DIR / f"{name}.webp"
        if p.exists():
            return p, True
    return DIR / f"{FALLBACK}.webp", False


def icon_uri(emoji):
    p, ok = icon_path(emoji)
    return "data:image/webp;base64," + base64.b64encode(p.read_bytes()).decode(), ok
