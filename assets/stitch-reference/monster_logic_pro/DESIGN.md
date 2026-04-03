# Design System Specification: Editorial Precision

## 1. Overview & Creative North Star
The North Star for this design system is **"The Command Alchemist."** 

While the utility of the application—cafe crawling and data harvesting—is inherently technical and high-speed, the interface must feel like a high-end editorial workspace. We are moving away from the "cluttered dashboard" aesthetic seen in legacy prosumer tools. Instead, we embrace a layout that balances **Professional Reliability** with **Intentional Breathing Room**. 

This system breaks the "template" look through:
*   **Layered Sophistication:** Moving beyond flat grey panels to a system of nested surfaces.
*   **Asymmetric Focus:** Utilizing a sidebar-heavy architecture that grounds the user, while the main canvas employs fluid, editorial spacing.
*   **Typographic Authority:** Using high-contrast scales between data-heavy labels and elegant, oversized headlines.

---

## 2. Colors: The Depth Palette
Our color strategy avoids harsh transitions. We use a "Tonal Shift" philosophy to define regions.

### Primary & Brand
*   **Primary (`#003629`):** A deep, authoritative Forest Green. Use this for the most significant actions and brand touchpoints.
*   **Primary Container (`#1b4d3e`):** Used for subtle branding in headers or high-level navigation blocks.
*   **Error (`#ba1a1a`):** A "Stop" signal that maintains the sophisticated tone without becoming neon or vibrating.

### The "No-Line" Rule
**Explicit Instruction:** Do not use `1px solid` borders to separate major UI sections. 
*   Boundaries are defined by background shifts. Use `surface-container-low` for the main backdrop and `surface-container-lowest` (pure white) for the primary interactive cards.
*   This creates a "Paper-on-Stone" effect that feels premium and custom.

### Glass & Texture
*   **Floating Elements:** Use `surface_variant` with a 70% opacity and a `20px` backdrop-blur for modals or pop-overs.
*   **Signature Gradients:** For primary CTAs, use a subtle linear gradient from `primary` (`#003629`) to `primary_container` (`#1b4d3e`) at a 135-degree angle. This adds a "lithographic" quality to buttons.

---

## 3. Typography: Editorial Utility
We pair **Manrope** (Display/Headlines) with **Inter** (Body/Data) to create an experience that is both beautiful and hyper-functional.

*   **Display Large (`manrope`, 3.5rem):** Reserved for hero data points or major section welcomes.
*   **Headline Medium (`manrope`, 1.75rem):** Used for primary module titles (e.g., "Execution Control").
*   **Body & Labels (`inter`):** 
    *   All numeric data must use **Tabular Slashed Zero** OpenType features. This ensures columns of data in the "Data/DB" section remain perfectly aligned regardless of the digit.
    *   **Label-SM (`inter`, 0.6875rem):** Used for micro-copy and metadata to keep the interface from feeling "heavy."

---

## 4. Elevation & Depth: Tonal Layering
Traditional drop shadows are a fallback, not a primary tool. We achieve depth through **The Layering Principle**.

### Stacking Tiers
1.  **Level 0 (Base):** `surface` (`#f8fafb`). The "desk" surface.
2.  **Level 1 (Sidebars/Sections):** `surface_container_low` (`#f2f4f5`).
3.  **Level 2 (Cards/Inputs):** `surface_container_lowest` (`#ffffff`). This creates a soft, natural lift.

### Ambient Shadows
Where floating is required (e.g., a "Start Crawl" button that stays fixed):
*   **Shadow Token:** `0 8px 32px rgba(25, 28, 29, 0.06)`. 
*   The shadow is tinted with the `on_surface` color, making it look like a natural ambient occlusion rather than a grey smudge.

### The "Ghost Border"
For input fields or cards that require high accessibility, use the `outline_variant` (`#c0c9c3`) at **20% opacity**. It provides a "hint" of a boundary without cluttering the visual field.

---

## 5. Components: Custom Primitives

### Buttons (The Precision Engine)
*   **Primary:** Solid `primary` background. Radius: `md` (0.375rem). Use the signature gradient for the "Start" state.
*   **Secondary:** `surface_container_highest` background with `on_surface_variant` text. No border.
*   **States:** On hover, shift background color one tier darker (e.g., from `primary` to `on_primary_fixed_variant`).

### Inputs (The Focus Field)
*   **Default:** `surface_container_lowest` with a "Ghost Border."
*   **Focus:** Transition the ghost border to `primary` (`#003629`) at 100% opacity. Add a subtle `primary_fixed` outer glow (4px spread, 10% opacity).
*   **Error:** Use `error` token for text and the border, paired with `error_container` for the background fill to ensure the field "screams" without breaking the layout.

### Cards & Data Lists
*   **Strict Rule:** No dividers. Use `spacing.4` (0.9rem) or background shifts to separate list items.
*   **Nesting:** Place `surface_container_high` chips on `surface_container_lowest` cards to denote status.

### Prosumer-Specific Components
*   **The Progress Ledger:** A custom list variant for crawl results. Instead of lines, use a alternating `surface_container_low` and `surface_container_lowest` zebra-striping with a `0.25rem` radius on each row.
*   **Speed Toggle:** A segmented control using `primary_fixed` for the active state, signifying high-speed "Pro" control.

---

## 6. Do's and Don'ts

### Do
*   **Do** use **Tabular Numbers** for all crawl counts and timestamps. Alignment is reliability.
*   **Do** allow for generous white space (use `spacing.10` or `spacing.12` between major modules).
*   **Do** use the `0.5rem` (lg) to `0.75rem` (xl) border-radius for cards to soften the "Monster" branding into a professional tool.

### Don't
*   **Don't** use 100% black text. Always use `on_surface` (`#191c1d`) to maintain the "Ink on Paper" editorial feel.
*   **Don't** use standard "Success Green." The brand is Forest Green; success should be indicated by the presence of the `primary` color or a "Check" icon, never a bright lime.
*   **Don't** cram icons. Every icon (Line Icons only) must have at least `8px` of internal padding to maintain the high-end feel.