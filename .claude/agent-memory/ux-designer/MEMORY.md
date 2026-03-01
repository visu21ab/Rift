# Rift UX Designer Memory

## Design System (March 2026)
- **Theme**: Dark premium aesthetic inspired by Epidemic Sound
- **Background**: #0a0a0a (deep black), cards #141414/#1a1a1a
- **Text**: Primary #ffffff, secondary #888888, muted #555555
- **Accent**: White buttons on dark bg (inverted from typical dark themes)
- **Brand colors preserved**: Spotify green #1DB954, SoundCloud orange #FF5500
- **Typography**: Inter font, weights 300-900, step titles 42px/800 weight
- **Border style**: rgba(255,255,255,0.08) subtle borders, no heavy outlines
- **Animations**: GSAP 3.13.0 + ScrollTrigger via CDN

## Key Files
- `templates/index.html` — Main app template (GSAP CDN scripts loaded before app.js)
- `static/css/style.css` — Full dark theme CSS with CSS custom properties
- `static/js/app.js` — GSAP animation functions at top, existing logic preserved below
- `templates/landing.html` — Separate landing page (not modified in redesign)

## GSAP Integration Pattern
- `initGSAPAnimations()` runs on DOMContentLoaded
- `animateTrackItems()`, `animateMetrics()`, `animatePlaylistItems()` called dynamically when content appears
- All GSAP calls guarded with `typeof gsap === 'undefined'` checks
- ScrollTrigger used for section fade-in on scroll (start: 'top 85%')

## Important Constraints
- All existing element IDs must be preserved (JS references them)
- Service selector radio buttons must stay functional
- Connected button states use brand colors with subtle backgrounds
- Landing page styles are in the same CSS file but kept compatible
