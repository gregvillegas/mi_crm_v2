# MiCRM — UI Modernization Plan

**Prepared by:** Development Team  
**Date:** August 2026  
**Status:** For Management Approval

---

## PHASE 1: CURRENT STATE AUDIT

### Layout Structure

- **Pattern:** Top Navigation Bar (sticky, dark bg) + Full-width container content
- **Navigation:** Horizontal `navbar-expand-lg` with icon-based nav links, dropdowns for Leads/Funnel/Monitoring/Teams/Files/Users
- **No sidebar.** All navigation is crammed into the top bar — on desktop, nav items show icons only (text reveals on hover); on mobile, full hamburger collapse
- **Content:** Uses Bootstrap's `.container.mt-4` wrapper (max-width constrained, centered)
- **Footer:** Simple text-center footer at the bottom

### CSS Architecture

- **Framework:** Bootstrap 5.3.0 (CDN-loaded)
- **Icons:** FontAwesome 6.0 (CDN)
- **Custom CSS:** ~180 lines of inline `<style>` in `base.html` (not extracted to a stylesheet)
- **`!important` usage:** 7 occurrences in base.html (`.newly-quoted-card`, `.bg-pink`, `.nav-link padding`)
- **Per-template styles:** Additional `<style>` blocks in child templates (customer_list.html, dashboard.html, etc.) — CSS leaks globally
- **No CSS variables or design tokens** — colors are hardcoded hex values
- **No build pipeline** — no PostCSS, no CSS modules, no scoping

### Density & Spacing

- **Density:** Mixed — "Comfortable" on the home page (large jumbotron, generous card padding), "Dense" in data tables (`.table-sm`, small text sizes)
- **Inconsistent spacing:** Some pages use `.mb-4`, others `.mb-3`; some cards use `.p-3`, others default padding
- **No consistent grid system** for content spacing — relies on Bootstrap utility classes applied ad-hoc per template

### Color Palette

