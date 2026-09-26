import pytest

from ml.normalizer import normalize


@pytest.mark.parametrize("src, expected", [
    ("Verify 0TP now", "Verify OTP now"),
    ("your b@nk account", "your bank account"),
    ("$BI KYC exp1red", "SBI KYC expired"),
    ("v e r i f y your account", "verify your account"),
    ("b.a.n.k details", "bank details"),
    ("раy now", "pay now"),                      # Cyrillic р, а
    ("o​tp", "otp"),                        # zero-width space
    ("ＯＴＰ", "OTP"),                            # full-width
    ("URGENT!! call", "URGENT!! call"),          # trailing ! is punctuation
])
def test_obfuscation_reversed(src, expected):
    assert normalize(src).text == expected


@pytest.mark.parametrize("text", [
    "Pay Rs 2,999 by 24Sep26",
    "OTP 482913 valid 5 mins",
    "Call 1800111109 or 9876543210",
    "Visit sbi-kyc.xyz or bit.ly/ab3d",
    "Mail help@b4nk.com",
    "A/c XX4521 debited",
    "I am fine. See you at 7pm on 21st",
    "gr8 c u l8r b4 2nite",
    "Get 10k cashback on 5G phones",
])
def test_legit_tokens_untouched(text):
    r = normalize(text)
    assert r.text == text
    assert r.count == 0


def test_changes_are_reported():
    r = normalize("URGENT! Your $BI KYC exp1red. Verify 0TP")
    assert {(c.original, c.normalized) for c in r.changes} == {("$BI", "SBI"), ("exp1red", "expired"), ("0TP", "OTP")}
    assert all(c.kind == "leet" for c in r.changes)
