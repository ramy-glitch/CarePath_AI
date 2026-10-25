"""The only patient-facing refusal. The model does not choose between a GP visit and emergency care."""

MESSAGE = "This result is not covered here. Contact your GP or NHS 111."


def fixed_message() -> str:
    return MESSAGE