| Role | Current Value | Issue |
|------|--------------|-------|
| Primary | `#0056b3` (dark blue) | Acceptable contrast |
| Navbar BG | Bootstrap `.bg-dark` (#212529) | Good contrast with white text |
| Accent Pink | `#e91e63` (funnel "quoted") | Used as background with white text — OK |
| Accent Yellow | `#FFC107` (funnel "closable") | **Low contrast** with black text on some elements |
| Accent Green | `#28A745` (funnel "project") | White text on green — borderline 3.5:1 ratio |
| Body text | Default Bootstrap (#212529) | OK |
| Muted text | Bootstrap `.text-muted` (#6c757d) | **Low contrast** on white bg: ~4.5:1, borderline |
| Links | Varies per section (text-primary, text-warning, text-success) | Inconsistent link colors across modules |

### Typography

- **Font Family:** System default (Bootstrap's native font stack — no custom typeface loaded)
- **Scale:** Uses Bootstrap's defaults (mix of `rem` and occasional inline `style="font-size: 0.7rem;"`)
- **Headings:** Bootstrap defaults (`display-4` on home, `h2` with custom border-bottom in pages)
- **No explicit typography scale** — sizes chosen per-component without system
- **Small text overuse:** Multiple `.small` and `font-size: 0.65rem` patterns for badges/labels — accessibility concern

### Data Visualization

- **Tables:** Bootstrap `.table .table-striped .table-hover` with `.table-sm` — dense but functional
- **Dashboard cards:** Custom colored cards with `.card-body` for KPIs — no chart library visible
- **Funnel stages:** Color-coded sections (pink/yellow/green/blue) with text totals — no actual charts/graphs
- **No data visualization library** (no Chart.js, no D3, no Recharts)

---

## AUDIT REPORT

| Component Area | Current Issues (Visual/Accessibility) | Recommendation |
|---|---|---|
| **Navigation Bar** | Too many items crammed into top nav; icon-only on desktop makes discoverability poor; relies on hover to show labels (inaccessible on touch devices) | Switch to collapsible left sidebar with icon+text; keep top bar for search/notifications/profile only |
| **Base CSS** | 180+ lines inline in base.html; 7x `!important`; no design tokens; styles leak globally from child templates | Extract to external stylesheet; introduce CSS custom properties for colors/spacing; eliminate `!important` |
| **Color Palette** | Yellow/Amber backgrounds with dark text have borderline contrast; green badges with white text fail WCAG AA; inconsistent link colors per module | Define HSL-based palette with guaranteed 4.5:1 contrast ratios; standardize link/accent usage |
| **Typography** | No custom font; mixed PX/REM; over-reliance on `.small` and sub-12px sizes; no clear type hierarchy | Adopt Inter/Lexend at 16px base; use consistent REM scale; minimum 12px for any text |
| **Spacing** | Inconsistent padding/margin across templates; no grid system beyond Bootstrap's columns | Adopt 4px/8px spacing scale; standardize with utility classes or design tokens |
| **Data Tables** | `.table-sm` is very dense; no sticky headers; no virtual scrolling for long lists; company names truncated inconsistently | Add sticky headers; consistent truncation with tooltips; consider row hover state improvements |
| **Dashboard Cards** | KPI cards use varied sizing; no unified card component; inline styles for heights (`min-height:130px`) | Create reusable KPI card component with consistent sizing |
| **Forms** | crispy_forms with Bootstrap rendering — functional but plain; no inline validation styling; long forms without section grouping | Add visual section separators; inline validation states; improve label/input spacing |
| **Buttons** | Mix of `.btn-primary`, `.btn-outline-*`, `.btn-sm`, `.btn-light` — no consistent hierarchy or sizing | Define 3 button tiers (Primary/Secondary/Ghost) with consistent sizes |
| **Notifications** | Basic dropdown with text items; no visual category distinction; fixed 360px width | Redesign as a proper notification panel with icons, timestamps, and unread indicators |
| **Footer** | Minimal, plain, disconnected from overall design | Integrate into layout system; add subtle branding |
| **Dark Mode** | Not supported at all | Add dark mode via CSS custom properties + `prefers-color-scheme` media query |
| **Responsiveness** | Bootstrap's grid provides basic responsive layout; navbar collapses at `lg`; data tables overflow horizontally on mobile | Improve mobile table views (card-based or horizontal scroll with shadow indicators) |

---

## PHASE 2: DESIGN SYSTEM PROPOSAL — "Clean Minimalist with Focus on Whitespace"

### Design Philosophy

For a CRM that handles dense data (customers, proposals, funnels, activities), the **Clean Minimalist** approach is correct. Glassmorphism/Neubrutalism would distract from data readability. The goal:

- **Reduce visual noise** — fewer borders, more whitespace
- **Clear information hierarchy** — typography and spacing do the heavy lifting, not color
- **Functional color** — color is reserved for status, actions, and alerts
- **Consistent density controls** — user can toggle between "Comfortable" and "Compact" view

### Design Tokens (CSS Custom Properties)

```css
:root {
  /* Spacing — 4px base grid */
  --space-1: 0.25rem;   /* 4px */
  --space-2: 0.5rem;    /* 8px */
  --space-3: 0.75rem;   /* 12px */
  --space-4: 1rem;      /* 16px */
  --space-5: 1.5rem;    /* 24px */
  --space-6: 2rem;      /* 32px */
  --space-8: 3rem;      /* 48px */
  --space-10: 4rem;     /* 64px */

  /* Colors — HSL for easy dark mode manipulation */
  --color-bg-primary: hsl(0, 0%, 100%);
  --color-bg-secondary: hsl(220, 14%, 96%);
  --color-bg-elevated: hsl(0, 0%, 100%);
  
  --color-text-primary: hsl(220, 13%, 13%);      /* #1e293b — Slate 800 */
  --color-text-secondary: hsl(215, 16%, 47%);    /* #64748b — Slate 500 */
  --color-text-muted: hsl(215, 20%, 65%);        /* #94a3b8 — Slate 400 */
  
  --color-brand: hsl(217, 91%, 40%);             /* #1d4ed8 — Blue 700 */
  --color-brand-hover: hsl(217, 91%, 33%);
  --color-brand-light: hsl(217, 91%, 95%);
  
  --color-success: hsl(142, 71%, 35%);           /* #15803d — Green 700 */
  --color-warning: hsl(38, 92%, 50%);            /* #d97706 — Amber 600 */
  --color-danger: hsl(0, 72%, 51%);              /* #dc2626 — Red 600 */
  --color-info: hsl(199, 89%, 40%);              /* #0284c7 — Sky 600 */
  
  /* Funnel Stage Colors (distinct, accessible) */
  --color-stage-pink: hsl(340, 82%, 52%);        /* #e11d62 */
  --color-stage-yellow: hsl(38, 92%, 50%);       /* #d97706 */
  --color-stage-green: hsl(142, 71%, 35%);       /* #15803d */
  --color-stage-blue: hsl(217, 91%, 50%);        /* #2563eb */
  
  /* Borders & Shadows */
  --border-color: hsl(220, 13%, 91%);            /* #e2e8f0 — Slate 200 */
  --border-radius-sm: 0.375rem;  /* 6px */
  --border-radius-md: 0.5rem;    /* 8px */
  --border-radius-lg: 0.75rem;   /* 12px */
  
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -4px rgba(0, 0, 0, 0.05);
  
  /* Typography */
  --font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-size-xs: 0.75rem;    /* 12px */
  --font-size-sm: 0.875rem;   /* 14px */
  --font-size-base: 1rem;     /* 16px */
  --font-size-lg: 1.125rem;   /* 18px */
  --font-size-xl: 1.25rem;    /* 20px */
  --font-size-2xl: 1.5rem;    /* 24px */
  --font-size-3xl: 1.875rem;  /* 30px */
  
  --line-height-tight: 1.25;
  --line-height-normal: 1.5;
  --line-height-relaxed: 1.75;
}

/* Dark Mode */
@media (prefers-color-scheme: dark) {
  :root {
    --color-bg-primary: hsl(222, 47%, 11%);
    --color-bg-secondary: hsl(217, 33%, 17%);
    --color-bg-elevated: hsl(215, 28%, 17%);
    --color-text-primary: hsl(210, 40%, 98%);
    --color-text-secondary: hsl(215, 20%, 65%);
    --color-text-muted: hsl(215, 16%, 47%);
    --border-color: hsl(217, 33%, 25%);
  }
}
```

### Typography System

| Level | Size | Weight | Use Case |
|-------|------|--------|----------|
| Display | 2rem (32px) | 700 | Page titles ("Sales Proposals") |
| Heading | 1.25rem (20px) | 600 | Section headers ("Filters", "Items") |
| Subheading | 1rem (16px) | 600 | Card headers, table section headers |
| Body | 0.875rem (14px) | 400 | Default body text, table cells |
| Caption | 0.75rem (12px) | 400 | Timestamps, secondary labels, badges |
| Minimum | 0.75rem (12px) | — | Nothing below 12px in the entire app |

### Layout Proposal

```
┌─────────────────────────────────────────────────────────────────┐
│  TOP BAR (56px)                                                  │
│  [Logo] [Global Search...............] [Notif] [Profile ▼]     │
├────────┬────────────────────────────────────────────────────────┤
│        │                                                         │
│  SIDE  │  MAIN CONTENT AREA                                     │
│  BAR   │                                                         │
│  (64px │  ┌──────────────────────────────────────────────────┐  │
│  collapsd│  │  Page Header + Actions                           │  │
│  240px │  ├──────────────────────────────────────────────────┤  │
│  expand)│  │  Content (tables, cards, forms)                   │  │
│        │  │                                                    │  │
│  [☰]   │  │                                                    │  │
│  [👥]  │  │                                                    │  │
│  [📊]  │  │                                                    │  │
│  [📄]  │  │                                                    │  │
│  [📧]  │  │                                                    │  │
│  [⚙️]  │  └──────────────────────────────────────────────────┘  │
│        │                                                         │
├────────┴────────────────────────────────────────────────────────┤
│  FOOTER (dynamic year + service years)                           │
└─────────────────────────────────────────────────────────────────┘
```

**Sidebar behavior:**
- **Collapsed (default on desktop):** 64px wide, icons only with tooltip labels
- **Expanded (on hover or pin):** 240px wide, icons + full text labels
- **Mobile:** Hidden off-canvas, revealed by hamburger tap

### Component Design Principles

| Component | Old Style | New Style |
|-----------|-----------|-----------|
| Cards | Hard borders, colored headers | Subtle shadow + border-radius-lg, no colored header bars |
| Buttons | `.btn-primary` blue everywhere | 3 tiers: Solid (primary actions), Outline (secondary), Ghost (tertiary) |
| Tables | `.table-striped` alternating gray | Clean white rows, subtle bottom border, hover highlight |
| Badges | Bootstrap colored pills | Softer backgrounds (light tint + darker text) for better readability |
| Inputs | Standard Bootstrap form-control | Slightly taller (40px), consistent border-radius, focus ring (brand color) |
| Dropdowns | Bootstrap default shadows | Lighter shadow, rounded-lg, more padding between items |

---

## PHASE 3: MODULAR IMPLEMENTATION PLAN (Strangler Fig Pattern)

### Prerequisites & Setup

#### Packages to install:
```
# No new JS packages needed — this is a Django/server-rendered app.
# The modernization is purely CSS + template changes.
# Optionally add Inter font via Google Fonts CDN.
```

#### Files to create:
```
static/core/css/
├── design-tokens.css       # CSS custom properties (from Phase 2)
├── components.css          # Atomic component styles
├── layout.css              # New sidebar layout
└── utilities.css           # Custom utility classes
```

#### base.html modifications:
- Add Google Fonts `<link>` for Inter
- Add `<link>` to the new `design-tokens.css` and `components.css`
- Keep Bootstrap 5.3 (don't remove — transition gradually)
- Add `data-theme="light"` to `<html>` for theme toggle support

---

### TASK BREAKDOWN

#### Foundation (Week 1)

- [ ] Create `static/core/css/design-tokens.css` with all CSS custom properties (colors, spacing, typography, shadows)
- [ ] Create `static/core/css/components.css` with base styles for Button, Card, Badge, Input, Table
- [ ] Add Google Fonts Inter `<link>` to `base.html`
- [ ] Add `design-tokens.css` and `components.css` links to `base.html`
- [ ] Override Bootstrap's `--bs-body-font-family` to use Inter
- [ ] Set `font-size: 16px` on `<html>` element
- [ ] Add dark mode CSS variables under `@media (prefers-color-scheme: dark)`
- [ ] Create `.btn-crm-primary`, `.btn-crm-secondary`, `.btn-crm-ghost` button classes (coexist with Bootstrap)
- [ ] Create `.card-crm` class (subtle shadow, rounded-lg, no hard borders)
- [ ] Create `.badge-crm-*` classes (soft background tints)
- [ ] Create `.input-crm` class (taller, consistent radius, branded focus ring)
- [ ] Ensure all new classes accept override via `class=""` attribute in templates (no `!important`)

#### Layout Shell (Week 2)

- [ ] Create `templates/includes/sidebar.html` partial with collapsible sidebar
- [ ] Create `templates/includes/topbar.html` partial with search + notifications + profile
- [ ] Create `templates/base_modern.html` that extends from the new layout (sidebar + topbar + content area)
- [ ] Migrate `home.html` to extend `base_modern.html` as the first test page
- [ ] Add sidebar collapse/expand JavaScript (CSS transition, `localStorage` persistence)
- [ ] Ensure existing `base.html` pages continue to work unchanged (parallel layout)
- [ ] Add mobile off-canvas sidebar behavior

#### Module Replacement (Weeks 3-6)

- [ ] **Week 3: Dashboard (home.html)** — Redesign KPI cards, funnel overview, missions widget using new component classes
- [ ] **Week 3: Sales Funnel Dashboard** — Update table headers, card styles, filter form to new design
- [ ] **Week 4: Customer List** — Update stat cards, filter section, table styles, action buttons
- [ ] **Week 4: Customer Detail** — Update info cards, history timeline, notes section
- [ ] **Week 5: Proposal List** — Update grouped team view, action buttons, filter bar
- [ ] **Week 5: Proposal Detail** — Update sidebar details card, approval status, email history
- [ ] **Week 5: Proposal Form** — Update item rows, attachment section, terms accordion
- [ ] **Week 6: Sales Monitoring** — Update activity dashboard, reports, team performance
- [ ] **Week 6: Mass Mailing** — Update campaign list, recipient management, template builder
- [ ] **Week 6: User/Team Management** — Update user list, group views, quota management

#### Polish & Dark Mode (Week 7)

- [ ] Test all pages with dark mode enabled
- [ ] Fix any contrast issues surfaced by dark mode
- [ ] Add a manual theme toggle (light/dark/system) in the user dropdown
- [ ] Remove old inline `<style>` blocks from base.html (move to components.css)
- [ ] Remove `!important` flags
- [ ] Accessibility audit: run axe-core on key pages, fix any WCAG AA failures
- [ ] Performance: ensure no layout shift from font loading (use `font-display: swap`)

#### Cleanup (Week 8)

- [ ] Remove `base.html` inline styles completely (all moved to external CSS)
- [ ] Deprecate `base.html` in favor of `base_modern.html` (rename when all pages migrated)
- [ ] Remove unused Bootstrap utility classes where replaced by custom design system
- [ ] Document the design system (tokens, component classes, usage examples)
- [ ] Create a styleguide page (`/styleguide/`) for developers to reference

---

## CONSTRAINTS HONORED

- No API call changes
- No state management changes
- No routing changes
- No business logic changes
- All new components work alongside Bootstrap (gradual migration, not rip-and-replace)
- Dark mode supported via `prefers-color-scheme` + manual toggle
- All new CSS classes are overridable (no `!important`)
- Server-rendered Django templates — no SPA/React/Vue dependency introduced

---

## NEXT STEP

After management approval, we begin **Phase 3, Step 1 (Foundation)** — creating the design tokens CSS file and atomic component classes that coexist with Bootstrap without breaking any existing pages.
