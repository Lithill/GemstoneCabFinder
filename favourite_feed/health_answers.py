"""Offline-only validation of symptom tracker answers.

This module does not register routes or write data. Keep question labels and
choice sets aligned with the non-saving JavaScript prototype.
"""
from datetime import date
import math

QUESTIONS = {
    "Hot flushes": "yesno", "Night sweats": "yesno",
    "Period / bleeding today": "period",
    "Period start or end date": "date",
    "Cycle changes or irregular periods": "severity",
    "Heavy bleeding or flooding": "severity",
    "Anhedonia (loss of enjoyment)": "severity",
    "Anxiety / feeling tense or nervous": "severity",
    "Change to your mood / mood swings": "severity",
    "Crying spells": "severity", "Depression / low mood": "severity",
    "Irritability": "severity", "Lack of motivation": "severity",
    "Shutdowns": "severity", "Meltdowns": "severity",
    "Panic attacks": "severity", "Anger or angry outbursts": "severity",
    "Brain fog": "severity",
    "Difficulty concentrating / loss of concentration": "severity",
    "Fatigue / lacking in energy": "severity",
    "Difficulty sleeping / insomnia": "sleep",
    "Fibromyalgia pain": "severity", "Bloating": "severity", "Breathing difficulties": "severity",
    "Digestive problems": "severity", "Feeling dizzy or faint": "severity",
    "Headaches": "severity", "Heartburn": "severity",
    "Heart palpitations": "severity", "Migraines": "severity",
    "Nausea": "severity",
    "Pins and needles / tingling hands or feet": "severity",
    "Sore breasts": "severity", "Tinnitus": "severity",
    "UTI episode / recurrent UTIs": "uti",
    "Sex drive / low libido / fluctuations": "libido",
    "Weight measurement": "weight",
}

CHOICES = {
    "yesno": {"Yes", "No"},
    "severity": {"None", "Mild", "Moderate", "Severe"},
    "period": {"None", "Period", "Spotting", "Unexpected"},
    "sleep": {"None", "Mild", "Moderate", "Severe"},
    "uti": {"Suspected", "Confirmed", "Symptoms", "Resolved"},
    "libido": {"Low", "Usual", "Higher", "Fluctuating"},
}
FLOW = {"Light", "Medium", "Heavy", "Flooding"}
UNITS = {"kg", "lb", "st"}


def validate_entry(day, question, answer):
    """Return a canonical entry; reject unrecognized or malformed answers.

    Notes are deliberately excluded until a separate privacy and retention
    decision is made. No entry is persisted by this function.
    """
    if not isinstance(day, str) or not isinstance(question, str) or question not in QUESTIONS:
        raise ValueError("Unknown date or symptom question.")
    try:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError
    except ValueError as exc:
        raise ValueError("Invalid entry date.") from exc
    if not isinstance(answer, dict) or set(answer) - {"answer", "flow", "detail", "hours", "unit"}:
        raise ValueError("Unexpected answer fields.")
    kind = QUESTIONS[question]
    value = answer.get("answer")
    if kind in CHOICES:
        if not isinstance(value, str) or value not in CHOICES[kind]:
            raise ValueError("Invalid answer choice.")
    elif kind == "date":
        if not isinstance(value, str):
            raise ValueError("Invalid period event date.")
        try:
            if date.fromisoformat(value).isoformat() != value:
                raise ValueError
        except ValueError as exc:
            raise ValueError("Invalid period event date.") from exc
    elif kind == "weight":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value < 1000:
            raise ValueError("Invalid weight.")
    allowed = {"answer"}
    if kind == "period" and value != "None":
        allowed.add("flow")
        if "flow" in answer and (not isinstance(answer["flow"], str) or answer["flow"] not in FLOW):
            raise ValueError("Invalid bleeding flow.")
    if kind == "date":
        allowed.add("detail")
        if not isinstance(answer.get("detail"), str) or answer["detail"] not in {"Start", "End"}:
            raise ValueError("Invalid period event.")
    if kind == "weight":
        allowed.add("unit")
        if not isinstance(answer.get("unit"), str) or answer["unit"] not in UNITS:
            raise ValueError("Invalid weight unit.")
    if kind == "sleep":
        allowed.add("hours")
        if "hours" in answer:
            hours = answer["hours"]
            if isinstance(hours, bool) or not isinstance(hours, (int, float)) or not math.isfinite(hours) or not 0 <= hours <= 24:
                raise ValueError("Invalid sleep duration.")
    if kind == "uti":
        allowed.add("detail")
        if "detail" in answer and (not isinstance(answer["detail"], str) or len(answer["detail"]) > 500):
            raise ValueError("Invalid UTI detail.")
    if set(answer) - allowed:
        raise ValueError("Fields do not match this question.")
    return {"day": day, "question": question, "answer": dict(answer)}
