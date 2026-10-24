import pytest
from anonymisation.to_lab_json import to_lab_json


def test_known_values_without_ranges_are_unknown():
    report = "Patient Name: <PERSON> Email: <EMAIL_ADDRESS> Haemoglobin: 13.5 g/dL White Blood Cells: 6.2 x10^9/L Platelets: 250 x10^9/L"
    data = to_lab_json(report)
    assert [x["value"] for x in data["results"]] == [13.5, 6.2, 250.0]
    assert all(x["flag"] == "unknown" and x["referenceRange"] is None for x in data["results"])
    assert "PERSON" not in str(data) and "EMAIL_ADDRESS" not in str(data)


def test_explicit_reference_range_and_flag():
    data = to_lab_json("Haemoglobin: 11.2 g/dL ref: 12.0-16.0")
    assert data["results"][0]["flag"] == "low"


@pytest.mark.parametrize("text", [
    "White Blood Cells: 6.2 x10“9/L",
    "Platelets: 250 x10*9/L",
    "Haemoglobin: 135 gid.",
    "Haemoglobin: 13.5 g/dL john@example.com",
    "Haemoglobin: 13.5 g/dL ref: 16-12",
])
def test_ambiguous_input_fails_closed(text):
    with pytest.raises(ValueError):
        to_lab_json(text)
