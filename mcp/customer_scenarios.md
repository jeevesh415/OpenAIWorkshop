# Customer Scenarios – Answer Key Included

## Scenario 1: Invoice Higher Than Usual

**Customer ID**: 251  
**Name**: John Doe  
**Email**: scenario1@example.com  
**Phone**: 555-0001  
**Address**: 123 Main St, City  
**Loyalty**: Silver  

**Challenge**: Latest invoice shows $150, 2.5× the usual amount.

**Solution**:

1. SELECT last 6 invoices → detect $150 outlier (std-dev or >50% above mean).
2. Cross-check DataUsage for same billing cycle → find ~22 GB vs plan's 10 GB cap.
3. Quote **Data Overage Policy – "may retroactively upgrade within 15 days"**.
4. Offer: (a) file invoice-adjustment; (b) upgrade plan & credit overage pro-rata.
5. Note that $50 already paid; $100 balance remains.

---

## Scenario 2: Internet Slower Than Before

**Customer ID**: 252  
**Name**: Jane Doe  
**Email**: scenario2@example.com  
**Phone**: 555-0002  
**Address**: 234 Elm St, Town  
**Loyalty**: Gold  

**Challenge**: Throughput much lower than advertised 1 Gbps tier.

**Solution**:

1. Confirm Subscriptions.service_status = 'slow'.
2. Query ServiceIncidents – open ticket still 'investigating'.
3. Use KB: **Troubleshooting Slow Internet – Basic Steps**.
4. Ask customer to run speed-test, reboot; escalate if still <25% of tier.

---

## Scenario 3: Travelling Abroad – Needs Roaming

**Customer ID**: 253  
**Name**: Mark Doe  
**Email**: scenario3@example.com  
**Phone**: 555-0003  
**Address**: 345 Oak St, Village  
**Loyalty**: Bronze  

**Challenge**: Leaving for Spain in 2 days, unsure how to enable roaming.

**Solution**:

1. Subscriptions.roaming_enabled = 0 → verify not active.
2. Check product offerings → suggest 'International Roaming' add-on.
3. Quote **International Roaming Options Explained**: must activate ≥3 days ahead.
4. Offer immediate activation with pro-rated charges.

---

## Scenario 4: Account Locked After Failed Logins

**Customer ID**: 254  
**Name**: Alice Doe  
**Email**: scenario4@example.com  
**Phone**: 555-0004  
**Address**: 456 Pine St, Hamlet  
**Loyalty**: Gold  

**Challenge**: Can't log in; sees 'Account Locked' message.

**Solution**:

1. Query SecurityLogs → 8 failed attempts + 1 account_locked event.
2. Verify customer identity (last 4 of SSN, DOB, etc.).
3. Quote **Account Security Policy – Unlock Procedure**.
4. Call unlock_account tool.
5. Recommend password reset & 2FA setup.

---

