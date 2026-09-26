import pytest

from ml.normalizer import normalize
from ml.obfuscate import ATTACKS, obfuscate

MSG = "URGENT your bank account is blocked. Verify OTP at sbi-kyc.xyz or call 9876543210 to claim refund"


@pytest.mark.parametrize("attack", ATTACKS)
def test_attack_changes_text_and_keeps_url_and_numbers(attack):
    out = obfuscate(MSG, attack, seed=1)
    assert out != MSG
    assert "sbi-kyc.xyz" in out
    assert "9876543210" in out


def test_seeded_and_reproducible():
    assert obfuscate(MSG, "mixed", seed=7) == obfuscate(MSG, "mixed", seed=7)


def test_non_keywords_untouched_at_rate_zero():
    assert obfuscate("see you at the station tomorrow", "leet", rate=0.0) == "see you at the station tomorrow"


@pytest.mark.parametrize("attack", ATTACKS)
def test_normalizer_recovers_attack(attack):
    # The defense should undo every attack the generator produces (case-insensitive).
    for seed in range(20):
        attacked = obfuscate(MSG, attack, seed=seed)
        recovered = " ".join(normalize(attacked).text.split()).replace(" .", ".")
        assert recovered.lower() == MSG.lower(), (attack, seed, attacked)
