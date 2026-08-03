# Ground Truth — Meridian Grid Technologies HR Corpus

**Company:** Meridian Grid Technologies Ltd (MGT) — Renewable-energy & smart-grid engineering, ~1400 employees, founded 2009, HQ Manchester, UK.  
**Sites:** Manchester (HQ), Bristol, Glasgow, Leeds, UK-wide field teams.  
*Fictional. All figures UK conventions (statutory leave, SSP, HMRC mileage, auto-enrolment).*

This is the authored answer key. Every query in `queries.json` traces to a fact, conflict, or gap below. Section names are the **authored** headings; note that the pipeline's chunk-level section tag may show an adjacent heading because 500-char chunks can span a section boundary. `expected_sources` (filenames) are exact.

## Documents

| Doc ID | File | Title | Ver |
|---|---|---|---|
| MGT-HR-001 | `Employee_Handbook.docx` | Employee Handbook | 2025.2 |
| MGT-HR-002 | `Leave_and_Time_Off_Policy.docx` | Leave & Time-Off Policy | 4.1 |
| MGT-HR-003 | `Flexible_and_Remote_Work_Policy.docx` | Flexible & Remote Work Policy (2025, current) | 3.0 |
| MGT-HR-003a | `Remote_Working_Policy_2023_Superseded.docx` | Remote Working Policy (2023, superseded) | 1.2 |
| MGT-HR-004 | `Compensation_and_Benefits_Policy.docx` | Compensation & Benefits Policy | 2.3 |
| MGT-HR-005 | `Performance_Management_Policy.docx` | Performance Management Policy | 2.0 |
| MGT-HR-006 | `Recruitment_and_Onboarding_Policy.docx` | Recruitment & Onboarding Policy | 1.4 |
| MGT-HR-007 | `IT_and_Acceptable_Use_Policy.docx` | IT & Acceptable Use Policy | 3.1 |
| MGT-HR-008 | `Travel_and_Expense_Policy.docx` | Travel & Expense Policy | 2.1 |
| MGT-HR-009 | `Code_of_Conduct_and_Disciplinary_Policy.docx` | Code of Conduct & Disciplinary Policy | 2.2 |
| MGT-HR-010 | `Health_and_Safety_Policy.docx` | Health & Safety Policy | 1.3 |

## Facts (single-source & agreeing)

