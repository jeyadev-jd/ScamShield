// Labeled messages for tuning the rule-based mock. Written for this purpose
// (synthetic), modelled on published RBI / cybercrime.gov.in advisories and
// common bank, telecom and commerce SMS formats. [text, isScam, sender?]
//
// TUNE is used while adjusting rules; HOLDOUT is only scored, never tuned on,
// to catch rules that merely memorize TUNE.

export const TUNE = [
  // --- scams: account / KYC / OTP
  ['URGENT: Your bank account will be suspended today. Verify your account immediately to avoid losing access.', true],
  ['URGENT! Your SBI KYC exp1red. Account will be blocked today. Verify 0TP at sbi-kyc.xyz', true],
  ['Dear user, your PAN is not linked. Your account will be blocked. Update now: bit.ly/pan-upd', true],
  ['Your HDFC netbanking is deactivated due to incomplete KYC. Click hdfc-kyc-update.info to reactivate', true],
  ['Dear Customer, your YONO account has been temporarily locked. Update your PAN card now to unlock: yono-sbi.online', true],
  ['Your debit card has been blocked due to suspicious activity. Call our customer care 9876543210 to unblock.', true],
  ['ICICI: Your credit card reward points worth Rs 7,850 expire today. Redeem now at icici-rewards.site', true],
  ['Bank official here. To stop the unauthorized transaction please share the OTP you just received.', true],
  ['Your KYC documents are pending. Your wallet will be closed within 24 hours. Complete KYC: tinyurl.com/kyc-pay', true],
  ['Dear customer your account is frozen by RBI. Update Aadhaar immediately to avoid permanent closure.', true],
  // --- scams: prize / lottery / cashback
  ["You are today's lucky winner! A cash reward of ₹25,000 has been reserved for you. Claim before midnight.", true],
  ['C o n g r a t s! You w0n Rs 25,00,000 in KBC l0ttery. Claim prize: tinyurl.com/kbc-claim', true],
  ['Congratulations! Your number has been selected for an iPhone 15. Pay Rs 99 delivery charge to claim.', true],
  ['You have received a cashback of Rs 2,500 on Paytm. Accept the request to credit it to your account.', true],
  ['Your mobile number won 2 crore in the WhatsApp lucky draw. Contact manager on WhatsApp to claim.', true],
  // --- scams: courier / customs / digital arrest
  ['IndiaPost: Your parcel is held at customs. Pay Rs 49 fee within 24 hrs or it will be returned: bit.ly/ip-redel', true],
  ['FedEx: A parcel in your name contains illegal items. Press 1 to speak to the customs officer.', true],
  ['This is CBI Mumbai. A parcel with narcotics is registered on your Aadhaar. Arrest warrant issued. Call immediately on video to avoid arrest.', true],
  ['Mumbai Police cyber cell: your number is linked to a money laundering case. Stay on video call, do not disconnect.', true],
  ['Your delivery failed due to incomplete address. Update address here: indiapost-track.top', true],
  // --- scams: job / task / investment
  ['Part time job! Earn Rs 3000 daily income by liking YouTube videos. Simple task. Contact on Telegram now.', true],
  ['Hiring now: work from home, earn 5000-8000 per day. No experience needed. WhatsApp HR 9XXXXXXXX1', true],
  ['Join our stock tips group and get 300% guaranteed returns in one week. Limited seats: t.me/profitking', true],
  ['Amazon part-time task: rate products and earn Rs 150 per review. Prepaid task deposit required.', true],
  // --- scams: UPI / payment / utility / family
  ['Hi, I sent Rs 5000 to your UPI by mistake. Please accept the collect request I sent to return it. Urgent, my mother is in hospital.', true],
  ['Dear consumer your electricity power will be disconnected tonight at 9.30pm because previous month bill was not updated. Call officer 88XXXXXX42', true],
  ['Your gas connection will be cut today due to pending KYC. Contact 7XXXXXXXX3 immediately.', true],
  ['Income Tax refund of Rs 15,490 approved. Submit your bank details to receive it: incometax-refund.info', true],
  ['Your recent payment could not be processed. Please verify your banking details to receive your refund.', true],
  ['Transaction failed. Rs 1,499 will be refunded once you confirm your card information here: pay-refund.site', true],
  ['Hi Mum, I dropped my phone and this is my new number. Can you send Rs 8000 urgently? I will explain later.', true],
  ['Your SIM will be deactivated within 2 hours as per TRAI. Press 9 to talk to customer executive.', true],
  // --- legit: bank / OTP / payments
  ['Dear Customer, your A/c XX4521 is debited by Rs 1,250.00 on 24Sep26 by UPI ref 426811. Not you? Call 1800111109. -SBI', false, 'VM-SBIINB'],
  ['482913 is the OTP for your HDFC Bank transaction of Rs 2,999. Valid for 5 mins. Do not share this OTP with anyone.', false, 'VK-HDFCBK'],
  ['Your OTP for login is 553201. Do not share it with anyone. -ICICI Bank', false],
  ['Rs 500.00 credited to your A/c XX9912 on 25-09-26 by UPI from RAHUL K. Avl Bal Rs 12,430.55 -Axis Bank', false],
  ['Your credit card statement for Sep is ready. Total due Rs 8,245, minimum due Rs 413, due date 05-Oct. -HDFC Bank', false],
  ['Your EMI of Rs 4,599 for loan XX2201 will be auto-debited on 03-Oct. Keep sufficient balance. -Bajaj Finance', false],
  ['Your KYC has been successfully updated. Thank you for banking with us. -Kotak', false],
  ['Transaction of Rs 1,999 at AMAZON on card XX4410 declined due to incorrect PIN. -SBI Card', false],
  // --- legit: commerce / travel / services
  ['Your Amazon order #408-1182 has been shipped and will arrive by Sat, 27 Sep. Track in the Amazon app.', false],
  ['PNR 4521887602, Train 12627, 28-Sep, SL S4 32. Chart prepared. Happy journey. -IRCTC', false],
  ['Your Swiggy order is out for delivery. Delivery partner Ramesh will reach in 10 mins.', false],
  ['Your parcel with AWB 7788123 has been delivered. Thank you for choosing Blue Dart.', false],
  ['Dear customer, your electricity bill of Rs 1,240 is due on 30 Sep. Pay via the official app. -TNEB', false],
  ['Your Airtel bill of Rs 499 is due on 02-Oct. Pay on Airtel Thanks app to avoid late fee.', false],
  ['Reminder: your appointment with Dr. Mehta is today at 4 pm. Reply C to confirm.', false],
  ['Your refund of Rs 649 for order #40-2218 has been initiated and will reach your account in 5-7 days. -Amazon', false],
  ['Payment of Rs 1,200 to Zomato failed. Any amount debited will be refunded within 48 hours. -HDFC Bank', false],
  ['Your Uber OTP is 4821. Share it with your driver to start the trip.', false],
  // --- legit: promotions (spam at worst, not scams)
  ['Recharge with Rs 349 and get 2GB/day for 28 days. Recharge on MyJio app or jio.com. T&C apply.', false, 'VM-JIOINF'],
  ['Big Diwali sale! Flat 50% off on all electronics, today only. Shop now at flipkart.com', false],
  ['Get flat 60% off on winter wear. Sale ends Sunday. Shop now at myntra.com T&C', false],
  ['Congratulations on your new Zomato Gold membership! Enjoy free delivery on all orders.', false],
  // --- legit: personal
  ['Hey, are we still meeting at 7 near the station? Call me when you reach.', false],
  ['Happy birthday! Have a great year ahead. Party tonight at our place, come by 8.', false],
  ['Mom please call me urgently when you see this, nothing serious, just need to ask something.', false],
  ['Can you share the notes from today\'s class? Exam is tomorrow.', false],
]

