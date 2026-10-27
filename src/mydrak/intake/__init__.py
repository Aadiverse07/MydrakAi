"""Mock-only image intake boundary (Phase 1).

Accepts synthetic image descriptors — never raw image bytes — validates them,
applies the privacy gate BEFORE any external processing, and returns a
deterministic mock diagnosis. There is no live model, network, Telegram SDK, or
outbound sender here; an optional caller-supplied `sender` hook is invoked at
most once, only when the gate allows, and only with privacy-safe metadata.
"""
