# Google OAuth public pages

This branch contains standalone HTML pages that do not require JavaScript, sign-in,
authentication configuration, or a working backend. It is based on main and can be
reviewed/deployed independently of codex/private-accounts.

After the Vercel deployment of this branch completes, open these exact URLs in a
signed-out browser and use them in Google Auth Platform > Branding:

- Application home page: https://codelens-ai-five.vercel.app/about.html
- Application privacy policy: https://codelens-ai-five.vercel.app/privacy.html
- Application terms of service: https://codelens-ai-five.vercel.app/terms.html

The contact address was confirmed by the project owner. Review the policy text
before publishing: it describes the current Render/Vercel/Supabase/Groq architecture,
the shared account-free demo, the conditional account features, and the incomplete
disk/vector cleanup of the existing repository-delete operation. Do not promise
complete automatic deletion until that behavior is implemented. Process manual
account and full-data deletion requests received at the published contact address.
Update these disclosures when account protection is enabled or hosting changes.

Both root and frontend Vercel configurations serve existing static files before
the SPA fallback, to cover deployments using either project root. If Vercel's
Clean URLs option is enabled, confirm the final redirect targets still serve the
correct documents before submitting them to Google.

Adding policy links does not complete OAuth configuration or make the application
production-ready. Google can separately require scope/brand/domain verification.
Check the actual requested scopes and authorized domains in your Google project.

Official requirements: https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification
