# CrossAudit Website Design System

**Updated:** 2026-08-12
**Product:** Local-first audited agent workspace
**Design dials:** Variance 7/10 · Motion 8/10 · Density 6/10

## Direction

Dark-only, cinematic, technically precise, and restrained. The page should feel like a professional macOS agent product, not a generic SaaS template. Content density comes from evidence, product behavior, and real interface captures rather than decorative cards.

## Foundation

| Role | Value |
| --- | --- |
| Background | `#0B0E13` |
| Surface | `#11161E` |
| Raised surface | `#171D27` |
| Accent surface | `#18243A` |
| Text | `#EFF3F8` |
| Secondary text | `#AAB3C0` |
| Faint text | `#768190` |
| Accent | `#6991DF` |
| Accent highlight | `#8BADEB` |
| Action | `#3D67B4` |

- Display: Space Grotesk, with PingFang SC for Chinese.
- Body: DM Sans, with PingFang SC for Chinese.
- Technical labels: IBM Plex Mono.
- Corners stay compact: `0.5rem` to `1rem`; no excessive pill shapes.
- Glass is reserved for the fixed navigation and download surface. Content remains clear and opaque.

## Page Structure

1. Product promise and real running interface.
2. Dense six-point trust strip.
3. Scroll-triggered audit execution graph with eight checkpoints and three outcomes.
4. Full-resolution real workspace proof.
5. Capability matrix for files, models, tools, HPC, Git, and recovery.
6. Safety boundaries and local versus connected data.
7. Live GitHub release download.

## Dynamic Flow Standard

- Use one pinned storytelling scene only.
- Scrolling through semantic chapters changes the active node, role, and durable evidence.
- Direct node selection must work without scrolling.
- Animate only opacity and transforms; avoid layout-driven scroll listeners.
- Show the complete system: input, durable run, generator, Git revision, deterministic gate, independent audit, controlled loop, human admission, PASS, BLOCK, and ESCALATE.
- Surrounding capabilities are visible but subordinate: Files, MCP and Skills, HPC, and GitHub.
- Respect `prefers-reduced-motion`; the full content remains visible and usable without animation.

## Product Imagery

- Only use captures from the real CrossAudit app.
- Canonical source size: 2704 × 1824 Retina pixels.
- Provide 960 and 1600 pixel derivatives through `srcset`.
- Link every displayed capture to its full-resolution original.
- Never blur, upscale, or substitute a concept render for product proof.

## Interaction Rules

- Keyboard focus is always visible.
- Interactive targets remain at least 44px where practical.
- Hover effects do not move surrounding layout.
- Fixed navigation never covers anchor targets.
- At 768px and below, the flow map becomes non-sticky and chapters become a readable grid.
- At 544px and below, all dense grids collapse to one or two columns without horizontal scrolling.
- Reduced transparency replaces glass with opaque surfaces.
- Increased contrast strengthens borders and secondary text.

## Anti-patterns

- No light theme.
- No generic gradients, glowing text, emoji icons, fake terminals, or fabricated UI screenshots.
- No repeated card grid where a hierarchy or narrative is more appropriate.
- No split heading-and-copy composition that creates an empty half-section.
- No hidden audit meaning, private reasoning display, or unexplained internal signals.
- No motion without an informational purpose.

## Release Checklist

- Build, lint, and rendered HTML tests pass.
- Verify 375, 768, 1024, and 1440 pixel layouts.
- Confirm no horizontal overflow.
- Confirm language switch, release links, screenshot links, flow node selection, and scroll-driven state changes.
- Confirm reduced-motion and reduced-transparency fallbacks.
- Deploy the exact tested build to the linked Vercel production project.
