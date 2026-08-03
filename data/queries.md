# Query Set — Meridian Grid Technologies HR Corpus

**Total queries:** 78  |  **answer:** 46  |  **conflict:** 16  |  **insufficient:** 16

Every query is derived from `ground_truth.json`. `trace` gives the fact/conflict/gap ID it targets. `expected_sources` are filenames; `expected_conflict_pair` is set only for conflict queries.

| Category | Count |
|---|---|
| single-fact lookup | 18 |
| multi-part | 10 |
| cross-document comparison | 10 |
| conflict-probing | 10 |
| out-of-scope / insufficient | 10 |
| aggregation / list-all | 8 |
| scenario / applied | 12 |


## single-fact lookup

| ID | Query | Decision | Trace | Sources / conflict pair | Key facts |
|---|---|---|---|---|---|
| Q001 | How many days of annual leave do full-time employees get? | **answer** | annual_leave_base | Leave_and_Time_Off_Policy.docx | 25 days per year plus 8 bank holidays |
| Q002 | What is the maximum annual leave I can carry over to next year? | **answer** | carryover_cap | Leave_and_Time_Off_Policy.docx | 5 days, to be used by 31 March |
| Q003 | How many weeks of full pay does enhanced maternity leave provide? | **answer** | maternity | Leave_and_Time_Off_Policy.docx | 16 weeks at full pay |
| Q004 | How much paternity leave is offered? | **answer** | paternity | Leave_and_Time_Off_Policy.docx | 4 weeks at full pay |
| Q005 | What is the business mileage reimbursement rate? | **answer** | mileage | Travel_and_Expense_Policy.docx | 45p/mile for first 10,000 miles, 25p/mile thereafter |
| Q006 | What is the deadline for submitting an expense claim? | **answer** | expense_deadline | Travel_and_Expense_Policy.docx | Within 30 days of the cost being incurred |
| Q007 | What is the hotel room cap for a stay in London? | **answer** | hotel_caps | Travel_and_Expense_Policy.docx | GBP 180 per night in London |
| Q008 | What is the subsistence cap for an evening meal? | **answer** | subsistence | Travel_and_Expense_Policy.docx | GBP 30 for an evening meal |
| Q009 | Over what value must a gift be declared? | **answer** | gift_threshold | Code_of_Conduct_and_Disciplinary_Policy.docx | Any gift over GBP 50 |
| Q010 | What is the minimum password length? | **answer** | password_length | IT_and_Acceptable_Use_Policy.docx | 14 characters |
| Q011 | How much is the employee referral bonus? | **answer** | referral_bonus | Recruitment_and_Onboarding_Policy.docx | GBP 1,500 |
| Q012 | What is the ratio of trained first-aiders to employees? | **answer** | first_aider_ratio | Health_and_Safety_Policy.docx | At least 1 first-aider per 50 employees on site |
| Q013 | How often are fire evacuation drills held? | **answer** | fire_drills | Health_and_Safety_Policy.docx | Quarterly at each office |
| Q014 | What performance rating scale is used? | **answer** | rating_scale | Performance_Management_Policy.docx | A scale of 1 to 5 (3 = fully meets expectations) |
| Q015 | What multiple of salary is provided as life assurance? | **answer** | life_assurance | Compensation_and_Benefits_Policy.docx | 4 times base salary |
| Q016 | Am I eligible for a company car? | **insufficient** | G1 | — | No document covers a company car scheme |
| Q017 | Does the company offer share options or stock to employees? | **insufficient** | G2 | — | No share/equity scheme is described anywhere |
| Q018 | Is jury service paid? | **insufficient** | G5 | — | Jury service pay is not covered by any policy |

## multi-part

