# Phase 5 — Self-Verification Report

Automated check of all 78 queries against the authored document text (via the pipeline's own DocumentLoader).

**Result: 78/78 verified, 0 failures.**

- **answer/conflict**: each cited source must literally contain its evidence sentence.
- **insufficient**: each distinguishing term must be absent from the entire corpus.


## single-fact lookup

**Q001** [answer] — PASS ✅ — _How many days of annual leave do full-time employees get?_
  - `Leave_and_Time_Off_Policy.docx`: ✓ "The standard annual leave entitlement is 25 days per year for full-time employees, in addition to the 8 public bank holidays recognised in England and Wales."

**Q002** [answer] — PASS ✅ — _What is the maximum annual leave I can carry over to next year?_
  - `Leave_and_Time_Off_Policy.docx`: ✓ "Employees may carry over a maximum of 5 days of unused annual leave into the following leave year."

**Q003** [answer] — PASS ✅ — _How many weeks of full pay does enhanced maternity leave provide?_
  - `Leave_and_Time_Off_Policy.docx`: ✓ "Eligible employees are entitled to enhanced maternity pay of 16 weeks at full pay, followed by 23 weeks at the prevailing rate of Statutory Maternity Pay, and a further 13 weeks unpaid, giving a total of up to 52 weeks of maternity leave."

**Q004** [answer] — PASS ✅ — _How much paternity leave is offered?_
  - `Leave_and_Time_Off_Policy.docx`: ✓ "Eligible employees are entitled to 4 weeks of paternity leave at full pay, to be taken within 52 weeks of the birth or placement for adoption."

**Q005** [answer] — PASS ✅ — _What is the business mileage reimbursement rate?_
  - `Travel_and_Expense_Policy.docx`: ✓ "Where employees use their own vehicle for business travel, mileage is reimbursed at 45 pence per mile for the first 10,000 business miles in the tax year, and 25 pence per mile for any additional business miles."

**Q006** [answer] — PASS ✅ — _What is the deadline for submitting an expense claim?_
  - `Travel_and_Expense_Policy.docx`: ✓ "All expense claims must be submitted through the expense system within 30 days of the date the cost was incurred."

**Q007** [answer] — PASS ✅ — _What is the hotel room cap for a stay in London?_
  - `Travel_and_Expense_Policy.docx`: ✓ "Where an overnight stay is required, the maximum room rate the company will reimburse is GBP 180 per night in London and GBP 120 per night elsewhere in the United Kingdom."

**Q008** [answer] — PASS ✅ — _What is the subsistence cap for an evening meal?_
  - `Travel_and_Expense_Policy.docx`: ✓ "The subsistence caps are GBP 10 for breakfast and GBP 30 for an evening meal, supported by receipts."

**Q009** [answer] — PASS ✅ — _Over what value must a gift be declared?_
  - `Code_of_Conduct_and_Disciplinary_Policy.docx`: ✓ "Any gift or hospitality with a value over GBP 50 must be declined or, where declining would cause offence, declared in the gifts and hospitality register and referred to a manager."

**Q010** [answer] — PASS ✅ — _What is the minimum password length?_
  - `IT_and_Acceptable_Use_Policy.docx`: ✓ "Passwords must be a minimum of 14 characters and must not be reused across systems."

**Q011** [answer] — PASS ✅ — _How much is the employee referral bonus?_
  - `Recruitment_and_Onboarding_Policy.docx`: ✓ "Employees who refer a candidate who is successfully appointed and completes probation are eligible for a referral bonus of GBP 1,500, paid in the payroll following confirmation of the new hire's probation."

**Q012** [answer] — PASS ✅ — _What is the ratio of trained first-aiders to employees?_
  - `Health_and_Safety_Policy.docx`: ✓ "The company maintains a ratio of at least 1 trained first-aider for every 50 employees on site."

**Q013** [answer] — PASS ✅ — _How often are fire evacuation drills held?_
  - `Health_and_Safety_Policy.docx`: ✓ "Fire evacuation drills are carried out quarterly at each office."

**Q014** [answer] — PASS ✅ — _What performance rating scale is used?_
  - `Performance_Management_Policy.docx`: ✓ "At the year-end review, overall performance is scored on a rating scale of 1 to 5, where 1 is 'below expectations' and 5 is 'outstanding'."

**Q015** [answer] — PASS ✅ — _What multiple of salary is provided as life assurance?_
  - `Compensation_and_Benefits_Policy.docx`: ✓ "Life assurance is provided at 4 times base salary."

**Q016** [insufficient] — PASS ✅ — _Am I eligible for a company car?_
  - term 'company car': ✓ absent

**Q017** [insufficient] — PASS ✅ — _Does the company offer share options or stock to employees?_
  - term 'share option': ✓ absent
  - term 'equity': ✓ absent

**Q018** [insufficient] — PASS ✅ — _Is jury service paid?_
  - term 'jury': ✓ absent


## multi-part

**Q019** [answer] — PASS ✅ — _What is the annual leave entitlement and how many days can be carried over?_
  - `Leave_and_Time_Off_Policy.docx`: ✓ "The standard annual leave entitlement is 25 days per year for full-time employees, in addition to the 8 public bank holidays recognised in England and Wales."
  - `Leave_and_Time_Off_Policy.docx`: ✓ "Employees may carry over a maximum of 5 days of unused annual leave into the following leave year."

**Q020** [answer] — PASS ✅ — _What is the mileage rate and the deadline to claim it?_
  - `Travel_and_Expense_Policy.docx`: ✓ "Where employees use their own vehicle for business travel, mileage is reimbursed at 45 pence per mile for the first 10,000 business miles in the tax year, and 25 pence per mile for any additional business miles."
  - `Travel_and_Expense_Policy.docx`: ✓ "All expense claims must be submitted through the expense system within 30 days of the date the cost was incurred."

**Q021** [answer] — PASS ✅ — _How much maternity and paternity leave is provided?_
  - `Leave_and_Time_Off_Policy.docx`: ✓ "Eligible employees are entitled to enhanced maternity pay of 16 weeks at full pay, followed by 23 weeks at the prevailing rate of Statutory Maternity Pay, and a further 13 weeks unpaid, giving a total of up to 52 weeks of maternity leave."
  - `Leave_and_Time_Off_Policy.docx`: ✓ "Eligible employees are entitled to 4 weeks of paternity leave at full pay, to be taken within 52 weeks of the birth or placement for adoption."

**Q022** [answer] — PASS ✅ — _What is the minimum password length and is multi-factor authentication required?_
  - `IT_and_Acceptable_Use_Policy.docx`: ✓ "Passwords must be a minimum of 14 characters and must not be reused across systems."
  - `IT_and_Acceptable_Use_Policy.docx`: ✓ "Multi-factor authentication is mandatory for all remote access and for all cloud-based business applications."

**Q023** [answer] — PASS ✅ — _What are the subsistence caps for breakfast and an evening meal?_
  - `Travel_and_Expense_Policy.docx`: ✓ "The subsistence caps are GBP 10 for breakfast and GBP 30 for an evening meal, supported by receipts."
  - `Travel_and_Expense_Policy.docx`: ✓ "The subsistence caps are GBP 10 for breakfast and GBP 30 for an evening meal, supported by receipts."

**Q024** [answer] — PASS ✅ — _What are the hotel caps in London and elsewhere in the UK?_
  - `Travel_and_Expense_Policy.docx`: ✓ "Where an overnight stay is required, the maximum room rate the company will reimburse is GBP 180 per night in London and GBP 120 per night elsewhere in the United Kingdom."
  - `Travel_and_Expense_Policy.docx`: ✓ "Where an overnight stay is required, the maximum room rate the company will reimburse is GBP 180 per night in London and GBP 120 per night elsewhere in the United Kingdom."

**Q025** [answer] — PASS ✅ — _How large is the annual bonus and when is it paid?_
  - `Compensation_and_Benefits_Policy.docx`: ✓ "Employees are eligible for a discretionary annual bonus of up to 10% of base salary, based on a combination of company performance against targets and individual performance rating."
  - `Compensation_and_Benefits_Policy.docx`: ✓ "Bonuses are paid in the April payroll following the performance year and require the employee to be in employment and not under notice at the payment date."

**Q026** [answer] — PASS ✅ — _What is the first-aider ratio and how often are fire drills held?_
  - `Health_and_Safety_Policy.docx`: ✓ "The company maintains a ratio of at least 1 trained first-aider for every 50 employees on site."
  - `Health_and_Safety_Policy.docx`: ✓ "Fire evacuation drills are carried out quarterly at each office."

**Q027** [answer] — PASS ✅ — _When are performance reviews held and what rating scale is used?_
  - `Performance_Management_Policy.docx`: ✓ "Formal performance reviews are conducted twice per year: a mid-year review in July and a year-end review in January."
  - `Performance_Management_Policy.docx`: ✓ "At the year-end review, overall performance is scored on a rating scale of 1 to 5, where 1 is 'below expectations' and 5 is 'outstanding'."

**Q028** [insufficient] — PASS ✅ — _What relocation allowance and childcare support does the company provide?_
  - term 'relocation': ✓ absent
  - term 'childcare': ✓ absent
  - term 'nursery': ✓ absent


## cross-document comparison

**Q029** [answer] — PASS ✅ — _What is the standard full-time working week across the company?_
  - `Employee_Handbook.docx`: ✓ "The standard full-time working week at Meridian Grid Technologies is 37.5 hours, worked Monday to Friday, exclusive of an unpaid one-hour lunch break each day."
  - `Flexible_and_Remote_Work_Policy.docx`: ✓ "Outside core hours, employees may flex their start and finish times between 07:00 and 19:00, provided they complete their contracted 37.5 hours per week and meet operational commitments."

**Q030** [answer] — PASS ✅ — _Compare annual leave entitlement with sabbatical eligibility._
  - `Leave_and_Time_Off_Policy.docx`: ✓ "The standard annual leave entitlement is 25 days per year for full-time employees, in addition to the 8 public bank holidays recognised in England and Wales."
  - `Leave_and_Time_Off_Policy.docx`: ✓ "Employees with at least 5 years of continuous service may apply for an unpaid sabbatical of between 1 and 6 months."

**Q031** [answer] — PASS ✅ — _How does the mileage rate change after 10,000 miles?_
  - `Travel_and_Expense_Policy.docx`: ✓ "Where employees use their own vehicle for business travel, mileage is reimbursed at 45 pence per mile for the first 10,000 business miles in the tax year, and 25 pence per mile for any additional business miles."

**Q032** [answer] — PASS ✅ — _Compare the expense approval limit for a line manager versus a department head._
  - `Travel_and_Expense_Policy.docx`: ✓ "Individual claims up to GBP 500 are approved by the line manager; claims above GBP 500 require additional approval from the department head."
  - `Travel_and_Expense_Policy.docx`: ✓ "Individual claims up to GBP 500 are approved by the line manager; claims above GBP 500 require additional approval from the department head."

**Q033** [answer] — PASS ✅ — _Compare when salary reviews take effect with when promotions take effect._
  - `Compensation_and_Benefits_Policy.docx`: ✓ "Salary reviews are conducted annually, and any increases take effect from 1 April."
  - `Performance_Management_Policy.docx`: ✓ "Promotions are considered once per year as part of the year-end review, with any promotions and associated salary changes taking effect from 1 April."

**Q034** [answer] — PASS ✅ — _How many days of compassionate leave are provided compared with paternity leave?_
  - `Leave_and_Time_Off_Policy.docx`: ✓ "Employees may take up to 5 days of paid compassionate leave following the death of a close family member."
  - `Leave_and_Time_Off_Policy.docx`: ✓ "Eligible employees are entitled to 4 weeks of paternity leave at full pay, to be taken within 52 weeks of the birth or placement for adoption."

**Q035** [conflict] — PASS ✅ — _Compare the maximum remote-working days per week in the current and the 2023 policies._
  - `Flexible_and_Remote_Work_Policy.docx`: ✓ "Eligible employees may work remotely for up to 3 days per week, with the remaining days worked from their assigned office."
  - `Remote_Working_Policy_2023_Superseded.docx`: ✓ "Eligible employees may work remotely for up to 2 days per week, with the remaining days worked from their assigned office."

**Q036** [conflict] — PASS ✅ — _What does the probationary period length say in the Handbook versus the Recruitment policy?_
  - `Employee_Handbook.docx`: ✓ "The probationary period for all new employees is 3 months from the start date."
  - `Recruitment_and_Onboarding_Policy.docx`: ✓ "The probationary period for all new employees is 6 months from the start date."

**Q037** [conflict] — PASS ✅ — _Compare the employer pension contribution in the Handbook and the Compensation policy._
  - `Employee_Handbook.docx`: ✓ "The employer contributes 5% of pensionable salary to the workplace pension scheme, and employees contribute a minimum of 4%."
  - `Compensation_and_Benefits_Policy.docx`: ✓ "The employer contributes 6% of pensionable salary to the workplace pension scheme."

**Q038** [conflict] — PASS ✅ — _Compare the rule on personal-device email access in the IT policy and the Code of Conduct._
  - `IT_and_Acceptable_Use_Policy.docx`: ✓ "The use of personal mobile devices to access corporate email is permitted for enrolled employees, provided the device is registered with the mobile-device-management system and protected by a passcode and remote-wipe capability."
  - `Code_of_Conduct_and_Disciplinary_Policy.docx`: ✓ "The use of personal mobile devices to access corporate email is prohibited at all times."


## conflict-probing

**Q039** [conflict] — PASS ✅ — _How many days per week am I allowed to work remotely?_
  - `Flexible_and_Remote_Work_Policy.docx`: ✓ "Eligible employees may work remotely for up to 3 days per week, with the remaining days worked from their assigned office."
  - `Remote_Working_Policy_2023_Superseded.docx`: ✓ "Eligible employees may work remotely for up to 2 days per week, with the remaining days worked from their assigned office."

**Q040** [conflict] — PASS ✅ — _What is the probationary period for new employees?_
  - `Employee_Handbook.docx`: ✓ "The probationary period for all new employees is 3 months from the start date."
  - `Recruitment_and_Onboarding_Policy.docx`: ✓ "The probationary period for all new employees is 6 months from the start date."

**Q041** [conflict] — PASS ✅ — _What percentage does the employer contribute to my pension?_
  - `Employee_Handbook.docx`: ✓ "The employer contributes 5% of pensionable salary to the workplace pension scheme, and employees contribute a minimum of 4%."
  - `Compensation_and_Benefits_Policy.docx`: ✓ "The employer contributes 6% of pensionable salary to the workplace pension scheme."

**Q042** [conflict] — PASS ✅ — _Can I use my personal phone to access work email?_
  - `IT_and_Acceptable_Use_Policy.docx`: ✓ "The use of personal mobile devices to access corporate email is permitted for enrolled employees, provided the device is registered with the mobile-device-management system and protected by a passcode and remote-wipe capability."
  - `Code_of_Conduct_and_Disciplinary_Policy.docx`: ✓ "The use of personal mobile devices to access corporate email is prohibited at all times."

**Q043** [conflict] — PASS ✅ — _What is the maximum number of remote working days allowed per week?_
  - `Flexible_and_Remote_Work_Policy.docx`: ✓ "Eligible employees may work remotely for up to 3 days per week, with the remaining days worked from their assigned office."
  - `Remote_Working_Policy_2023_Superseded.docx`: ✓ "Eligible employees may work remotely for up to 2 days per week, with the remaining days worked from their assigned office."

**Q044** [conflict] — PASS ✅ — _How long is the probation period for a new starter?_
  - `Employee_Handbook.docx`: ✓ "The probationary period for all new employees is 3 months from the start date."
  - `Recruitment_and_Onboarding_Policy.docx`: ✓ "The probationary period for all new employees is 6 months from the start date."

**Q045** [conflict] — PASS ✅ — _What is the employer pension contribution rate?_
  - `Employee_Handbook.docx`: ✓ "The employer contributes 5% of pensionable salary to the workplace pension scheme, and employees contribute a minimum of 4%."
  - `Compensation_and_Benefits_Policy.docx`: ✓ "The employer contributes 6% of pensionable salary to the workplace pension scheme."

**Q046** [conflict] — PASS ✅ — _Is accessing corporate email on a personal mobile device allowed?_
  - `IT_and_Acceptable_Use_Policy.docx`: ✓ "The use of personal mobile devices to access corporate email is permitted for enrolled employees, provided the device is registered with the mobile-device-management system and protected by a passcode and remote-wipe capability."
  - `Code_of_Conduct_and_Disciplinary_Policy.docx`: ✓ "The use of personal mobile devices to access corporate email is prohibited at all times."

**Q047** [conflict] — PASS ✅ — _Up to how many days a week can eligible employees work from home?_
  - `Flexible_and_Remote_Work_Policy.docx`: ✓ "Eligible employees may work remotely for up to 3 days per week, with the remaining days worked from their assigned office."
  - `Remote_Working_Policy_2023_Superseded.docx`: ✓ "Eligible employees may work remotely for up to 2 days per week, with the remaining days worked from their assigned office."

**Q048** [conflict] — PASS ✅ — _What is the length of the probationary period at the company?_
  - `Employee_Handbook.docx`: ✓ "The probationary period for all new employees is 3 months from the start date."
  - `Recruitment_and_Onboarding_Policy.docx`: ✓ "The probationary period for all new employees is 6 months from the start date."


## out-of-scope / insufficient

**Q049** [insufficient] — PASS ✅ — _What is the company's current stock price?_
  - term 'stock price': ✓ absent
  - term 'share price': ✓ absent

**Q050** [insufficient] — PASS ✅ — _Can I bring my dog to the office?_
  - term 'dog': ✓ absent
  - term 'pet': ✓ absent
  - term 'pets': ✓ absent

**Q051** [insufficient] — PASS ✅ — _What relocation allowance is available when moving for a role?_
  - term 'relocation': ✓ absent

**Q052** [insufficient] — PASS ✅ — _Are childcare vouchers or an on-site nursery available?_
  - term 'childcare': ✓ absent
  - term 'nursery': ✓ absent

**Q053** [insufficient] — PASS ✅ — _How do I receive equity or share options?_
  - term 'share option': ✓ absent
  - term 'equity': ✓ absent

**Q054** [insufficient] — PASS ✅ — _What are the eligibility rules for a company car?_
  - term 'company car': ✓ absent

**Q055** [insufficient] — PASS ✅ — _Will I be paid while on jury service?_
  - term 'jury': ✓ absent

**Q056** [insufficient] — PASS ✅ — _What is the CEO's total annual salary?_
  - term 'ceo': ✓ absent

**Q057** [insufficient] — PASS ✅ — _Does the company pay for a gym membership?_
  - term 'gym': ✓ absent

**Q058** [insufficient] — PASS ✅ — _Is dental insurance included in benefits?_
  - term 'dental': ✓ absent


## aggregation / list-all

**Q059** [answer] — PASS ✅ — _List all the types of leave available to employees._
  - `Leave_and_Time_Off_Policy.docx`: ✓ "3 Adoption and Shared Parental Leave Adoption leave mirrors the enhanced maternity provisions."

**Q060** [answer] — PASS ✅ — _What are the data classification levels used by the company?_
  - `IT_and_Acceptable_Use_Policy.docx`: ✓ "The company uses four classification levels: Public, Internal, Confidential and Restricted."

**Q061** [answer] — PASS ✅ — _What core benefits does the company offer?_
  - `Compensation_and_Benefits_Policy.docx`: ✓ "The company provides private medical insurance for all employees after successful completion of probation."

**Q062** [answer] — PASS ✅ — _List the stages of the disciplinary procedure._
  - `Code_of_Conduct_and_Disciplinary_Policy.docx`: ✓ "The disciplinary procedure follows progressive stages: an informal discussion where appropriate, followed by a formal first written warning, a final written warning, and dismissal."

**Q063** [answer] — PASS ✅ — _How does annual leave increase with length of service?_
  - `Leave_and_Time_Off_Policy.docx`: ✓ "Employees receive 27 days per year after completing 5 years of continuous service, and 30 days per year after completing 10 years of continuous service."
  - `Leave_and_Time_Off_Policy.docx`: ✓ "Employees receive 27 days per year after completing 5 years of continuous service, and 30 days per year after completing 10 years of continuous service."

**Q064** [answer] — PASS ✅ — _What personal protective equipment is required for field work?_
  - `Health_and_Safety_Policy.docx`: ✓ "Field engineers and site visitors must wear the personal protective equipment specified in the relevant site risk assessment, which as a minimum includes a hard hat, safety boots and a high-visibility vest when on operational sites."

**Q065** [answer] — PASS ✅ — _What pre-employment checks are carried out before a new hire starts?_
  - `Recruitment_and_Onboarding_Policy.docx`: ✓ "Right-to-work checks must be completed and documented before an individual starts employment, in line with UK immigration law."

**Q066** [answer] — PASS ✅ — _What are the expense approval thresholds and accommodation caps?_
  - `Travel_and_Expense_Policy.docx`: ✓ "Individual claims up to GBP 500 are approved by the line manager; claims above GBP 500 require additional approval from the department head."
  - `Travel_and_Expense_Policy.docx`: ✓ "Where an overnight stay is required, the maximum room rate the company will reimburse is GBP 180 per night in London and GBP 120 per night elsewhere in the United Kingdom."


## scenario / applied

**Q067** [answer] — PASS ✅ — _I have completed 6 years of service. How many annual leave days am I entitled to?_
  - `Leave_and_Time_Off_Policy.docx`: ✓ "Employees receive 27 days per year after completing 5 years of continuous service, and 30 days per year after completing 10 years of continuous service."

**Q068** [answer] — PASS ✅ — _I drove 12,000 business miles this year in my own car. How is that reimbursed?_
  - `Travel_and_Expense_Policy.docx`: ✓ "Where employees use their own vehicle for business travel, mileage is reimbursed at 45 pence per mile for the first 10,000 business miles in the tax year, and 25 pence per mile for any additional business miles."

**Q069** [answer] — PASS ✅ — _I have 3 years' service and want a sabbatical. Am I eligible?_
  - `Leave_and_Time_Off_Policy.docx`: ✓ "Employees with at least 5 years of continuous service may apply for an unpaid sabbatical of between 1 and 6 months."

**Q070** [answer] — PASS ✅ — _A supplier offered me a gift worth GBP 70. What should I do?_
  - `Code_of_Conduct_and_Disciplinary_Policy.docx`: ✓ "Any gift or hospitality with a value over GBP 50 must be declined or, where declining would cause offence, declared in the gifts and hospitality register and referred to a manager."

**Q071** [answer] — PASS ✅ — _I have been off sick long-term after 2 years' service. What sick pay do I get?_
  - `Leave_and_Time_Off_Policy.docx`: ✓ "After completing 1 year of continuous service, employees are entitled to company sick pay of 3 months at full pay followed by 3 months at half pay in any rolling 12-month period."

**Q072** [answer] — PASS ✅ — _As a new starter, when will my first formal performance review be?_
  - `Performance_Management_Policy.docx`: ✓ "Formal performance reviews are conducted twice per year: a mid-year review in July and a year-end review in January."

**Q073** [answer] — PASS ✅ — _I want to claim an expense from 45 days ago. Will it be paid?_
  - `Travel_and_Expense_Policy.docx`: ✓ "Claims submitted after 30 days may be refused."

**Q074** [answer] — PASS ✅ — _I am booking a hotel in London for a business trip. What is the nightly limit?_
  - `Travel_and_Expense_Policy.docx`: ✓ "Where an overnight stay is required, the maximum room rate the company will reimburse is GBP 180 per night in London and GBP 120 per night elsewhere in the United Kingdom."

**Q075** [conflict] — PASS ✅ — _I am a new employee. How long is my probationary period?_
  - `Employee_Handbook.docx`: ✓ "The probationary period for all new employees is 3 months from the start date."
  - `Recruitment_and_Onboarding_Policy.docx`: ✓ "The probationary period for all new employees is 6 months from the start date."

**Q076** [conflict] — PASS ✅ — _I would like to work from home. How many days a week can I do that?_
  - `Flexible_and_Remote_Work_Policy.docx`: ✓ "Eligible employees may work remotely for up to 3 days per week, with the remaining days worked from their assigned office."
  - `Remote_Working_Policy_2023_Superseded.docx`: ✓ "Eligible employees may work remotely for up to 2 days per week, with the remaining days worked from their assigned office."

**Q077** [insufficient] — PASS ✅ — _I am relocating cities for this role. What relocation support can I claim?_
  - term 'relocation': ✓ absent

**Q078** [insufficient] — PASS ✅ — _Can I bring my pet to work on Fridays?_
  - term 'dog': ✓ absent
  - term 'pet': ✓ absent
  - term 'pets': ✓ absent
