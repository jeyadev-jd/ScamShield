"""Synthetic Indian SMS for training augmentation (hard negatives + Indian scam types).

    python -m ml.synth                 # writes data/raw/synthetic_train.csv

Why: UCI and Mishra-Soni contain almost no Indian transactional messages, so a
model trained on them flags real bank debit alerts, OTPs and bills as spam
(experiment E2 measures exactly this). Until enough real Indian messages are
collected, templated messages fill the gap.

Rules that keep this honest:
- Written to TRAIN ONLY. build_dataset never puts these rows in a test split.
- Every row has is_synthetic=1 and source "synthetic".
- ``python -m ml.build_dataset --no-synthetic`` trains without them, so the
  report can show results with and without augmentation.
- The templates are generic formats, not copies of the evaluation messages.
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "synthetic_train.csv"

BANKS = [("SBI", "SBIINB"), ("HDFC Bank", "HDFCBK"), ("ICICI Bank", "ICICIB"), ("Axis Bank", "AXISBK"),
         ("Kotak Bank", "KOTAKB"), ("PNB", "PNBSMS"), ("Bank of Baroda", "BOBSMS"), ("Canara Bank", "CANBNK"),
         ("Union Bank", "UBOIND"), ("IDFC FIRST Bank", "IDFCFB"), ("Yes Bank", "YESBNK"), ("IndusInd Bank", "INDUSB")]
MERCHANTS = ["AMAZON", "FLIPKART", "SWIGGY", "ZOMATO", "BIGBASKET", "UBER", "OLA", "IRCTC", "MYNTRA", "DMART",
             "RELIANCE SMART", "APOLLO PHARMACY", "BOOKMYSHOW", "MAKEMYTRIP", "BLINKIT", "ZEPTO"]
NAMES = ["RAHUL K", "PRIYA S", "ANIL KUMAR", "MEENA R", "ARJUN P", "DIVYA N", "SURESH M", "KAVYA J", "VIKRAM T", "ANJALI D"]
APPS = ["Amazon", "Flipkart", "Paytm", "PhonePe", "Google Pay", "Swiggy", "Zomato", "Ola", "Uber", "Myntra",
        "Naukri", "LinkedIn", "Instagram", "WhatsApp", "DigiLocker", "Aadhaar (UIDAI)", "IRCTC", "CRED", "Groww", "Zerodha"]
UTIL = [("TNEB", "electricity"), ("BESCOM", "electricity"), ("MSEDCL", "electricity"), ("Tata Power", "electricity"),
        ("Airtel", "postpaid"), ("Jio", "postpaid"), ("Vi", "postpaid"), ("BSNL", "broadband"), ("ACT Fibernet", "broadband"),
        ("Mahanagar Gas", "gas"), ("Indane", "LPG")]
COURIERS = ["Blue Dart", "Delhivery", "DTDC", "Ecom Express", "India Post", "Shadowfax", "Xpressbees"]
BRANDS_PROMO = ["Myntra", "AJIO", "Nykaa", "Croma", "Reliance Digital", "Lenskart", "Pantaloons", "Decathlon", "Tanishq", "boAt"]
FAKE_TLDS = ["xyz", "top", "online", "site", "info", "live", "icu", "club", "support", "vip"]
SHORT = ["bit.ly", "tinyurl.com", "cutt.ly", "rb.gy", "is.gd"]


def _amt(r, lo=50, hi=50000):
    v = r.randint(lo, hi)
    return f"{v:,}" if r.random() < 0.6 else str(v)


def _acct(r):
    return f"XX{r.randint(1000, 9999)}"


def _date(r):
    d, m = r.randint(1, 28), r.choice(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    return r.choice([f"{d:02d}{m}{r.choice(['25', '26'])}", f"{d:02d}-{m}-26", f"{d:02d}/{r.randint(1, 12):02d}/26"])


def _mobile(r):
    return f"{r.choice('6789')}{r.randint(100000000, 999999999)}"


def _fake_domain(r, brand):
    b = brand.lower().replace(" ", "")
    return r.choice([f"{b}-{r.choice(['kyc', 'verify', 'secure', 'update', 'reward', 'help'])}.{r.choice(FAKE_TLDS)}",
                     f"{r.choice(['secure', 'my', 'online', 'e'])}-{b}.{r.choice(FAKE_TLDS)}",
                     f"{r.choice(SHORT)}/{''.join(r.choices('abcdefghjkmnpqrstuvwxyz23456789', k=6))}"])


# ------------------------------------------------------------------ legitimate

def ham(r: random.Random) -> str:
    bank, code = r.choice(BANKS)
    k = r.randrange(16)
    if k == 0:
        return (f"Dear Customer, your A/c {_acct(r)} is debited by Rs {_amt(r)}.00 on {_date(r)} "
                f"{r.choice(['by UPI ref', 'trf to', 'for'])} {r.choice([str(r.randint(10**8, 10**9)), r.choice(NAMES), r.choice(MERCHANTS)])}. "
                f"{r.choice(['Not you? Call 1800' + str(r.randint(100000, 999999)), 'If not done by you, report to your bank.', 'Avl Bal Rs ' + _amt(r) + '.' + str(r.randint(10, 99))])} -{bank}")
    if k == 1:
        return f"Rs {_amt(r)} credited to your A/c {_acct(r)} on {_date(r)} by {r.choice(['UPI', 'NEFT', 'IMPS'])} from {r.choice(NAMES)}. Avl Bal Rs {_amt(r)}. -{bank}"
    if k == 2:
        return (f"{r.randint(100000, 999999)} is your OTP for {r.choice(['transaction', 'login', 'payment of Rs ' + _amt(r)])} "
                f"on {r.choice(APPS + [bank])}. {r.choice(['Valid for 5 mins.', 'Valid for 10 minutes.', ''])} "
                f"{r.choice(['Do not share it with anyone.', 'Never share your OTP with anyone, including bank staff.', 'Do not share this OTP.'])}")
    if k == 3:
        return f"Your OTP to {r.choice(['log in to', 'verify your email on', 'verify your mobile on', 'reset your password on'])} {r.choice(APPS)} is {r.randint(1000, 999999)}. {r.choice(['Do not share it.', 'It expires in 10 minutes.', ''])}"
    if k == 4:
        return f"Transaction of Rs {_amt(r)} at {r.choice(MERCHANTS)} on card {_acct(r)} {r.choice(['is successful', 'declined due to incorrect PIN', 'declined due to insufficient balance'])}. -{bank}"
    if k == 5:
        return f"Your {r.choice(['credit card', bank + ' credit card'])} statement is ready. Total due Rs {_amt(r)}, minimum due Rs {_amt(r, 100, 3000)}, due date {_date(r)}."
    if k == 6:
        return f"Your EMI of Rs {_amt(r, 500, 30000)} for loan {_acct(r)} will be auto-debited on {_date(r)}. Please keep sufficient balance. -{r.choice([bank, 'Bajaj Finance', 'HDB Financial'])}"
    if k == 7:
        u, kind = r.choice(UTIL)
        return f"Dear customer, your {u} {kind} bill of Rs {_amt(r, 100, 5000)} is due on {_date(r)}. Pay via the {u} app or website. {r.choice(['Ignore if paid.', 'Thank you.', ''])}"
    if k == 8:
        return f"Your {r.choice(APPS[:6] + ['Nykaa', 'Meesho', 'AJIO'])} order #{r.randint(100, 999)}-{r.randint(1000000, 9999999)} {r.choice(['has been shipped', 'is out for delivery', 'will be delivered today', 'has been delivered'])}. {r.choice(['Track in the app.', 'Thank you for shopping with us.', ''])}"
    if k == 9:
        return f"Shipment {r.randint(10**9, 10**10)} from {r.choice(COURIERS)} {r.choice(['is out for delivery', 'has been delivered', 'will be delivered by 7 PM'])}. {r.choice(['OTP for delivery: ' + str(r.randint(1000, 9999)), ''])}"
    if k == 10:
        return f"PNR {r.randint(10**9, 10**10)}, Train {r.randint(10000, 22999)}, {_date(r)}, {r.choice(['SL', '3A', '2A', 'CC'])} {r.choice(['S', 'B', 'A'])}{r.randint(1, 9)} {r.randint(1, 72)}. {r.choice(['Chart prepared.', 'Booking confirmed.', 'Happy journey.'])} -IRCTC"
    if k == 11:
        return f"Your refund of Rs {_amt(r, 50, 5000)} for order {r.randint(10**6, 10**7)} has been {r.choice(['initiated', 'processed'])} and will reach your {r.choice(['account', 'original payment method'])} in {r.randint(3, 7)} days. -{r.choice(APPS[:6])}"
    if k == 12:
        return f"Payment of Rs {_amt(r, 50, 5000)} to {r.choice(MERCHANTS)} failed. Any amount debited will be refunded within {r.choice(['48 hours', '5 working days'])}. -{bank}"
    if k == 13:
        return f"Reminder: your appointment {r.choice(['with Dr. ' + r.choice(['Mehta', 'Rao', 'Iyer', 'Khan', 'Das']), 'at the service centre', 'for vehicle service'])} is {r.choice(['today', 'tomorrow'])} at {r.randint(9, 18)}:{r.choice(['00', '30'])}. {r.choice(['Reply C to confirm.', 'Call us to reschedule.', ''])}"
    if k == 14:
        return f"{r.choice(BRANDS_PROMO)}: {r.choice(['End of season sale', 'Festive sale', 'Weekend offer', 'Diwali sale'])}! {r.choice(['Flat', 'Up to'])} {r.choice([20, 30, 40, 50, 60, 70])}% off. {r.choice(['Shop now in the app.', 'Visit your nearest store.', 'T&C apply.'])}"
    return r.choice([
        f"Hey, reached {r.choice(['home', 'office', 'the station', 'college'])}. Will call you {r.choice(['later', 'tonight', 'tomorrow'])}.",
        f"Can you {r.choice(['send me the notes', 'pick up milk on the way', 'call me when free', 'share the photos'])}? {r.choice(['Thanks!', 'Urgent-ish', ''])}",
        f"Happy {r.choice(['birthday', 'anniversary', 'Diwali', 'Pongal'])}! {r.choice(['Have a great day.', 'Party at our place tonight.', 'Miss you.'])}",
        f"Meeting moved to {r.randint(2, 6)} pm {r.choice(['today', 'tomorrow'])}. Same room.",
    ])


# ------------------------------------------------------------------ scams

def scam(r: random.Random) -> tuple[str, str]:
    bank, _ = r.choice(BANKS)
    short = bank.split()[0]
    k = r.randrange(12)
    if k == 0:
        return "kyc", (f"{r.choice(['Dear customer', 'Dear ' + short + ' user', 'URGENT'])}: your {r.choice(['KYC is pending', 'KYC has expired', 'PAN is not updated', 'e-KYC is incomplete'])}. "
                       f"Your account will be {r.choice(['blocked', 'suspended', 'frozen'])} {r.choice(['today', 'within 24 hours', 'tonight'])}. Update now: {_fake_domain(r, short)}")
    if k == 1:
        return "otp_account", (f"{r.choice(['Your', 'Dear customer, your'])} {r.choice(['debit card', 'netbanking', 'account', 'YONO access', 'credit card'])} has been "
                               f"{r.choice(['blocked', 'locked', 'put on hold', 'suspended'])} due to {r.choice(['suspicious activity', 'incomplete verification', 'a security issue'])}. "
                               f"{r.choice(['Share the OTP sent to you to restore it.', 'Call ' + _mobile(r) + ' immediately.', 'Verify your card details at ' + _fake_domain(r, short)])}")
    if k == 2:
        return "prize_lottery", (f"{r.choice(['Congratulations!', 'Lucky winner!', 'Congrats!'])} Your number has {r.choice(['won', 'been selected for'])} "
                                 f"{r.choice(['Rs ' + _amt(r, 10000, 2500000), 'an iPhone', 'a car in the lucky draw', 'a cash reward'])}. "
                                 f"{r.choice(['Claim before midnight', 'Pay a small processing fee to claim', 'Claim now at ' + _fake_domain(r, 'reward')])}.")
    if k == 3:
        c = r.choice(COURIERS + ["FedEx", "DHL"])
        return "courier", (f"{c}: your {r.choice(['parcel', 'shipment', 'package'])} is {r.choice(['on hold at customs', 'undeliverable due to incomplete address', 'held for unpaid duty'])}. "
                           f"{r.choice(['Pay Rs ' + _amt(r, 25, 499) + ' fee', 'Update your address', 'Pay customs charges'])} {r.choice(['within 24 hrs', 'today', 'now'])}: {_fake_domain(r, c)}")
    if k == 4:
        return "digital_arrest", (f"{r.choice(['This is CBI', 'Mumbai Police cyber cell', 'Delhi Police', 'Narcotics Bureau', 'TRAI legal department'])}: "
                                  f"{r.choice(['a parcel with drugs is registered on your Aadhaar', 'your number is linked to a money laundering case', 'an arrest warrant is issued in your name', 'your SIM is used for illegal activity'])}. "
                                  f"{r.choice(['Stay on video call and do not tell anyone.', 'Press 1 to speak to the officer.', 'Call immediately to avoid arrest.', 'You are under digital arrest, do not disconnect.'])}")
    if k == 5:
        return "job_task", (f"{r.choice(['Part time job', 'Work from home', 'Hiring now', 'Online job'])}: earn Rs {_amt(r, 1000, 9000)} {r.choice(['per day', 'daily'])} by "
                            f"{r.choice(['liking YouTube videos', 'rating products', 'simple online tasks', 'reviewing hotels'])}. "
                            f"{r.choice(['Contact on Telegram', 'WhatsApp HR ' + _mobile(r), 'Message us on Telegram now', 'Small task deposit required'])}.")
    if k == 6:
        return "upi_payment", (f"{r.choice(['Hi, I sent Rs ' + _amt(r, 500, 20000) + ' to your UPI by mistake', 'You have received a cashback of Rs ' + _amt(r, 100, 5000)])}. "
                               f"{r.choice(['Please accept the collect request to return it.', 'Accept the request and enter your UPI PIN to receive it.', 'Scan the QR code to receive the amount.'])}")
    if k == 7:
        return "phishing", (f"Your {r.choice(['electricity', 'gas connection', 'SIM', 'broadband'])} will be {r.choice(['disconnected tonight', 'cut today', 'deactivated within 2 hours'])} "
                            f"{r.choice(['as last bill was not updated', 'due to pending KYC', 'as per TRAI rules'])}. {r.choice(['Call officer ' + _mobile(r), 'Update now: ' + _fake_domain(r, 'bill'), 'Contact ' + _mobile(r) + ' immediately'])}.")
    if k == 8:
        return "phishing", (f"{r.choice(['Income Tax refund of Rs ' + _amt(r, 1000, 40000) + ' approved', 'Your recent payment could not be processed', 'Your refund is pending'])}. "
                            f"{r.choice(['Submit your bank details', 'Verify your banking details', 'Confirm your card information'])} to receive it: {_fake_domain(r, 'refund')}")
    if k == 9:
        return "phishing", (f"{r.choice(['Hi Mum', 'Hi Dad', 'Hello Papa', 'Hi Amma'])}, {r.choice(['I dropped my phone', 'I lost my phone', 'my phone is broken'])} and this is my new number. "
                            f"Can you send Rs {_amt(r, 2000, 20000)} {r.choice(['urgently', 'now', 'today'])}? {r.choice(['Will explain later.', 'Please don’t call, just send.', ''])}")
    if k == 10:
        return "job_task", (f"{r.choice(['Join our stock tips group', 'Invest with us', 'Crypto trading plan'])}: {r.choice(['guaranteed returns of', 'get'])} {r.choice([100, 200, 300, 500])}% "
                            f"{r.choice(['in one week', 'monthly'])}. {r.choice(['Limited seats', 'Join now'])}: t.me/{r.choice(['profit', 'wealth', 'stock'])}{r.randint(10, 999)}")
    return "otp_account", (f"{r.choice(['Bank official here', short + ' customer care', 'Fraud team'])}: {r.choice(['to stop an unauthorized transaction', 'to reverse a suspicious debit', 'to unblock your account'])}, "
                           f"please {r.choice(['share the OTP you just received', 'tell us the verification code', 'confirm your card number and CVV'])}.")


def generate(n_ham: int = 900, n_scam: int = 450, seed: int = 7) -> pd.DataFrame:
    r = random.Random(seed)
    rows = [{"text": " ".join(ham(r).split()), "label": "ham", "category": "legit"} for _ in range(n_ham)]
    for _ in range(n_scam):
        cat, text = scam(r)
        rows.append({"text": " ".join(text.split()), "label": "smishing", "category": cat})
    df = pd.DataFrame(rows).drop_duplicates("text")
    df["source"] = "synthetic"
    df["is_synthetic"] = 1
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ham", type=int, default=900)
    ap.add_argument("--scam", type=int, default=450)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    df = generate(a.ham, a.scam, a.seed)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"wrote {len(df)} rows to {OUT}: {df['label'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
