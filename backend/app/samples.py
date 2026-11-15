"""The three ready-made sample drafts for the Northwind Foods demo workspace.

Each draft deliberately contains planted errors so a first-time visitor sees the
review pipeline do real work immediately:

  linkedin_post  -> off-tone hype, prohibited terms, wrong product name,
                    contradicted protein fact, unsupported "#1 in India" claim
  ad             -> contradicted price, prohibited claims, missing ad disclaimer
  email          -> prohibited term, missing unsubscribe disclaimer

These are *inputs*, not expected outputs. Nothing here is a hardcoded finding.
"""
from __future__ import annotations

SAMPLES: list[dict[str, str]] = [
    {
        "key": "linkedin_post",
        "title": "LinkedIn launch post",
        "content_type": "social",
        "body": (
            "We're thrilled to announce that Northwind Harvest Oat Bars are now "
            "available across India! \U0001F389\n\n"
            "Made with oats, almonds, honey and sea salt, our bars are the cheapest "
            "wholesome snack you'll find. Northwind Harvest Oat Crunch bars deliver "
            "12g of protein per bar \u2014 perfect for busy mornings.\n\n"
            "We're the #1 oat bar brand in India, guaranteed to keep you full all day. "
            "Grab yours today!"
        ),
    },
    {
        "key": "ad",
        "title": "Print ad \u2014 morning fuel",
        "content_type": "ad",
        "body": (
            "Northwind Harvest Oat Bars. Fuel your morning.\n\n"
            "6g of protein per bar. Made with oats, almonds, honey and sea salt. "
            "No palm oil, ever.\n\n"
            "Now just \u20b9199 for a pack of 6 \u2014 our best price this season. "
            "Order at northwindfoods.example.\n\n"
            "100% natural ingredients. Detox your day the wholesome way."
        ),
    },
    {
        "key": "email",
        "title": "Launch announcement email",
        "content_type": "email",
        "body": (
            "Subject: Your Northwind Harvest Oat Bars are here\n\n"
            "Hi there,\n\n"
            "Great news \u2014 Northwind Harvest Oat Bars launched on 12 March 2025 "
            "and are now shipping nationwide.\n\n"
            "Each bar has 6g of protein and is made with oats, almonds, honey and sea "
            "salt. We're FSSAI certified and USDA Organic, and this superfood bar is "
            "perfect for busy mornings.\n\n"
            "Reply to this email with any questions. We'd love to hear from you.\n\n"
            "\u2014 The Northwind Kitchen team"
        ),
    },
]

SAMPLES_BY_KEY = {s["key"]: s for s in SAMPLES}
