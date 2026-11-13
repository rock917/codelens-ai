# Application themes

Settings → Appearance offers Midnight Violet (default), Cyber Cyan, Emerald Matrix,
and Arctic Light. The profile menu links directly to this section. Theme changes
only change colors: page layout and application behavior stay the same.

## Persistence

The frontend uses the existing authenticated Supabase client to update only
`user_metadata.codelens_theme`. This cosmetic value is never used for permissions.
There are no schema migrations, backend changes, new credentials, or environment
variables. Theme saves are serialized so rapid selections persist in order.

Versioned, per-user localStorage entries retain the chosen theme if account sync
fails. Settings shows the failure and permits retry by selecting the theme again.
The signed-out page uses a local device preference. Invalid preferences fall back
to Midnight Violet; unavailable browser storage does not prevent switching.
The head script in `frontend/index.html` applies the last valid local theme before
React loads, and the provider reconciles the authenticated preference before paint.

## Colors and highlighting

`frontend/src/theme/tokens.css` defines the palettes and semantic design tokens.
All workspace screens, auth screens, menus and portal dialogs reference these
tokens. Google’s brand logo retains its official colors. Preview cards scope the
same tokens using `data-theme`.

`frontend/src/theme/syntax.ts` retains highlight.js categories while mapping them
to syntax tokens, including a contrasting light palette. Explorer and search use
the same highlighting configuration. Reduced-motion preferences are respected.

## Verification

Frontend tests cover guest refresh, account metadata, account isolation, rapid
selection, failed sync/retry, invalid preferences, blocked storage, and cross-tab
updates. Palette tests require 4.5:1 contrast for body/status/syntax text on the
three application surfaces and for filled button labels.

Manual release check: switch each theme, refresh, sign out/in, inspect Explorer
syntax and chat markdown, and open the sign-out and deletion dialogs without
submitting deletion. Confirm the theme remains selected and focus is visible.
