"""GOV.UK publication pages: find an attachment's current URL via the content API.

Asset URLs (assets.publishing.service.gov.uk/media/<id>/...) change whenever a file is
republished, but the publication page path stays put.
"""

import re

import requests

from lix_core.config import GovukAttachmentAccess

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
    if len(matches) != 1:
        found = [a.get("url") for a in attachments]
        raise RuntimeError(
            f"Expected one attachment matching {access.attachment_regex!r} on "
            f"gov.uk/{access.path}, found {len(matches)}. Attachments: {found}"
        )
    att = matches[0]
    return {
        "url": att["url"],
        "title": att.get("title"),
        "modified": page.get("public_updated_at"),
    }
