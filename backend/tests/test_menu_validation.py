import pytest
from pydantic import ValidationError

from app.schemas.menu import CanonicalMenu
from app.services.menu_schema import gemini_menu_json_schema
from app.services.menu_validation import parse_price_text, validate_canonical_menu


def test_validate_italian_menu_normalizes_comma_price_and_whitespace() -> None:
    menu = validate_canonical_menu(
        {
            "restaurant": "  Trattoria   da Mario ",
            "currency": "eur",
            "language": "IT",
            "source": {"type": "text", "value": " pasted menu "},
            "categories": [
                {
                    "name": " Antipasti ",
                    "items": [
                        {
                            "name": " Bruschetta   al pomodoro ",
                            "description": " Pane tostato\ncon pomodoro fresco ",
                            "price": None,
                            "price_text": "€ 6,50",
                            "allergens": [" Glutine ", "glutine"],
                            "tags": [" Vegetariano "],
                        }
                    ],
                }
            ],
        }
    )

    assert menu.restaurant == "Trattoria da Mario"
    assert menu.currency == "EUR"
    assert menu.language == "it"
    item = menu.categories[0].items[0]
    assert item.name == "Bruschetta al pomodoro"
    assert item.description == "Pane tostato con pomodoro fresco"
    assert item.price == 6.5
    assert item.price_text == "€ 6,50"
    assert item.allergens == ["glutine"]
    assert item.tags == ["vegetariano"]


def test_validate_english_menu_keeps_missing_price_as_null() -> None:
    menu = validate_canonical_menu(
        {
            "restaurant": "Nobu Milan",
            "currency": None,
            "language": "en",
            "source": {"type": "url", "value": "https://example.com/menu.pdf"},
            "categories": [
                {
                    "name": "Desserts",
                    "items": [
                        {
                            "name": "Chef selection",
                            "description": "Daily dessert tasting",
                            "price": None,
                            "price_text": None,
                        }
                    ],
                }
            ],
        }
    )

    assert menu.categories[0].items[0].price is None
    assert menu.currency is None


@pytest.mark.parametrize(
    ("price_text", "expected"),
    [
        ("€ 6,50", 6.5),
        ("6.50", 6.5),
        ("€ 7/hg", 7.0),
    ],
)
def test_parse_price_text(price_text: str, expected: float) -> None:
    assert parse_price_text(price_text) == expected


def test_multi_price_text_builds_variants_without_guessing_item_price() -> None:
    menu = validate_canonical_menu(
        {
            "restaurant": "Pizzeria",
            "currency": "EUR",
            "language": "it",
            "source": {"type": "file", "value": "menu.md"},
            "categories": [
                {
                    "name": "Pizze",
                    "items": [
                        {
                            "name": "Margherita",
                            "price_text": "normale € 6,50 / maxi € 9,00",
                        }
                    ],
                }
            ],
        }
    )

    item = menu.categories[0].items[0]
    assert item.price is None
    assert [(variant.name, variant.price, variant.price_text) for variant in item.variants] == [
        ("Option 1", 6.5, "€ 6,50"),
        ("Option 2", 9.0, "€ 9,00"),
    ]


def test_duplicate_categories_and_items_are_merged_conservatively() -> None:
    menu = validate_canonical_menu(
        {
            "restaurant": "Demo",
            "currency": "EUR",
            "language": "en",
            "source": {"type": "text", "value": "menu"},
            "categories": [
                {"name": "Starters", "items": [{"name": "Olives", "price_text": "4.00"}]},
                {
                    "name": " starters ",
                    "items": [{"name": "Olives", "price_text": "4.00", "tags": ["vegan"]}],
                },
            ],
        }
    )

    assert len(menu.categories) == 1
    assert len(menu.categories[0].items) == 1
    assert menu.categories[0].items[0].tags == ["vegan"]


def test_invalid_generated_json_is_rejected_with_useful_errors() -> None:
    with pytest.raises(ValidationError) as error:
        CanonicalMenu.model_validate(
            {
                "restaurant": "",
                "source": {"type": "text", "value": "menu"},
                "categories": [{"name": "Pasta", "items": [{"name": "Carbonara", "price": -1}]}],
                "unexpected": True,
            }
        )

    error_text = str(error.value)
    assert "restaurant" in error_text
    assert "Price cannot be negative" in error_text
    assert "unexpected" in error_text


def test_gemini_schema_is_generated_from_canonical_menu() -> None:
    schema = gemini_menu_json_schema()

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert "categories" in schema["properties"]
    assert "$defs" in schema
