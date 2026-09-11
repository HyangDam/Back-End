-- Product-market data is intentionally separate from the source perfume catalog.
-- It supports verified price comparison, price sorting, and release-date sorting.

CREATE TABLE IF NOT EXISTS perfume_market_metadata (
    perfume_id INT NOT NULL,
    released_at DATE NULL,
    official_product_url VARCHAR(1000) NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (perfume_id),
    CONSTRAINT fk_market_metadata_perfume
        FOREIGN KEY (perfume_id) REFERENCES perfumes(perfume_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS perfume_market_offers (
    offer_id INT NOT NULL AUTO_INCREMENT,
    perfume_id INT NOT NULL,
    retailer VARCHAR(100) NOT NULL,
    product_url VARCHAR(1000) NOT NULL,
    price_krw INT NULL,
    capacity_ml INT NULL,
    checked_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (offer_id),
    UNIQUE KEY uq_perfume_market_offer (perfume_id, retailer, product_url(255)),
    INDEX ix_perfume_market_offers_price (perfume_id, price_krw),
    CONSTRAINT fk_market_offer_perfume
        FOREIGN KEY (perfume_id) REFERENCES perfumes(perfume_id)
        ON DELETE CASCADE
);