export const HOLDOUT = [
  ['Dear SBI customer, your account will be blocked in 24 hrs. Complete e-KYC here: sbi-ekyc.live', true],
  ['Your Aadhaar-linked bank account is suspended. Call 8XXXXXXXX0 immediately to reactivate.', true],
  ['Lucky draw winner! You won a Tata Safari. Pay registration fee Rs 12,500 to receive the car.', true],
  ['DHL: shipment on hold, customs duty Rs 199 unpaid. Pay now or package will be destroyed: dhl-pay.xyz', true],
  ['This is Delhi Police. Your Aadhaar is used in a drug case. You are under digital arrest. Do not tell family.', true],
  ['Earn Rs 2000 per day by completing simple online tasks. Message us on Telegram to start.', true],
  ['Your electricity will be disconnected at 10 pm. Update your bill immediately, call 9XXXXXXXX7', true],
  ['Your PhonePe account is on hold. Share the verification code sent to you to restore access.', true],
  ['Congrats! Rs 10,000 Google Pay reward unlocked. Scan the QR code to receive the amount.', true],
  ['Your Netflix account is locked. Update payment details immediately at netflix-billing.top', true],
  ['Rs 2,000.00 debited from A/c XX7781 on 25-Sep for NEFT to PRIYA S. If not done by you, call 18002662. -ICICI', false, 'AX-ICICIB'],
  ['719204 is your OTP to log in to Paytm. Never share it with anyone, including Paytm staff.', false, 'VM-PAYTMB'],
  ['Your Flipkart order of boAt headphones will be delivered today by 9 PM.', false],
  ['Your BSNL broadband bill of Rs 799 is generated. Due date 10-Oct. Pay online at bsnl.co.in', false],
  ['Dear customer, your FASTag balance is low (Rs 85). Recharge to avoid penalty at toll plazas. -NHAI', false],
  ['Hurry! End of season sale, up to 70% off. Visit your nearest Westside store.', false],
  ['Your cheque no 000123 for Rs 15,000 has been cleared. -Canara Bank', false],
  ['Hi, reached home safely. Will call you tomorrow morning.', false],
  ['Your LIC premium of Rs 6,230 is due on 15-Oct. Pay via LIC app or licindia.in', false],
  ['Your OTP to verify your email on Naukri is 382019. Valid for 10 minutes.', false],
]