| ID | Topic | Value | Type | Source doc(s) → section |
|---|---|---|---|---|
| working_week | Standard full-time working week | 37.5 hours/week (Mon-Fri) | agreeing | `Employee_Handbook.docx` → 2. Working Hours; `Flexible_and_Remote_Work_Policy.docx` → 4. Core Hours and Flexible Time |
| core_hours | Core hours | 10:00 to 16:00 | single | `Flexible_and_Remote_Work_Policy.docx` → 4. Core Hours and Flexible Time |
| annual_leave_base | Base annual leave entitlement | 25 days/year (+8 bank holidays) | single | `Leave_and_Time_Off_Policy.docx` → 2.1 Entitlement |
| annual_leave_5yr | Annual leave after 5 years' service | 27 days/year | single | `Leave_and_Time_Off_Policy.docx` → 2.1 Entitlement |
| annual_leave_10yr | Annual leave after 10 years' service | 30 days/year | single | `Leave_and_Time_Off_Policy.docx` → 2.1 Entitlement |
| carryover_cap | Annual leave carry-over cap | 5 days (use by 31 March) | single | `Leave_and_Time_Off_Policy.docx` → 2.2 Carry-Over |
| sick_pay | Company sick pay (after 1 year service) | 3 months full pay + 3 months half pay (rolling 12 months) | single | `Leave_and_Time_Off_Policy.docx` → 3. Sickness Absence and Sick Pay |
| maternity | Enhanced maternity pay | 16 weeks full pay (then 23 wks SMP, 13 wks unpaid; up to 52 wks total) | single | `Leave_and_Time_Off_Policy.docx` → 4.1 Maternity Leave |
| paternity | Enhanced paternity leave | 4 weeks full pay | single | `Leave_and_Time_Off_Policy.docx` → 4.2 Paternity Leave |
| compassionate | Compassionate/bereavement leave | up to 5 days paid | single | `Leave_and_Time_Off_Policy.docx` → 5.1 Compassionate and Bereavement Leave |
| sabbatical | Sabbatical eligibility | after 5 years' service; 1-6 months unpaid | single | `Leave_and_Time_Off_Policy.docx` → 5.2 Sabbatical Leave |
| pay_review | Salary review cadence | annual; increases effective 1 April | single | `Compensation_and_Benefits_Policy.docx` → 2. Salary and Pay Reviews |
| pension_employee | Employee minimum pension contribution | 4% of pensionable salary | single | `Compensation_and_Benefits_Policy.docx` → 3. Workplace Pension |
| bonus | Discretionary annual bonus | up to 10% of base salary | single | `Compensation_and_Benefits_Policy.docx` → 4. Annual Bonus |
| life_assurance | Life assurance | 4x base salary | single | `Compensation_and_Benefits_Policy.docx` → 5. Core Benefits |
| ev_scheme | Electric-vehicle salary-sacrifice scheme (personal cars) | available | single | `Compensation_and_Benefits_Policy.docx` → 5. Core Benefits |
| notice_standard | Notice period after probation (standard) | 1 month written notice | agreeing | `Compensation_and_Benefits_Policy.docx` → 6. Notice Periods; `Code_of_Conduct_and_Disciplinary_Policy.docx` → 7. Notice Periods |
| notice_senior | Notice period after probation (senior manager+) | 3 months written notice | agreeing | `Compensation_and_Benefits_Policy.docx` → 6. Notice Periods; `Code_of_Conduct_and_Disciplinary_Policy.docx` → 7. Notice Periods |
| referral_bonus | Employee referral bonus | GBP 1,500 (on referred hire passing probation) | single | `Recruitment_and_Onboarding_Policy.docx` → 4. Employee Referral Scheme |
| probation_notice | Notice period during probation | 1 week (either party) | single | `Recruitment_and_Onboarding_Policy.docx` → 5. Probationary Period |
| onboarding | Onboarding plan | structured 90-day plan; 30/60/90-day check-ins | single | `Recruitment_and_Onboarding_Policy.docx` → 6. Onboarding |
| right_to_work | Right-to-work checks | completed before start; 3 years of references | single | `Recruitment_and_Onboarding_Policy.docx` → 3. Right to Work and Pre-Employment Checks |
| password_length | Minimum password length | 14 characters | single | `IT_and_Acceptable_Use_Policy.docx` → 2. Accounts, Passwords and Authentication |
| mfa | Multi-factor authentication | mandatory for remote access + cloud apps | single | `IT_and_Acceptable_Use_Policy.docx` → 2. Accounts, Passwords and Authentication |
| data_classes | Data classification levels | Public, Internal, Confidential, Restricted | single | `IT_and_Acceptable_Use_Policy.docx` → 3. Data Classification |
| incident_report | Security incident reporting deadline | within 1 hour of discovery | single | `IT_and_Acceptable_Use_Policy.docx` → 7. Incident Reporting |
| mileage | Business mileage reimbursement | 45p/mile first 10,000 miles; 25p/mile thereafter | single | `Travel_and_Expense_Policy.docx` → 2. Mileage and Private Vehicle Use |
| hotel_caps | Hotel room caps | GBP 180/night London; GBP 120/night elsewhere UK | single | `Travel_and_Expense_Policy.docx` → 4. Accommodation |
| subsistence | Subsistence meal caps | GBP 10 breakfast; GBP 30 evening meal | single | `Travel_and_Expense_Policy.docx` → 5. Subsistence |
| expense_deadline | Expense claim submission deadline | within 30 days of cost | single | `Travel_and_Expense_Policy.docx` → 6. Approval and Submission |
| expense_approval | Expense approval thresholds | <= GBP 500 line manager; > GBP 500 department head | single | `Travel_and_Expense_Policy.docx` → 6. Approval and Submission |
| gift_threshold | Gift/hospitality declaration threshold | over GBP 50 must be declined/declared | single | `Code_of_Conduct_and_Disciplinary_Policy.docx` → 3. Gifts and Hospitality |
| disciplinary | Disciplinary stages | informal -> first written (6mo) -> final written (12mo) -> dismissal | single | `Code_of_Conduct_and_Disciplinary_Policy.docx` → 6. Disciplinary Procedure |
| grievance | Grievance procedure | informal first; formal meeting normally within 10 working days; right to appeal | single | `Code_of_Conduct_and_Disciplinary_Policy.docx` → 8. Grievance Procedure |
| whistleblowing | Whistleblowing | confidential channel; protection from detriment | single | `Code_of_Conduct_and_Disciplinary_Policy.docx` → 9. Whistleblowing |
| review_cycle | Performance review cycle | twice per year (mid-year July, year-end January) | single | `Performance_Management_Policy.docx` → 2. Performance Review Cycle |
| rating_scale | Performance rating scale | 1 to 5 (3 = fully meets) | single | `Performance_Management_Policy.docx` → 3. Objectives and Ratings |
| promotion | Promotion cycle | annual (year-end review), effective 1 April; rating 4+ required | single | `Performance_Management_Policy.docx` → 4. Promotion |
| pip | Performance Improvement Plan duration | normally 8 to 12 weeks | single | `Performance_Management_Policy.docx` → 5. Managing Underperformance |
| first_aider_ratio | First-aider ratio | at least 1 per 50 employees on site | single | `Health_and_Safety_Policy.docx` → 4. First Aid |
| fire_drills | Fire evacuation drills | quarterly at each office | single | `Health_and_Safety_Policy.docx` → 5. Fire Safety |
| dse | Display screen equipment assessment | self-assessment on appointment + on change (incl. home) | single | `Health_and_Safety_Policy.docx` → 3. Display Screen Equipment |
| ppe | PPE for field work | min hard hat, safety boots, hi-vis vest on operational sites | single | `Health_and_Safety_Policy.docx` → 6. Personal Protective Equipment and Field Work |
| lone_working | Lone working | check-in schedule + alarm; risk assessment for high-risk | single | `Health_and_Safety_Policy.docx` → 7. Lone Working |
| riddor | Accident reporting | reportable injuries notified to HSE under RIDDOR | single | `Health_and_Safety_Policy.docx` → 8. Accident and Incident Reporting |

