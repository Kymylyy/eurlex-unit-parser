"""Label parsing utilities used by the parser."""

import re

PARAGRAPH_NUM_RE = re.compile(r"^(\d+)\.\s*")
POINT_LABEL_RE = re.compile(r"^\(?([a-z]{1,2})\)?$", re.IGNORECASE)
SUBPOINT_LABEL_RE = re.compile(
    r"^\(?("
    r"i{1,3}|iv|v|vi{0,3}|ix|"
    r"x{1,3}|xi{0,3}|xiv|xv|xvi{0,3}|xix|"
    r"xxi{0,3}|xxiv|xxv|xxvi{0,3}|xxix|"
    r"xxxi{0,3}|xxxiv|xxxv|xxxvi{0,3}|xxxix"
    r")\)?$",
    re.IGNORECASE,
)
NUMERIC_LABEL_RE = re.compile(r"^\(?(\d+)\)?[.\)]?$")
DASH_LABEL_RE = re.compile(r"^[—–-]$")
QUOTE_CHARS = "'\u2018\u2019"


def normalize_label(label: str) -> tuple[str, str, bool]:
    """
    Normalize a label and determine its type.

    Returns: (normalized_label, label_type, is_quoted)
    label_type: 'paragraph', 'point', 'subpoint', 'numeric', 'dash', 'unknown'
    is_quoted: True if label started with quote.
    """
    label = label.strip()
    is_quoted = False

    if label and label[0] in QUOTE_CHARS:
        is_quoted = True
        label = label[1:].strip()

    m = PARAGRAPH_NUM_RE.match(label)
    if m and "(" not in label:
        return m.group(1), "paragraph", is_quoted

    m = NUMERIC_LABEL_RE.match(label)
    if m:
        return m.group(1), "numeric", is_quoted

    m = SUBPOINT_LABEL_RE.match(label)
    if m:
        return m.group(1).lower(), "subpoint", is_quoted

    m = POINT_LABEL_RE.match(label)
    if m:
        return m.group(1).lower(), "point", is_quoted

    if DASH_LABEL_RE.match(label):
        return "—", "dash", is_quoted

    return label, "unknown", is_quoted
