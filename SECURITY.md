# Security

## Reporting a vulnerability

Please report security problems privately through GitHub's
[private vulnerability reporting](https://github.com/MysterionRise/uk-liveability-index/security/advisories/new),
not in a public issue. Include what you found, how to reproduce it and what it could
affect. You should get a reply within a week.

## What to know when you run it

- **Model keys** live in `.env`, which git ignores. Set a credit limit on the key with
  your provider: the app's own caps (see `.env.example`) count what the provider
  reports, and the provider's limit is the real backstop.
- **The assistant reads data written by other people.** Place and pub names come from
  OpenStreetMap and other open sources; the assistant is told to treat tool results as
  data, and an eval checks it ignores instructions hidden in a name. Its tools only read
  the index's data, apart from moving the map, weights and shortlist on your page.
- **SQL in analyst mode** runs in a separate in-memory DuckDB with only the index's
  tables: one SELECT at a time, no file or network access, a row cap and a timeout.
- **The app serves plain HTTP** on one port (3000 by default). To put it on the
  internet, run it behind a proxy that adds HTTPS, and expect to tighten the caps.
