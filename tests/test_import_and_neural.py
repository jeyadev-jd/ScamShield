import pytest

from ml.import_public import fix_mojibake, relabel


@pytest.mark.parametrize("text, src, label, method", [
    ("Dear SBI user your YONO Account will be block today Please update PAN", "spam", "smishing", "rule_smishing"),
    ("Dear Customer Your RBL Credit Card Points Worth INR XXXX expire by today Kindly redeem", "spam", "smishing", "rule_smishing"),
    ("get special offer on hdfc bank two wheeler loan nil processing fee exclusively for you", "spam", "spam", "rule_spam"),
    ("Rs299 recharged! Enjoy Unlimited Calls+4GB/Day+100SMS/Day", "spam", "spam", "rule_spam"),
    ("I sold it and am now waiting for the stock recommended by the professor today", "ham", "smishing", "rule_override_ham"),
    ("Hi, good morning, Saumya will be on leave today due to health issues.", "ham", "ham", "source_ham"),
])
def test_relabel(text, src, label, method):
    got_label, category, got_method = relabel(text, src)
    assert (got_label, got_method) == (label, method)
    assert category == ("legit" if label == "ham" else "promotional" if label == "spam" else category)


def test_fix_mojibake():
    assert fix_mojibake("Thatâ\u0080\u0099s all") == "That’s all"
    assert fix_mojibake("plain text") == "plain text"


def test_recurrent_classifier_learns():
    pytest.importorskip("torch")
    from ml.train_rnn import RecurrentClassifier

    scam = ["urgent your kyc expired verify otp at sbi-kyc.xyz", "you won a lottery prize claim now",
            "account blocked update pan card immediately", "earn rs 3000 daily part time task telegram"] * 15
    ham = ["see you at the station tomorrow", "reached home call you later",
           "meeting moved to 4 pm", "happy birthday have a great day"] * 15
    for arch in ("rnn", "lstm"):
        m = RecurrentClassifier(arch=arch, epochs=25, device="cpu", emb=16, hidden=16).fit(scam + ham, [1] * 60 + [0] * 60)
        p = m.predict_proba(["your kyc expired verify otp now", "meeting moved to 5 pm tomorrow"])
        assert m.classes_ == [0, 1] and p.shape == (2, 2)
        assert p[0, 1] > 0.5 > p[1, 1], arch


def test_attention_models_learn_and_expose_weights():
    pytest.importorskip("torch")
    from ml.train_rnn import RecurrentClassifier

    scam = ["urgent your kyc expired verify otp at sbi-kyc.xyz", "you won a lottery prize claim now",
            "account blocked update pan card immediately", "earn rs 3000 daily part time task telegram"] * 15
    ham = ["see you at the station tomorrow", "reached home call you later",
           "meeting moved to 4 pm", "happy birthday have a great day"] * 15
    for arch in ("rnn_attn", "lstm_attn"):
        m = RecurrentClassifier(arch=arch, epochs=25, device="cpu", emb=16, hidden=16).fit(scam + ham, [1] * 60 + [0] * 60)
        # Attention pooling fixes the plain RNN's last-word bias on this probe ("... see you").
        p = m.predict_proba(["your kyc expired verify otp now", "reached the station see you"])
        assert p[0, 1] > 0.5 > p[1, 1], arch
        w = m.attention("urgent your kyc expired verify otp now")
        assert [t for t, _ in w] == ["urgent", "your", "kyc", "expired", "verify", "otp", "now"]
        assert abs(sum(a for _, a in w) - 1) < 1e-3
    with pytest.raises(ValueError):
        RecurrentClassifier(arch="rnn", epochs=1, device="cpu").fit(scam, [1] * 60).attention("x")
