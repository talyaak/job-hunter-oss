from app.ingestion.linkedin_auth import extract_linkedin_description


def test_extract_linkedin_description_from_json():
    html = 'foo "description":{"text":"We are hiring a developer.\\n\\nRequirements:\\n- TypeScript"} bar'
    text = extract_linkedin_description(html)
    assert text is not None
    assert "We are hiring" in text
    assert "TypeScript" in text


def test_extract_linkedin_description_from_markup():
    html = '<div class="show-more-less-html__markup">Build APIs with <b>Node</b>.</div>'
    text = extract_linkedin_description(html)
    assert text == "Build APIs with Node."


def test_extracts_description_from_testid_box_with_nested_spans():
    """Logged-in job pages (checked live, Nov 2026): hashed classes, stable data-testid, nested spans."""
    from app.ingestion.linkedin_auth import extract_linkedin_description

    html = (
        '<div class="x"><span class="i1 i2" tabindex="-1" data-testid="expandable-text-box">'
        "At Acme we build payments.<br><br>You will: <span class=\"b\">own services</span> and "
        "<span>mentor</span> teammates.</span><span>unrelated footer text that must not leak</span></div>"
    )
    text = extract_linkedin_description(html)
    assert text is not None
    assert text.startswith("At Acme we build payments.")
    assert "own services" in text and "mentor teammates." in text
    assert "unrelated footer" not in text


def test_testid_box_too_short_or_unclosed_is_ignored():
    from app.ingestion.linkedin_auth import extract_linkedin_description

    assert extract_linkedin_description('<span data-testid="expandable-text-box">short</span>') is None
    assert extract_linkedin_description('<span data-testid="expandable-text-box">never closed ' + "x" * 50) is None
