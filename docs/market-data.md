# Market Data Policy

`app/data/perfume_market_metadata.csv` holds manually verified release dates.
Only entries with `released_at` are returned by `sort=latest`; products without
an evidenced release date remain available through ordinary search and
recommendation.

`app/data/perfume_market_offers.csv` holds manually checked retail offers.
`sort=price_asc` and `sort=price_desc` use the lowest collected `price_krw` per
perfume. A Naver Shopping URL is a discovery link, not a verified price offer,
until a specific product URL and checked price are added to the offers file.

Each release-date row keeps `release_source_url` and `verified_at` for audit.
The runtime database currently stores the release date and official product URL;
the CSV preserves the source evidence used during catalog maintenance.