| ID | Query | Decision | Trace | Sources / conflict pair | Key facts |
|---|---|---|---|---|---|
| Q019 | What is the annual leave entitlement and how many days can be carried over? | **answer** | annual_leave_base+carryover_cap | Leave_and_Time_Off_Policy.docx | 25 days/year; carry over up to 5 days |
| Q020 | What is the mileage rate and the deadline to claim it? | **answer** | mileage+expense_deadline | Travel_and_Expense_Policy.docx | 45p/25p per mile; claim within 30 days |
| Q021 | How much maternity and paternity leave is provided? | **answer** | maternity+paternity | Leave_and_Time_Off_Policy.docx | Maternity 16 weeks full pay; paternity 4 weeks full pay |
| Q022 | What is the minimum password length and is multi-factor authentication required? | **answer** | password_length+mfa | IT_and_Acceptable_Use_Policy.docx | 14 characters; MFA mandatory for remote access and cloud apps |
| Q023 | What are the subsistence caps for breakfast and an evening meal? | **answer** | subsistence | Travel_and_Expense_Policy.docx | GBP 10 breakfast; GBP 30 evening meal |
| Q024 | What are the hotel caps in London and elsewhere in the UK? | **answer** | hotel_caps | Travel_and_Expense_Policy.docx | GBP 180/night London; GBP 120/night elsewhere |
| Q025 | How large is the annual bonus and when is it paid? | **answer** | bonus | Compensation_and_Benefits_Policy.docx | Up to 10% of base salary; paid in April payroll |
| Q026 | What is the first-aider ratio and how often are fire drills held? | **answer** | first_aider_ratio+fire_drills | Health_and_Safety_Policy.docx | 1 first-aider per 50 employees; quarterly fire drills |
| Q027 | When are performance reviews held and what rating scale is used? | **answer** | review_cycle+rating_scale | Performance_Management_Policy.docx | Twice yearly (July, January); 1-5 rating scale |
| Q028 | What relocation allowance and childcare support does the company provide? | **insufficient** | G3+G4 | — | Neither relocation support nor childcare is covered |

## cross-document comparison

| ID | Query | Decision | Trace | Sources / conflict pair | Key facts |
|---|---|---|---|---|---|
| Q029 | What is the standard full-time working week across the company?<br>_Agreeing fact (same value 37.5 in both docs) — safe._ | **answer** | working_week | Employee_Handbook.docx, Flexible_and_Remote_Work_Policy.docx | 37.5 hours/week — stated consistently in the Handbook and Flexible Work policy |
| Q030 | Compare annual leave entitlement with sabbatical eligibility. | **answer** | annual_leave_base+sabbatical | Leave_and_Time_Off_Policy.docx | 25 days base leave; sabbatical after 5 years' service |
| Q031 | How does the mileage rate change after 10,000 miles? | **answer** | mileage | Travel_and_Expense_Policy.docx | 45p/mile up to 10,000 miles, then 25p/mile |
| Q032 | Compare the expense approval limit for a line manager versus a department head. | **answer** | expense_approval | Travel_and_Expense_Policy.docx | Line manager approves up to GBP 500; above GBP 500 needs department head |
| Q033 | Compare when salary reviews take effect with when promotions take effect.<br>_Both state '1 April' (same value) — agreeing, safe._ | **answer** | pay_review+promotion | Compensation_and_Benefits_Policy.docx, Performance_Management_Policy.docx | Both take effect from 1 April |
| Q034 | How many days of compassionate leave are provided compared with paternity leave? | **answer** | compassionate+paternity | Leave_and_Time_Off_Policy.docx | Compassionate up to 5 days; paternity 4 weeks |
| Q035 | Compare the maximum remote-working days per week in the current and the 2023 policies. | **conflict** | C2 | Flexible_and_Remote_Work_Policy.docx + Remote_Working_Policy_2023_Superseded.docx | Current 2025 policy says 3 days/week; superseded 2023 policy says 2 days/week |
| Q036 | What does the probationary period length say in the Handbook versus the Recruitment policy? | **conflict** | C1 | Employee_Handbook.docx + Recruitment_and_Onboarding_Policy.docx | Handbook says 3 months; Recruitment says 6 months |
| Q037 | Compare the employer pension contribution in the Handbook and the Compensation policy. | **conflict** | C3 | Employee_Handbook.docx + Compensation_and_Benefits_Policy.docx | Handbook says 5%; Compensation says 6% |
| Q038 | Compare the rule on personal-device email access in the IT policy and the Code of Conduct. | **conflict** | C4 | IT_and_Acceptable_Use_Policy.docx + Code_of_Conduct_and_Disciplinary_Policy.docx | IT permits it; Code of Conduct prohibits it |

## conflict-probing

| ID | Query | Decision | Trace | Sources / conflict pair | Key facts |
|---|---|---|---|---|---|
| Q039 | How many days per week am I allowed to work remotely? | **conflict** | C2 | Flexible_and_Remote_Work_Policy.docx + Remote_Working_Policy_2023_Superseded.docx | Conflict: 3 days/week (2025) vs 2 days/week (2023) |
| Q040 | What is the probationary period for new employees? | **conflict** | C1 | Employee_Handbook.docx + Recruitment_and_Onboarding_Policy.docx | Conflict: 3 months (Handbook) vs 6 months (Recruitment) |
| Q041 | What percentage does the employer contribute to my pension? | **conflict** | C3 | Employee_Handbook.docx + Compensation_and_Benefits_Policy.docx | Conflict: 5% (Handbook) vs 6% (Compensation) |
| Q042 | Can I use my personal phone to access work email? | **conflict** | C4 | IT_and_Acceptable_Use_Policy.docx + Code_of_Conduct_and_Disciplinary_Policy.docx | Conflict: permitted (IT) vs prohibited (Code of Conduct) |
| Q043 | What is the maximum number of remote working days allowed per week? | **conflict** | C2 | Flexible_and_Remote_Work_Policy.docx + Remote_Working_Policy_2023_Superseded.docx | Conflict: 3 vs 2 days/week |
| Q044 | How long is the probation period for a new starter? | **conflict** | C1 | Employee_Handbook.docx + Recruitment_and_Onboarding_Policy.docx | Conflict: 3 vs 6 months |
| Q045 | What is the employer pension contribution rate? | **conflict** | C3 | Employee_Handbook.docx + Compensation_and_Benefits_Policy.docx | Conflict: 5% vs 6% |
| Q046 | Is accessing corporate email on a personal mobile device allowed? | **conflict** | C4 | IT_and_Acceptable_Use_Policy.docx + Code_of_Conduct_and_Disciplinary_Policy.docx | Conflict: permitted vs prohibited |
| Q047 | Up to how many days a week can eligible employees work from home? | **conflict** | C2 | Flexible_and_Remote_Work_Policy.docx + Remote_Working_Policy_2023_Superseded.docx | Conflict: 3 vs 2 days/week |
| Q048 | What is the length of the probationary period at the company? | **conflict** | C1 | Employee_Handbook.docx + Recruitment_and_Onboarding_Policy.docx | Conflict: 3 vs 6 months |

## out-of-scope / insufficient

| ID | Query | Decision | Trace | Sources / conflict pair | Key facts |
|---|---|---|---|---|---|
| Q049 | What is the company's current stock price? | **insufficient** | out-of-scope | — | Not in scope; MGT is private and no share price exists in the corpus |
| Q050 | Can I bring my dog to the office? | **insufficient** | G6 | — | No policy addresses pets in the workplace |
| Q051 | What relocation allowance is available when moving for a role? | **insufficient** | G3 | — | No relocation support is described |
| Q052 | Are childcare vouchers or an on-site nursery available? | **insufficient** | G4 | — | No childcare benefit is mentioned |
| Q053 | How do I receive equity or share options? | **insufficient** | G2 | — | No equity/share scheme exists in any policy |
| Q054 | What are the eligibility rules for a company car? | **insufficient** | G1 | — | No company car scheme is offered |
| Q055 | Will I be paid while on jury service? | **insufficient** | G5 | — | Jury service pay is not covered |
| Q056 | What is the CEO's total annual salary? | **insufficient** | out-of-scope | — | Individual executive pay is not in the corpus |
| Q057 | Does the company pay for a gym membership? | **insufficient** | out-of-scope | — | No gym/fitness benefit is listed among core benefits |
| Q058 | Is dental insurance included in benefits? | **insufficient** | out-of-scope | — | Only private medical is offered; dental is not mentioned |

## aggregation / list-all

| ID | Query | Decision | Trace | Sources / conflict pair | Key facts |
|---|---|---|---|---|---|
| Q059 | List all the types of leave available to employees. | **answer** | leave_types | Leave_and_Time_Off_Policy.docx | Annual, sickness, maternity, paternity, adoption, shared parental, compassionate/bereavement, sabbatical, public duties |
| Q060 | What are the data classification levels used by the company? | **answer** | data_classes | IT_and_Acceptable_Use_Policy.docx | Public, Internal, Confidential, Restricted |
| Q061 | What core benefits does the company offer? | **answer** | benefits_list | Compensation_and_Benefits_Policy.docx | Private medical, life assurance 4x, EAP, cycle-to-work, EV salary-sacrifice, season-ticket loan |
| Q062 | List the stages of the disciplinary procedure. | **answer** | disciplinary | Code_of_Conduct_and_Disciplinary_Policy.docx | Informal discussion, first written warning, final written warning, dismissal |
| Q063 | How does annual leave increase with length of service? | **answer** | annual_leave_base+annual_leave_5yr+annual_leave_10yr | Leave_and_Time_Off_Policy.docx | 25 days base, 27 after 5 years, 30 after 10 years |
| Q064 | What personal protective equipment is required for field work? | **answer** | ppe | Health_and_Safety_Policy.docx | Minimum: hard hat, safety boots, high-visibility vest on operational sites |
| Q065 | What pre-employment checks are carried out before a new hire starts? | **answer** | right_to_work | Recruitment_and_Onboarding_Policy.docx | Right-to-work checks and references covering the previous 3 years; extra screening for some roles |
| Q066 | What are the expense approval thresholds and accommodation caps? | **answer** | expense_approval+hotel_caps | Travel_and_Expense_Policy.docx | <=GBP 500 line manager, >GBP 500 dept head; hotels GBP 180 London / GBP 120 elsewhere |

## scenario / applied

| ID | Query | Decision | Trace | Sources / conflict pair | Key facts |
|---|---|---|---|---|---|
| Q067 | I have completed 6 years of service. How many annual leave days am I entitled to? | **answer** | annual_leave_5yr | Leave_and_Time_Off_Policy.docx | 27 days per year (5-9 years band) |
| Q068 | I drove 12,000 business miles this year in my own car. How is that reimbursed? | **answer** | mileage | Travel_and_Expense_Policy.docx | 45p for the first 10,000 miles and 25p for the remaining 2,000 miles |
| Q069 | I have 3 years' service and want a sabbatical. Am I eligible? | **answer** | sabbatical | Leave_and_Time_Off_Policy.docx | No — sabbaticals require at least 5 years' continuous service |
| Q070 | A supplier offered me a gift worth GBP 70. What should I do? | **answer** | gift_threshold | Code_of_Conduct_and_Disciplinary_Policy.docx | Decline it or declare it in the gifts register (anything over GBP 50) |
| Q071 | I have been off sick long-term after 2 years' service. What sick pay do I get? | **answer** | sick_pay | Leave_and_Time_Off_Policy.docx | 3 months at full pay then 3 months at half pay in a rolling 12 months |
| Q072 | As a new starter, when will my first formal performance review be? | **answer** | review_cycle | Performance_Management_Policy.docx | At the next mid-year (July) or year-end (January) review |
| Q073 | I want to claim an expense from 45 days ago. Will it be paid? | **answer** | expense_deadline | Travel_and_Expense_Policy.docx | It may be refused — claims must be submitted within 30 days |
| Q074 | I am booking a hotel in London for a business trip. What is the nightly limit? | **answer** | hotel_caps | Travel_and_Expense_Policy.docx | GBP 180 per night in London |
| Q075 | I am a new employee. How long is my probationary period? | **conflict** | C1 | Employee_Handbook.docx + Recruitment_and_Onboarding_Policy.docx | Conflict: Handbook 3 months vs Recruitment 6 months |
| Q076 | I would like to work from home. How many days a week can I do that? | **conflict** | C2 | Flexible_and_Remote_Work_Policy.docx + Remote_Working_Policy_2023_Superseded.docx | Conflict: current 3 days/week vs superseded 2 days/week |
| Q077 | I am relocating cities for this role. What relocation support can I claim? | **insufficient** | G3 | — | No relocation support is described in any policy |
| Q078 | Can I bring my pet to work on Fridays? | **insufficient** | G6 | — | No policy addresses pets in the workplace |