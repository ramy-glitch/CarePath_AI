"""Mask identifiers in OCR text. Lab names and values stay in the string."""

ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION"]


def find_identifiers(text: str, analyzer):
    return analyzer.analyze(text=text, entities=ENTITIES, language="en")


def mask_text(text: str, anonymizer, findings) -> str:
    return anonymizer.anonymize(text=text, analyzer_results=findings).text
