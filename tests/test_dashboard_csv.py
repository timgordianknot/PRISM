from apps.fincrm_dashboard import parse_csv_text, to_csv_bytes


def test_csv_roundtrip_handles_quoted_commas() -> None:
    rows = [
        {"date": "2026-03-01", "merchant": "Smith, Johnson & Co", "category": "Operations", "amount": -12.5},
        {"date": "2026-03-02", "merchant": 'Client "A"', "category": "Revenue", "amount": 100.0},
    ]

    csv_text = to_csv_bytes(rows).decode("utf-8")
    parsed = parse_csv_text(csv_text)

    assert len(parsed) == 2
    assert parsed[0]["merchant"] == "Smith, Johnson & Co"
    assert parsed[1]["merchant"] == 'Client "A"'
    assert parsed[1]["category"] == "Revenue"


def test_parse_csv_empty_input_returns_empty_list() -> None:
    assert parse_csv_text("") == []