## Planted Conflicts (Conflict queries)

### C1 — Length of the probationary period
- **Detector:** numeric + NLI
- **Realism:** Cross-document drift: handbook summary vs authoritative recruitment policy
- `Employee_Handbook.docx` (§ 3. Probationary Period): **3 months**
- `Recruitment_and_Onboarding_Policy.docx` (§ 5. Probationary Period): **6 months**

### C2 — Maximum remote-working days per week
- **Detector:** NLI (spans diluted below numeric sim gate)
- **Realism:** Versioned: superseded 2023 policy still in the corpus alongside current 2025 policy
- `Flexible_and_Remote_Work_Policy.docx` (§ 3. Hybrid Working Arrangements): **3 days/week (2025, current)**
- `Remote_Working_Policy_2023_Superseded.docx` (§ 3. Remote Working Days): **2 days/week (2023, superseded)**

### C3 — Employer pension contribution rate
- **Detector:** numeric + NLI
- **Realism:** Handbook benefits summary is stale vs authoritative reward policy
- `Compensation_and_Benefits_Policy.docx` (§ 3. Workplace Pension): **6% (authoritative)**
- `Employee_Handbook.docx` (§ 4. Pay and Benefits Summary): **5% (out-of-date summary)**

### C4 — Use of personal mobile devices to access corporate email
- **Detector:** NLI (keyword prong diluted below sim gate)
- **Realism:** Two owning teams (InfoSec vs Employee Relations) disagree
- `IT_and_Acceptable_Use_Policy.docx` (§ 4. Personal Devices and Bring Your Own Device): **permitted (for MDM-enrolled devices)**
- `Code_of_Conduct_and_Disciplinary_Policy.docx` (§ 5. Use of Personal Devices): **prohibited at all times**

## Deliberate Gaps (Insufficient queries)

| ID | Topic | Note |
|---|---|---|
| G1 | Company car scheme / company vehicle eligibility | No document offers a company car. Note: an EV salary-sacrifice scheme for PERSONAL cars exists (Comp & Benefits 5) — a 'company car' query is still a genuine gap, but avoid the word 'electric-vehicle scheme'. |
| G2 | Share options / ESPP / equity / stock | MGT is private; no share scheme is mentioned in any policy. |
| G3 | Relocation allowance / relocation support | No relocation package is described anywhere in the corpus. |
| G4 | On-site childcare / nursery / childcare vouchers | No childcare benefit is mentioned in any policy. |
| G5 | Jury service pay | Public-duties leave (magistrate, school governor) is unpaid and jury service is never mentioned; whether jury service is paid is not covered. |
| G6 | Pet-friendly office / bringing pets to work | No policy addresses pets or animals in the workplace. |
