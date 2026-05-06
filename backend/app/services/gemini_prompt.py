from __future__ import annotations

from app.domain.imports import ImportInputType


def build_menu_extraction_prompt(
    *,
    source_text: str,
    input_type: ImportInputType,
    source_label: str | None = None,
    previous_errors: list[str] | None = None,
) -> str:
    source_name = source_label or input_type.value
    retry_guidance = ""
    if previous_errors:
        retry_guidance = "\n\nPrevious output problems to fix:\n" + "\n".join(f"- {error}" for error in previous_errors)

    return f"""Extract a restaurant menu from the source below and return only JSON matching the provided schema.

Rules:
- Preserve the restaurant name when it is present; otherwise infer a concise name from the source name.
- Use ISO 4217 currency codes such as EUR when a currency is identifiable.
- Use a BCP 47 language tag such as it, en, or it-en when the menu language is identifiable.
- Group items into meaningful menu categories.
- Keep item descriptions concise and factual.
- Store normalized numeric prices in price, and preserve the original price string in price_text when useful.
- Put multi-size or multi-format prices in variants.
- Put allergens and dietary labels in allergens or tags.
- Set confidence_score from 0 to 1 based on extraction completeness.
- Add validation_warnings for missing prices, uncertain currency, duplicate-looking content, or low confidence.
- Do not invent menu items that are not supported by the source.
{retry_guidance}

Source type: {input_type.value}
Source name: {source_name}

Menu source:
\"\"\"
{source_text}
\"\"\""""
