# Market Data Policy

`app/data/perfume_market_metadata.csv` holds manually verified market dates.
Only entries with `released_at` are returned by `sort=latest`; products without
an evidenced release date remain available through ordinary search and
recommendation.

`app/data/perfume_market_offers.csv` holds manually checked retail offers.
`sort=price_asc` and `sort=price_desc` use the lowest collected `price_krw` per
perfume. A Naver Shopping URL is a discovery link, not a verified price offer,
until a specific product URL and checked price are added to the offers file.

Each row keeps `release_source_url` and `verified_at` for audit. `market_date_type`
is `launch` when the source states a launch date. It is
`domestic_availability` only when the best available evidence is a Korean
official event or sales-start date rather than an explicit launch date. Clients
can use this field to avoid presenting the latter as an exact launch date.
The runtime database currently stores the release date and official product URL;
the CSV preserves the source evidence used during catalog maintenance.
