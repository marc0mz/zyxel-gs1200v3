# Publishing through HACS

This source tree has the HACS repository structure, `hacs.json`, an integration manifest, a HACS validation workflow, and a Hassfest workflow. The connected GitHub profile is `marc0mz`; the proposed new repository is `zyxel-gs1200v3`.

Initial public repository:

1. Create a public GitHub repository; HACS supports public GitHub repositories.
2. Confirm the proposed repository name and, if it changes, update the two GitHub URLs in `manifest.json`.
3. Set the repository description and topics (`home-assistant`, `hacs`, `zyxel`, `integration`).
4. Choose and add a license before inviting reuse or accepting contributions.
5. Keep the current original blue project monogram, or supply an authorized Zyxel logo file without altering its artwork.
6. Review the alpha status and known feature gaps in `README.md` and `TEST_LOG.md` before publishing.

For a custom HACS repository, a public default branch is enough; a GitHub Release is optional. If releases are added later, their tag sets the version HACS shows. The first public upload can therefore be installed from the default branch while Home Assistant and switch-side checks continue.

Adding the integration to HACS's default catalog is separate from publishing the GitHub repository. It requires the HACS and Hassfest workflows to pass and a separate submission to `hacs/default`. The official HACS integration publishing guide also calls for a Home Assistant Brands entry; the project monogram is not Zyxel's official logo.

The local integration `brand/` directory contains a blue project monogram for development. It is not presented as Zyxel's official logo.
