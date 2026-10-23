# Operator dashboard design

Surface mode: Operate. Live camera leads; compact introduction, adjacent instrument readout, enrollment workflow and searchable audit history follow.

| Role | Choice |
|---|---|
| Canvas / ink | #f3f5f3 / #15242e |
| Camera / accent | #10191f / #005dc4 |
| Display / body | Local Space Grotesk / system sans |
| Numerals | Tabular figures for telemetry and audit |
| Controls | 44px minimum touch height; visible 3px focus outline |
| Motion | Selected Transitions.dev dialog; GSAP decorative marks only |
| Mobile | Readouts below camera; dock suppressed while editing fields |

Controls and data do not wait for animation. Reduced motion disables transitions. CSS and GSAP never share transform ownership on the floating camera. No cloud workflow or framework migration.

The earlier docs/design.md remains historical reference material; this file describes the implemented operator surface.
