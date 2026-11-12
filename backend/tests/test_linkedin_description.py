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
