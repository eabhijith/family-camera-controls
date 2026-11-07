# Camera control design system

Mode: Operate. Familiarity, readable labels and restraint take priority over
decorative effects. This refines the existing cards rather than replacing the
family navigation.

- Inherit HA's sans-serif font and theme surfaces.
- Body/control labels at least 16px; touch targets at least 56px high, 8px gaps.
- One strong cyan accent for selected view; white-on-dark selected text.
- Consistent authored SVG directional icons, not Unicode glyphs.
- Upper/both/lower selection changes displayed view only.
- Movement panel always names the lower camera; upper control remains absent
  until real support is verified.
- Stable image region, useful connection/retry feedback, visible keyboard focus.
- Avoid frequent live-region announcements for snapshot timestamps.
- Respect reduced-motion; no decorative animations, external fonts or trackers.
- Verify phone and desktop layouts using explicitly simulated images, without
  placing household camera screenshots into the public repository.

Guidance consulted: Impeccable Operate/craft-floor references and UI/UX Pro Max
touch-spacing/target guidance. The Impeccable context launcher timed out; no
successful automated Impeccable audit is claimed.
