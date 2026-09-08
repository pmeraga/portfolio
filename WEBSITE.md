# Portfolio website

The website is a dependency-free static site in `docs/`, hosted by GitHub Pages from `main` → `/docs`. Source projects remain browsable in the repository.

Public GitHub URL: https://pmeraga.github.io/portfolio/
Intended custom domain: https://pranavmeraga.com/

## Local preview

```bash
python3 -m http.server 8765 --directory docs
```

Open http://localhost:8765/ . Changes to `docs/` publish automatically when pushed to `main`; no Node build is needed.

## Custom domain connection

At setup time, the domain used `dns1.namecheaphosting.com` and `dns2.namecheaphosting.com`, with the apex A record at `198.187.29.17`. DNS changes must therefore be made in the active Namecheap hosting DNS zone (normally cPanel Zone Editor), not in an inactive registrar DNS panel.

To complete the connection:

1. Add `pranavmeraga.com` as the custom domain in the repository's GitHub Pages settings before changing DNS. Keep `docs/CNAME` containing `pranavmeraga.com` once enabled.
2. Replace the apex website A record with the following four GitHub Pages A records. Review any existing AAAA record for conflicts. Preserve unrelated mail and service records.

| Type | Name | Value |
| --- | --- | --- |
| A | @ | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |
| CNAME | www | pmeraga.github.io |

3. Wait for DNS validation and certificate issuance, then enable **Enforce HTTPS** in GitHub Pages.
4. Verify the apex and `www` URLs, including secure redirects.

The repository's account is `pmeraga`, so the DNS CNAME target is `pmeraga.github.io` (without `/portfolio`). The HECTUR project is separately hosted under `pranavmeraga.github.io`.

GitHub documentation: https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site

See [asset sources](docs/ASSETS.md) for the Mercor logo, HECTUR thumbnail, and research visualization.
