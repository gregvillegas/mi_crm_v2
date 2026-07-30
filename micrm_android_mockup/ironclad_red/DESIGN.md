# Design System: High-Density Editorial B2B

## 1. Overview & Creative North Star
**The Creative North Star: "The Precision Architect"**

In the world of B2B CRM, information is the most valuable asset. However, high information density often leads to cognitive fatigue. This design system moves beyond the standard "utilitarian" Android app to create a **High-Density Editorial** experience. 

We are moving away from the "boxy" nature of traditional CRMs. By leveraging **Intentional Asymmetry** and **Tonal Depth**, we transform a data-heavy interface into a curated workspace. The "Precision Architect" approach treats every data point as a deliberate choice, using a mix of sophisticated typography and layered surfaces to guide the eye without the need for intrusive lines or borders. It is professional, authoritative, and custom-tailored for the high-stakes Android environment.

---

## 2. Colors & Surface Philosophy
The palette is rooted in the "Micro Image Red" (#B22222), but its application is surgical. We use a sophisticated range of tinted neutrals to create a sense of environmental depth.

### The "No-Line" Rule
**Borders are prohibited for sectioning.** To achieve a premium, custom feel, boundaries must be defined solely through background color shifts. For example:
- Use `surface_container_low` for a sidebar or secondary panel sitting on a `surface` background.
- High-priority data modules should use `surface_container_highest` to draw the eye.

### Surface Hierarchy & Nesting
Think of the UI as layers of fine paper.
*   **Base:** `surface` (#f4faff) — The foundation of the application.
*   **Sectioning:** `surface_container_low` (#e6f6ff) — Used for grouping related content blocks.
*   **Actionable Containers:** `surface_container_highest` (#c9e7f7) — For the most interactive or information-dense cards.

### The "Glass & Gradient" Rule
To elevate the experience above a standard template:
- **Hero Actions:** Use a subtle linear gradient from `primary` (#8f000d) to `primary_container` (#b22222) at a 45-degree angle. This adds "soul" and dimension to CTAs.
- **Floating Elements:** Modals and floating action menus must use **Glassmorphism**. Apply a semi-transparent `surface_tint` with a `backdrop-filter: blur(20px)` to allow the background data to softly bleed through, maintaining context.

---

## 3. Typography
We use a dual-typeface system to balance authority with readability.

*   **Display & Headlines (Manrope):** Chosen for its geometric precision and modern architectural feel. Use `headline-lg` (2rem) and `headline-md` (1.75rem) to establish clear landmarks in the CRM.
*   **Body & Labels (Inter):** Replaces Roboto for a more premium, editorial finish. It provides superior legibility at the high information densities required by MiCRM.
*   **Data Emphasis:** Numbers and statuses should use `label-md` or `label-sm` in **Medium/Semi-bold** weights to ensure they are the first thing a user scans in a high-density list.

---

## 4. Elevation & Depth
Depth in this system is a product of light and material, not artificial shadows.

*   **The Layering Principle:** Avoid `elevation-dp` values. Instead, "stack" tiers. A `surface_container_lowest` card placed on a `surface_container_low` background creates a "soft lift" that feels native to the screen.
*   **Ambient Shadows:** If an element must float (e.g., a bottom sheet), use an extra-diffused shadow.
    *   *Blur:* 16dp - 24dp
    *   *Opacity:* 6%
    *   *Color:* Use a tint of `on_surface` (#001f2a), never pure black.
*   **The Ghost Border:** If accessibility requires a stroke (e.g., in high-sunlight outdoor usage), use the `outline_variant` token at **15% opacity**. This provides a "suggestion" of a container without breaking the editorial flow.

---

## 5. Components

### Cards & Lists
*   **The Rule of White Space:** Dividers are forbidden. Separate list items using the spacing scale (8dp/16dp).
*   **Structure:** Cards use `roundedness-lg` (0.5rem). Use `surface_container_highest` for "Selected" states instead of a border.

### Buttons
*   **Primary:** High-contrast `primary` (#8f000d) with `on_primary` (#ffffff) text. Use the gradient rule for main "Save" or "Convert" actions.
*   **Secondary:** No background. Use `primary` text with a `surface_container` hover/press state.
*   **Tertiary:** Ghost style. Use `on_surface_variant` for low-priority actions like "Cancel."

### Status Chips
*   **High Contrast:** For B2B clarity, chips use semi-bold typography.
*   **Success:** `on_tertiary_fixed_variant` text on `tertiary_fixed` background.
*   **Urgent/Error:** `on_error_container` text on `error_container`.

### Input Fields
*   **Style:** Filled style only (no outlines). Use `surface_container_high` as the field background.
*   **Active State:** Indicate focus with a 2dp bottom-bar in `primary` red, rather than a full border.

### Precision CRM Components
*   **Data Grid:** Compact rows with 4dp vertical padding. Alternating row colors are replaced by a subtle `surface_container_lowest` vs `surface` shift.
*   **KPI Sparklines:** Small, simplified charts using `primary` for trend lines to maintain brand cohesion within data.

---

## 6. Do’s and Don’ts

### Do:
*   **Do** use asymmetrical spacing (e.g., more top padding than bottom) to create an editorial feel.
*   **Do** rely on the Typography Scale to convey hierarchy before reaching for a new color.
*   **Do** use the `surface_container` tiers to nest information groups (e.g., a lead's contact info vs. their history).

### Don't:
*   **Don't** use 1px solid black or grey lines to separate content.
*   **Don't** use standard Material 3 shadows (they are too "heavy" for a premium CRM).
*   **Don't** crowd the interface. Even in a high-density environment, use "Active White Space"—intentional gaps that allow the eye to rest between data clusters.