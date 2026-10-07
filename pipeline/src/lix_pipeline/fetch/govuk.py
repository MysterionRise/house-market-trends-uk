"""GOV.UK publication pages: find an attachment's current URL via the content API.

Asset URLs (assets.publishing.service.gov.uk/media/<id>/...) change whenever a file is
republished, but the publication page path stays put.
"""

import re

import requests

from lix_core.config import GovukAttachmentAccess
from lix_pipeline.fetch.dates import find_date

CONTENT_API = "https://www.gov.uk/api/content"


def resolve_attachment(access: GovukAttachmentAccess, session: requests.Session) -> dict:
    """Return the lock "resolved" section for the attachment matching ``attachment_regex``."""
    resp = session.get(f"{CONTENT_API}/{access.path.strip('/')}", timeout=(30, 60))
    resp.raise_for_status()
    page = resp.json()
    attachments = page.get("details", {}).get("attachments", [])
    matches = [
        a
        for a in attachments
        if re.search(access.attachment_regex, a.get("url", ""))
        or re.search(access.attachment_regex, a.get("filename", "") or "")
    ]
    if access.pick == "latest" and matches:
        dated = [(find_date(a.get("url", "")), a) for a in matches]
        undated = [a.get("url") for d, a in dated if d is None]
        if undated:
            raise RuntimeError(f"Can't read a date from {undated}; tighten attachment_regex")
        matches = [max(dated, key=lambda pair: pair[0])[1]]
    if len(matches) != 1:
        found = [a.get("url") for a in attachments]
        raise RuntimeError(
            f"Expected one attachment matching {access.attachment_regex!r} on "
            f"gov.uk/{access.path}, found {len(matches)}. Attachments: {found[:20]}"
        )
    att = matches[0]
    return {
        "url": att["url"],
        "title": att.get("title"),
        "modified": page.get("public_updated_at"),
    }
