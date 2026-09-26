// Quiz bank. `scam` is the ground truth; `tell` is the human-written giveaway.
// Placeholder sample messages written for the UI; replace with items from the Indian test set.
export const QUIZ = [
  { sender: 'VM-SBIINB', time: '09:14', scam: false, category: 'legit',
    text: 'Dear Customer, your A/c XX4521 is debited by Rs 1,250.00 on 24Sep26 by UPI ref 426811. Not you? Call 1800111109. -SBI',
    tell: 'Registered sender header, masked account number, no link, and a published toll-free number.' },
  { sender: '+91 98XXXXXX21', time: '10:02', scam: true, category: 'kyc',
    text: 'URGENT! Your SBI KYC exp1red. Account will be blocked today. Verify 0TP at sbi-kyc.xyz',
    tell: 'Personal mobile number, a lookalike .xyz domain, and a request for your OTP.' },
  { sender: 'AD-INDPST', time: '11:47', scam: true, category: 'courier',
    text: 'IndiaPost: Your parcel is held at customs. Pay Rs 49 fee within 24 hrs or it will be returned: bit.ly/ip-redel',
    tell: 'India Post does not collect fees through shortened links. The small amount is bait for card details.' },
  { sender: 'VK-HDFCBK', time: '12:30', scam: false, category: 'legit',
    text: '482913 is the OTP for your HDFC Bank transaction of Rs 2,999. Valid for 5 mins. Do not share this OTP with anyone.',
    tell: 'A real OTP message tells you not to share it. It asks nothing of you.' },
  { sender: '+91 70XXXXXX88', time: '13:05', scam: true, category: 'digital_arrest',
    text: 'This is CBI Mumbai. A parcel with narcotics is registered on your Aadhaar. Arrest warrant issued. Call immediately on video to avoid arrest.',
    tell: 'No agency arrests anyone over a video call. Fear plus urgency is the whole attack.' },
  { sender: 'JD-AMAZON', time: '14:22', scam: false, category: 'legit',
    text: 'Your Amazon order #408-1182 has been shipped and will arrive by Sat, 27 Sep. Track in the Amazon app.',
    tell: 'No link to click, no payment asked, and it points you to the official app.' },
  { sender: '+91 63XXXXXX10', time: '15:40', scam: true, category: 'job_task',
    text: 'Part time job! Earn Rs 3000 daily income by liking YouTube videos. Simple task. Contact on Telegram now.',
    tell: 'Easy money for trivial tasks, then a move to Telegram. Later "tasks" ask you to deposit money.' },
  { sender: 'VM-JIOINF', time: '16:18', scam: false, category: 'promotional',
    text: 'Recharge with Rs 349 and get 2GB/day for 28 days. Recharge on MyJio app or jio.com. T&C apply.',
    tell: 'Promotional but genuine: registered header and the official domain jio.com.' },
  { sender: '+91 81XXXXXX45', time: '17:55', scam: true, category: 'prize_lottery',
    text: 'C o n g r a t s! You w0n Rs 25,00,000 in KBC l0ttery. Claim prize: tinyurl.com/kbc-claim',
    tell: 'Spaced letters and zeros for o are there to dodge spam filters. You cannot win a lottery you never entered.' },
  { sender: '+91 90XXXXXX73', time: '18:31', scam: true, category: 'upi_payment',
    text: 'Hi, I sent Rs 5000 to your UPI by mistake. Please accept the collect request I sent to return it. Urgent, my mother is in hospital.',
    tell: 'Accepting a collect request sends money out of your account, it never brings money in.' },
  { sender: 'VM-ELECTR', time: '19:10', scam: true, category: 'phishing',
    text: 'Dear consumer your electricity power will be disconnected tonight at 9.30pm because previous month bill was not updated. Call officer 88XXXXXX42',
    tell: 'Utilities never disconnect with a same-night SMS and a personal "officer" number. The broken grammar is a common sign.' },
  { sender: 'AX-IRCTCI', time: '20:02', scam: false, category: 'legit',
    text: 'PNR 4521887602, Train 12627, 28-Sep, SL S4 32. Chart prepared. Happy journey. -IRCTC',
    tell: 'Pure information: booking details, no link, no request.' },
]

export function drawQuiz(n = 10) {
  const a = [...QUIZ]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]]
  }
  return a.slice(0, n)
}
