For implementation 

2. 90th percentile for drive_thru

3. prioty queue for drive through and mobile

3. Need to record customer queue time, currently I am recording customer system time. Brew time.

4. Need add a warm up period before recording.

5. play around with config..
    • Staff allocation per shift (e.g., number of cashiers, cooks, baristas, and bussers)
    • Beverage policy (e.g., urn size and brew schedule)
    • Prioritization at the pack station (e.g., whether mobile or drive-thru orders get precedence)
    • Pickup shelf capacity
    • Number of toasters or espresso machines

6. Dynamic labour cost? (low prio)

10. readme update

Bug free:

Possible simulation bugs, suggested by results such as:
1. different methods producing nearly identical performance when they clearly should differ;
2. performance remaining unchanged under significantly different parameter settings;
3. unusually large confidence intervals;
4. results that are difficult to interpret or show no clear performance trends.

- for report 

1. CRN method comparing scenarios

2. Calcualte confidence intervals in the performance evaluation 

3. explain the main flow 

4. following the “Guideline for Writing Report,”

5. Writing issue - unpolished chatgpt in writing. grammatical errors...


Jin's Modification: 12/6/2025
- Order Quantity System
    Changed needs_coffee, needs_espresso, needs_hot_food from bool to int (0-5)
    Added weighted random selection for quantities (1-2 more likely than 3-5)
    Added order_quantities and quantity_weights to SimulationConfig
- Financial Calculations
    Added item costs: cost_coffee, cost_espresso, cost_hot_food
    Replaced fixed avg_revenue with per-order calculations
    Added calculate_order_price() (selling price)
    Added calculate_order_cost() (material cost)
    Updated calculate_order_revenue() to use (price - cost)
- Fixed duplicate renege recording (added check for has_reneged)
- Fixed duplicate waste recording in packing and pickup
- Add debug function 
- Dining area implementation: 
    if walkin customer has no table, current logic is leaving restaurant without any penalty,
    but record the no seating count. 