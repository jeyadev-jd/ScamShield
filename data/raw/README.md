# Raw data

The downloaded datasets are not committed. Fetch them into these folders, then run
`python -m ml.run_all` (or `ml.import_public` followed by `ml.build_dataset`).

| Folder / file | Dataset | Where to get it | License |
|---|---|---|---|
| `uci/SMSSpamCollection` | UCI SMS Spam Collection (Almeida & Gómez Hidalgo) | https://archive.ics.uci.edu/dataset/228/sms+spam+collection (unzip) | CC BY 4.0 |
| `mishra_soni/Dataset_5971.csv` | SMS Phishing Dataset for Machine Learning and Pattern Recognition (Mishra & Soni) | https://data.mendeley.com/datasets/f45bkkt8pr (Dataset_5971.zip, unzip) | CC BY 4.0 |
| `india_spam/spam_ham_india.csv` | Indian Telecom SMS Spam Collection | https://github.com/junioralive/india-spam-sms-classification (`dataset/spam_ham_india.csv`) | MIT |
| `scamshield_hf/{train,val,test}.jsonl` | ScamShield dataset (real rows only are used) | https://huggingface.co/datasets/sidzzz07/scamshield-dataset | MIT |
| `indian_raw.csv` (committed) | Messages quoted in news / PIB Fact Check reports, plus published and synthetic examples | this repository | — |

Generated files (not committed): `indian_public.csv` from `python -m ml.import_public`, and
`synthetic_train.csv` from `python -m ml.synth`.

## `indian_raw.csv` format

| Column | Values |
|---|---|
| `text` | the message exactly as received (obfuscation kept) |
| `label` | `ham`, `spam`, or `smishing` |
| `category` | `phishing, otp_account, upi_payment, kyc, prize_lottery, job_task, courier, digital_arrest, promotional, legit` |
| `source` | where it came from, e.g. `news:tribuneindia`, `pib_factcheck`, `published_example`, `synthetic`, `personal` |
| `is_synthetic` | `1` if written or adapted, `0` if received or reported as received |

Label rule of thumb: `smishing` tries to steal credentials, money or an OTP (link, call-back, collect
request); `spam` is unwanted promotion with no theft; `ham` is legitimate, including real bank and OTP
messages, which serve as hard negatives.

To add your own messages, append rows to `indian_raw.csv`. `build_dataset.py` masks phone numbers,
Aadhaar, PAN, account numbers and e-mail addresses, but review anonymisation by hand before sharing.
