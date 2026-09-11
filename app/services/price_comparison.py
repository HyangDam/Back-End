"""Provide safe outbound price-comparison links without price scraping."""

from urllib.parse import quote_plus


def build_price_comparison(
    perfume: dict,
    source_url: str = "",
    offers: list[dict] | None = None,
) -> dict:
    query = " ".join(
        part.strip()
        for part in [perfume.get("brand", ""), perfume.get("name", "")]
        if part
    )
    encoded_query = quote_plus(query)
    links = [
        {
            "retailer": "네이버 쇼핑",
            "url": f"https://search.shopping.naver.com/search/all?query={encoded_query}",
            "type": "search",
        }
    ]
    if source_url:
        links.append(
            {
                "retailer": "공식 판매처",
                "url": source_url,
                "type": "official",
            }
        )

    offers = offers or []
    has_verified_price = any(offer.get("price_krw") is not None for offer in offers)
    return {
        "perfume_id": perfume["perfume_id"],
        "query": query,
        "price_status": "collected" if has_verified_price else "not_collected",
        "message": (
            "확인 가격 데이터를 비교합니다. 가격과 재고는 판매처에서 최종 확인하세요."
            if has_verified_price
            else "현재 확인 가격 데이터가 없어 판매처 검색 링크를 제공합니다."
        ),
        "offers": offers,
        "links": links,
    }
