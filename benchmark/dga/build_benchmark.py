"""Build benchmark/dga/questions.jsonl + evidence crops from the ORIGINAL PDF.

Gold answers were written by reading the original pages (page renders + text layer + vector
data for axis readings). This script only serialises them, resolves printed page numbers,
resolves bbox regions from anchor strings on the page, and renders the crops.
It never reads any pipeline output.

Run:  "/Volumes/T7 Dev/AI20K/day6/venv/bin/python" -W ignore benchmark/dga/build_benchmark.py
"""
import json
import os
import re

import fitz

HERE = os.path.dirname(os.path.abspath(__file__))
PDF = "/Volumes/T7 Dev/AI20K/day7/dga/raw/dga_2020_2025.pdf"
CROPS = os.path.join(HERE, "crops")
OUT = os.path.join(HERE, "questions.jsonl")

doc = fitz.open(PDF)


def printed_page(pno):
    t = doc[pno - 1].get_text()
    m = re.search(r"Page (\d{1,3})\b", t)
    return int(m.group(1)) if m else None


def region(pno, top, bottom, x0=40, x1=572, pad=4, last_bottom=False, top_pad=None, bot_pad=12):
    """bbox from the first hit of `top` to the first (or last) hit of `bottom`."""
    pg = doc[pno - 1]
    a = pg.search_for(top)
    b = pg.search_for(bottom)
    assert a, (pno, top)
    assert b, (pno, bottom)
    ytop = min(r.y0 for r in a)
    below = [r for r in b if r.y0 >= ytop]
    assert below, (pno, bottom)
    ybot = max(r.y1 for r in below) if last_bottom else min(r.y1 for r in below)
    return [x0, round(ytop - (pad if top_pad is None else top_pad), 1), x1, round(ybot + bot_pad, 1)]


def T(pno, quote):
    return {"pdf_page": pno, "kind": "text", "ref": f"PDF p.{pno} body text", "quote": quote,
            "bbox": None, "crop": None, "reading": None}


def F(pno, kind, ref, bbox, quote=None, reading=None):
    return {"pdf_page": pno, "kind": kind, "ref": ref, "quote": quote, "bbox": bbox,
            "crop": None, "reading": reading}


Q = []


def add(id_, split, group, tags, question, evidence, rationale, answer=None, absence=None, near=None):
    q = {"id": id_, "split": split, "group": group, "tags": tags, "question": question}
    if group == "none":
        q.update({"expected_behavior": "abstain", "answerable": False, "evidence": [],
                  "absence_check": absence, "near_topic": near})
    else:
        q.update({"expected_answer": answer, "answerable": True, "evidence": evidence})
    q["rationale"] = rationale
    Q.append(q)


# ---------------------------------------------------------------- fixed bboxes (PDF points)
BB = {
    "fig1_1": [48, 53, 581, 706],
    "fig1_2": [48, 53, 562, 497],
    "fig1_6": [40, 290, 572, 745],
    "fig1_7": [48, 322, 528, 708],
    "fig1_8_table": [48, 401, 562, 636],
    "fig1_10": [48, 53, 612, 710],
    "fig1_12": [48, 53, 612, 712],
    "fig2_1": [48, 470, 562, 680],
    "fig2_2_chart": [48, 182, 394, 552],
    "fig2_2_box": [48, 571, 562, 672],
    "fig3_2_donuts": [48, 463, 562, 656],
    "fig5_1_hei": [398, 197, 562, 509],
    "tab5_2": [48, 53, 562, 338],
    "tab5_3": [302, 360, 562, 622],
    "tabA2_2": [48, 53, 562, 696],
}

# ================================================================ TEST (30)
# ---- table (6)
add("t01", "test", "table", ["appendix", "lookup", "weekly-amounts"],
    "For a client on an 1,800-calorie Healthy U.S.-Style eating pattern (age 2+), how many cup-equivalents per week of red & orange vegetables and of dark-green vegetables does the pattern call for?",
    [F(157, "table", "Table A3-2, rows 'Red and Orange Vegetables (cup eq/wk)' and 'Dark-Green Vegetables (cup eq/wk)', column '1,800'",
       region(157, "Table A3-2", "Red and Orange Vegetables"), quote="Healthy U.S.-Style Dietary Pattern for Ages 2 and Older")],
    "Requires locating the right appendix table, the 1,800 column and two weekly-unit subgroup rows (not the daily total).",
    answer="Red & orange vegetables: 5½ cup eq per week; dark-green vegetables: 1½ cup eq per week (Table A3-2, 1,800-calorie column; subgroup amounts are weekly).")

add("t02", "test", "table", ["appendix", "compute", "sex-comparison"],
    "A moderately active 16-year-old boy and a moderately active 16-year-old girl: what are their estimated daily calorie needs, and how big is the gap?",
    [F(153, "table", "Table A2-2, row '16', columns Males 'Moderately Active' and Females 'Moderately Active'", BB["tabA2_2"],
       quote="Estimated Calorie Needs per Day, by Age, Sex, and Physical Activity Level")],
    "Two-cell lookup in a dense 26x6 grid plus subtraction.",
    answer="Boy: 2,800 calories/day; girl: 2,000 calories/day; difference = 2,800 - 2,000 = 800 calories/day (Table A2-2, age 16, moderately active).")

add("t03", "test", "table", ["pregnancy", "lactation", "footnote", "calculation"],
    "How many extra calories per day does a breastfeeding woman with a healthy pre-pregnancy weight need in the first 6 months postpartum, and how is that figure derived?",
    [F(125, "table", "Table 5-2, row 'Lactation: 1st 6 months' + footnote b", BB["tab5_2"],
       quote="subtracting 170 calories/day to account for weight loss in the first 6 months postpartum")],
    "Needs the table cell and its footnote to explain the derivation (condition: healthy pre-pregnancy weight).",
    answer="+330 calories/day vs pre-pregnancy needs (applies to women with a healthy pre-pregnancy weight). Derivation (footnote b): +500 calories/day for milk production minus 170 calories/day for weight loss in the first 6 months postpartum = 330.")

add("t04", "test", "table", ["older-adults", "lookup"],
    "In the eating pattern for adults 60 and older at 2,000 calories, how many calories per day are left for 'other uses' and what share of the total is that? How much protein foods is recommended at that level?",
    [F(138, "table", "Table 6-1, rows 'Limit on Calories for Other Uses (kcal/day)', '(%/day)', 'Protein Foods (ounce eq/day)', column '2,000'",
       region(138, "Table 6-1", "Limit on Calories for Other Uses (%/day)"), quote="Healthy U.S.-Style Dietary Pattern for Adults Ages 60 and Older")],
    "Three cells in the same column of a chapter table that differs subtly from Appendix A3-2.",
    answer="240 kcal/day for other uses, which is 12% of calories; protein foods 5½ ounce-eq per day (Table 6-1, 2,000-calorie column).")

add("t05", "test", "table", ["pregnancy", "weight-gain", "conditional"],
    "A woman whose pre-pregnancy BMI is 27 asks how much weight she should gain in total during pregnancy and per week in the 2nd and 3rd trimesters. What does the guidance table say?",
    [F(125, "table", "Table 5-3, row 'Overweight' (BMI 25-29.9)", BB["tab5_3"], quote="Weight Gain Recommendations for Pregnancy")],
    "Requires mapping BMI 27 to the 'Overweight' row (25-29.9) before reading two columns with units.",
    answer="BMI 27 falls in the Overweight category (BMI 25-29.9): total gain 15-25 lb; weekly gain in the 2nd and 3rd trimesters 0.6 lb on average (range 0.5-0.7 lb/week). (Calculations assume 1.1-4.4 lb gained in the first trimester.)")

add("t06", "test", "table", ["toddlers", "appendix", "lookup"],
    "For a toddler (12-23 months) who no longer drinks breast milk or formula, eating on the 1,000-calorie pattern, how much dairy, fruit and grains are recommended per day?",
    [F(156, "table", "Table A3-1, rows 'Dairy (cup eq/day)', 'Fruits (cup eq/day)', 'Grains (ounce eq/day)', column '1,000'",
       region(156, "Table A3-1", "Dairy (cup eq/day)"), quote="Who Are No Longer Receiving Human Milk or Infant Formula")],
    "Toddler table is a distinct appendix table with fractional cells; three rows, one column, mixed units.",
    answer="Dairy 2 cup eq/day, fruits 1 cup eq/day, grains 3 ounce eq/day (Table A3-1, 1,000-calorie column).")

# ---- image / diagram (5)
add("t07", "test", "image", ["nutrient-dense", "swap", "photo-panel"],
    "In the guidelines' side-by-side photo panel of 'typical' versus nutrient-dense single choices, what is shown as the better choice instead of butter, and instead of soda?",
    [F(35, "figure", "Figure 1-2 (Making Nutrient-Dense Choices: One Food or Beverage At a Time), columns 4 and 5", BB["fig1_2"], quote="Vegetable Oil Sparkling Water")],
    "Pairings are only expressed by the column layout of the infographic (top = nutrient-dense, bottom = typical).",
    answer="Butter -> vegetable oil; soda -> sparkling water (Figure 1-2: the top 'Nutrient-dense' row pairs with the bottom 'Typical' row in each column).")

add("t08", "test", "image", ["life-stage", "diagram", "health-outcomes"],
    "According to the diagram summarising the science on healthy eating across the lifespan, what benefits are listed for women who are pregnant or lactating?",
    [F(37, "figure", "Figure 1-3, panel 'Women Who Are Pregnant or Lactating'", region(37, "Figure 1-3", "Favorable bone health"),
       quote="Favorable cognitive development in the child")],
    "Diagram with one panel per life stage; must pick the correct panel.",
    answer="Two benefits: favorable cognitive development in the child, and favorable folate status in women during pregnancy and lactation (Figure 1-3).")

add("t09", "test", "image", ["85-15", "diagram", "calories"],
    "In the 85-15 guide graphic, what share of daily calories is needed to meet food group needs in nutrient-dense forms, and what is the remaining share available for?",
    [F(50, "figure", "Figure 1-7 (The 85-15 Guide)", BB["fig1_7"], quote="85% of calories are needed per day to meet food group recommendations healthfully, in nutrient-dense forms"),
     T(50, "This equates to 250 to 350 remaining calories for calorie patterns appropriate for most Americans")],
    "Ring diagram; 15% label sits outside the ring with its explanation.",
    answer="About 85% of daily calories are needed to meet food group recommendations in nutrient-dense forms; the remaining ~15% is available for other uses, including added sugars and saturated fat (the text adds: eating more than the recommended amount of a food group, or alcohol), about 250-350 calories for most Americans' calorie patterns.")

add("t10", "test", "image", ["sample-day", "menu", "multi-page", "sum"],
    "The guidelines show a sample day of nutrient-dense meals that comes in under 2,000 calories. What are the calorie totals for breakfast, lunch, dinner and snacks, and what does the whole day add up to?",
    [F(52, "figure", "Figure 1-9 (Making Healthy Choices: One Day At a Time), Breakfast and Lunch panels", region(52, "Figure 1-9", "Iced Tea, No Sugar"), quote="BREAKFAST Total calories: 375"),
     F(53, "figure", "Figure 1-9 (continued), Dinner and Snacks panels", region(53, "DINNER", "Yogurt and Peaches"), quote="SNACKS Total calories: 300")],
    "Menu infographic split over two pages; the day total is not printed and must be summed.",
    answer="Breakfast 375, lunch 715, dinner 585, snacks 300 calories; day total = 375 + 715 + 585 + 300 = 1,975 calories (under 2,000).")

add("t11", "test", "image", ["toddlers", "swap", "photo-panel"],
    "For toddlers, which healthier swaps does the guidelines' photo panel suggest for fried vegetables and for high-sodium meats?",
    [F(76, "figure", "Figure 2-1 (Make Healthy Shifts To Empower Toddlers ...), arrows 'Fried Vegetables -> Roasted Vegetables' and 'High-sodium Meats -> Ground Lean Meats'", BB["fig2_1"],
       quote="Make Healthy Shifts To Empower Toddlers To Eat Nutrient-Dense Foods in Dietary Patterns")],
    "Pairs are encoded by arrows between photos; text layer order scrambles the pairs.",
    answer="Fried vegetables -> roasted vegetables; high-sodium meats -> ground lean meats (Figure 2-1).")

# ---- chart (5)
add("t12", "test", "chart", ["stacked-bar", "calories", "compute"],
    "For 2 cups of movie-theater-style popcorn with butter, how many calories come from the popcorn itself versus the added butter, and what percentage of the total is the butter?",
    [F(34, "figure", "Figure 1-1, bar 'Movie Theater-Style Popcorn With Butter, 2 cups'", BB["fig1_1"],
       quote="Air-Popped Popcorn Butter 62 122 184 Total",
       reading="Stacked horizontal bar, x-axis CALORIES 0-300; legend: dark blue = calories in nutrient-dense form, orange = additional calories as consumed. Segment values are printed labels: 62 (blue, air-popped popcorn) + 122 (orange, butter) = 184 total.")],
    "Must map legend colours to segments and compute a share.",
    answer="Air-popped popcorn 62 calories + butter 122 calories = 184 calories total; butter = 122/184 ≈ 66% of the calories.")

add("t13", "test", "chart", ["bubble-chart", "added-sugars", "sources"],
    "What is the single largest food-category source of added sugars for Americans aged 1+, what share does it contribute, and which item within it is the biggest contributor?",
    [F(56, "figure", "Figure 1-10, largest bubble 'Sugar-Sweetened Beverages' and inset 'Within Sugar-Sweetened Beverages'", BB["fig1_10"],
       quote="Soft Drinks 16%",
       reading="Bubble chart of % of added-sugars intake; percentages are printed labels. Largest bubble: Sugar-Sweetened Beverages 24%; inset breaks it into Soft Drinks 16%, Fruit Drinks 5%, Sport & Energy Drinks 2%, Other 1%.")],
    "Needs reading both the main bubbles and the inset breakdown.",
    answer="Sugar-sweetened beverages, 24% of added sugars intake; within them soft drinks are largest at 16% (fruit drinks 5%, sport & energy drinks 2%, other 1%).")

add("t14", "test", "chart", ["donut", "children", "sex-comparison"],
    "Among girls aged 2-4, which of added sugars, saturated fat and sodium is exceeded by the largest share, and are boys of that age better or worse on it?",
    [F(90, "figure", "Figure 3-2, bottom panel 'Percent Exceeding Limits of Added Sugars, Saturated Fat, and Sodium'", BB["fig3_2_donuts"],
       quote="Males 61% Females 57%",
       reading="Three donut pairs (Males/Females) under headers Added Sugars, Saturated Fat, Sodium; orange = exceeding limit. Printed labels: Added sugars M 61% F 57%; Saturated fat M 87% F 88%; Sodium M 97% F 95%. The text layer lists the numbers without headers, so the mapping must be read from the image.")],
    "Requires attaching donut labels to the correct nutrient header and sex.",
    answer="Sodium: 95% of girls aged 2-4 exceed the limit (limit 1,200 mg for ages 2-3; 1,500 mg at age 4). Boys are slightly worse at 97%. (For comparison: saturated fat F 88% / M 87%, added sugars F 57% / M 61%.)")

add("t15", "test", "chart", ["HEI", "pregnancy", "compare-series"],
    "How do Healthy Eating Index scores compare among adult women in general, pregnant women and lactating women, and how many points higher is the pregnant group than adult women overall?",
    [F(126, "figure", "Figure 5-1, right panel 'Healthy Eating Index Score (on a scale of 0-100)'", BB["fig5_1_hei"],
       quote="62 63 54",
       reading="Three labelled bubbles over illustrations; labels assigned by position: Adult Women 54, Women Who Are Pregnant 63, Women Who Are Lactating 62 (text layer order 62 63 54 does not match, read from image).")],
    "Label-to-series assignment is only visual; then a difference.",
    answer="Adult women 54, pregnant women 63, lactating women 62 (HEI-2015, 0-100). Pregnant women score 63 - 54 = 9 points higher than adult women overall.")

add("t16", "test", "chart", ["range-plot", "toddlers", "axis-reading"],
    "For toddlers aged 12-23 months, in which food groups does the average intake sit above the top of the recommended intake range, and which group falls below its range?",
    [F(78, "figure", "Figure 2-2, top panel 'Average Daily Food Group Intakes Compared to Recommended Intake Ranges'", BB["fig2_2_chart"],
       quote="Average Daily Food Group Intakes Compared to Recommended Intake Ranges",
       reading="Y-axis 'CUP or OZ EQUIVALENT' 0-3.5; teal bars = recommended range, purple dot = average intake. Verified from vector data (page.get_drawings, gridline y0=492.3pt for 0, y=277.9pt for 3.5, 61.26pt per unit): Fruits dot ≈1.25 vs range top 1.0; Grains dot ≈3.08 vs top 3.0; Dairy dot ≈2.58 vs top 2.0; Vegetables dot ≈0.56 below range bottom (~0.65-0.75); Protein foods dot ≈1.94 on the ~2.0 recommendation (not above). Tolerance ±0.1."),
     T(79, "Total grains, particularly refined grains, are consumed in amounts that exceed recommendations")],
    "Values are not printed; must compare dot vs bar positions on the axis.",
    answer="Above the range: total fruits (~1.25 cup eq vs top ~1.0), total grains (~3.1 oz eq vs top 3.0) and total dairy (~2.6 cup eq vs top 2.0). Below the range: total vegetables (~0.55 cup eq/day). Protein foods sit at about the recommended ~2 oz eq (not above).")

# ---- multi-hop (4)
add("t17", "test", "multihop", ["mediterranean", "seafood", "cross-table", "compute"],
    "At 2,400 calories a day, how much more seafood per week does the Healthy Mediterranean-Style pattern call for than the Healthy U.S.-Style pattern?",
    [F(162, "table", "Table A3-5 (Mediterranean), row 'Seafood (ounce eq/wk)', column '2,400'", region(162, "Table A3-5", "Seafood (ounce eq/wk)"), quote="Healthy Mediterranean-Style Dietary Pattern for Ages 2 and Older"),
     F(157, "table", "Table A3-2 (U.S.-Style), row 'Seafood (ounce eq/wk)', column '2,400'", region(157, "Table A3-2", "Seafood (ounce eq/wk)"), quote="Healthy U.S.-Style Dietary Pattern for Ages 2 and Older")],
    "Same row in two tables five pages apart; subtraction.",
    answer="Mediterranean: 16 ounce-eq/week; U.S.-Style: 10 ounce-eq/week; difference = 16 - 10 = 6 ounce-eq more seafood per week (2,400-calorie column of both tables).")

add("t18", "test", "multihop", ["calorie-needs", "pattern", "chain"],
    "A moderately active 28-year-old woman wants to follow the Healthy U.S.-Style pattern at her estimated calorie needs. How many cup-equivalents of vegetables and fruits should she aim for daily?",
    [F(153, "table", "Table A2-2, row '26-30', Females 'Moderately Active'", BB["tabA2_2"], quote="Estimated Calorie Needs per Day, by Age, Sex, and Physical Activity Level"),
     F(157, "table", "Table A3-2, rows 'Vegetables (cup eq/day)' and 'Fruits (cup eq/day)', column '2,000'", region(157, "Table A3-2", "Fruits (cup eq/day)"), quote="Healthy U.S.-Style Dietary Pattern for Ages 2 and Older")],
    "Chain: calorie need from Appendix 2, then pattern amounts from Appendix 3.",
    answer="Estimated needs: 2,000 calories/day (female, 26-30, moderately active). At 2,000 calories: vegetables 2½ cup-eq/day and fruits 2 cup-eq/day.")

add("t19", "test", "multihop", ["HEI", "life-stage", "compare"],
    "How many points higher is the Healthy Eating Index score of adults 60 and older than that of adolescents aged 14-18?",
    [F(98, "figure", "Figure 3-8, 'Healthy Eating Index Score (on a scale of 0-100)' bubble", region(98, "Figure 3-8", "Data Sources"), quote="(on a scale of 0-100) 51",
       reading="HEI score printed in a bubble: 51 for ages 14 through 18."),
     T(140, "Healthy Eating Index score of 63 out of 100")],
    "Two life-stage chapters (Ch.3 figure and Ch.6 text).",
    answer="Adults 60+: 63; adolescents 14-18: 51; difference = 63 - 51 = 12 points.")

add("t20", "test", "multihop", ["pregnancy", "calorie-needs", "chain"],
    "A sedentary 28-year-old woman with a healthy pre-pregnancy weight is in her second trimester. Roughly how many calories per day does she need now?",
    [F(153, "table", "Table A2-2, row '26-30', Females 'Sedentary'", BB["tabA2_2"], quote="Estimated Calorie Needs per Day, by Age, Sex, and Physical Activity Level"),
     F(125, "table", "Table 5-2, row 'Pregnancy: 2nd trimester'", BB["tab5_2"], quote="Pregnancy: 2nd trimester + 340 calories")],
    "Baseline from Appendix 2 + increment from Chapter 5 table.",
    answer="Pre-pregnancy estimate 1,800 calories/day (female 26-30, sedentary) + 340 calories (2nd trimester) ≈ 2,140 calories/day (estimate for a healthy pre-pregnancy weight; individual needs should be checked with a healthcare provider).")

# ---- text (4)
add("t21", "test", "text", ["infants", "allergy", "conditional"],
    "When should peanut-containing foods be introduced for a baby who has severe eczema or an egg allergy, and what should caregivers do first?",
    [T(71, "If an infant has severe eczema, egg allergy, or both"),
     T(71, "should be introduced into the diet as early as age 4 to 6 months"),
     T(71, "Caregivers should check with the infant's healthcare provider before feeding the infant peanut")],
    "Conditional recommendation for a high-risk subgroup.",
    answer="For infants at high risk (severe eczema, egg allergy, or both), age-appropriate peanut-containing foods should be introduced as early as 4-6 months of age to reduce peanut-allergy risk; caregivers should first check with the infant's healthcare provider (a blood test or skin prick test may be recommended to decide whether/how to introduce peanut).")

add("t22", "test", "text", ["lactation", "caffeine", "conditional"],
    "Is coffee okay while breastfeeding? How much caffeine does the guidance consider low to moderate for a lactating mother?",
    [T(131, "about 300 milligrams or less per day, which is about 2 to 3 cups of coffee")],
    "Specific lactation number differs from the general adult figure elsewhere (400 mg).",
    answer="Caffeine passes into breast milk in small amounts but usually does not harm the infant at low-to-moderate intakes: about 300 mg or less per day (about 2-3 cups of coffee).")

add("t23", "test", "text", ["alcohol", "definition", "conditional"],
    "For adults of legal drinking age who choose to drink, what are the daily limits for men and women, is that an average over the week, and what counts as one drink?",
    [T(62, "2 drinks or less in a day for men and 1 drink or less in a day for women"),
     T(62, "This is not intended as an average over several days"),
     T(62, "One alcoholic drink equivalent is defined as containing 14 grams (0.6 fl oz) of pure alcohol")],
    "Synthesis of limit, condition (per day, not averaged) and definition.",
    answer="Men: 2 drinks or less in a day; women: 1 drink or less in a day, on days when alcohol is consumed - not an average over several days. One drink equivalent = 14 g (0.6 fl oz) pure alcohol, e.g. 12 fl oz regular beer (5%), 5 fl oz wine (12%), or 1.5 fl oz 80-proof spirits (40%). Choosing not to drink is also an option; drinking less is better than more.")

add("t24", "test", "text", ["lactation", "supplements", "upper-limit"],
    "A breastfeeding mother keeps taking her prenatal vitamins. Which nutrients could she overdo, and what are the upper limits?",
    [T(128, "Continued use of prenatal supplements by women who are lactating may exceed their needs for folic acid and iron"),
     T(128, "Women who are lactating should not exceed the Tolerable Upper Intake Level (UL) of 1,000 micrograms of folic acid and 45 milligrams of iron")],
    "Conditional (lactating + continued prenatal supplement) with two ULs and units.",
    answer="Folic acid and iron. Lactating women should not exceed the UL of 1,000 micrograms of folic acid and 45 milligrams of iron per day; they should seek guidance from a healthcare provider on supplement use.")

# ---- none (6)
NONE_T = [
    ("t25", "Does the guidance recommend intermittent fasting or time-restricted eating windows for weight management in adults?",
     [r"intermittent", r"time[- ]restricted", r"\bfasting\b", r"eating window"], r"weight management",
     "Adjacent to the weight-management and calorie-balance sections; a model may invent a stance."),
    ("t26", "What is the acceptable daily intake (mg per kg body weight) of aspartame or sucralose according to these guidelines?",
     [r"aspartame", r"sucralose", r"stevia", r"acceptable daily intake", r"mg/kg"], r"no-calorie sweeteners",
     "The document mentions low- and no-calorie sweeteners (p.55) and links to FDA, but gives no ADI values."),
    ("t27", "What glycemic index values do the guidelines give for brown rice versus white rice?",
     [r"glycemic", r"\bGI\b"], r"Brown rice",
     "Brown rice replaces white rice in the burrito-bowl figure (Figure 1-8), tempting a GI claim."),
    ("t28", "Do the guidelines recommend choosing organic produce to reduce pesticide residues for children?",
     [r"organic", r"pesticide", r"herbicide", r"residue"], r"vegetables",
     "Heavily discusses vegetables and fruit for children, but never organic vs conventional or pesticides."),
    ("t29", "How much microplastic exposure comes from eating seafood, and do the guidelines limit seafood because of it?",
     [r"microplastic", r"plastic"], r"methylmercury",
     "Seafood safety is discussed only in terms of methylmercury (FDA/EPA advice)."),
    ("t30", "What do the guidelines say about monosodium glutamate (MSG) as a hidden source of sodium?",
     [r"monosodium", r"\bMSG\b", r"glutamate"], r"sodium",
     "Sodium sources are discussed at length (Figure 1-12), but MSG is never named."),
]
NONE_D = [
    ("d19", "What daily carbohydrate limit (grams) do the guidelines set for people following a ketogenic diet?",
     [r"ketogenic", r"\bketo\b", r"ketosis", r"low[- ]carb"], r"carbohydrate",
     "Carbohydrate appears in nutrient goal tables, but no keto/low-carb guidance exists."),
    ("d20", "Are creatine or whey protein powder supplements recommended for teenage athletes?",
     [r"creatine", r"\bwhey\b", r"protein powder", r"protein supplement"], r"protein foods",
     "Protein foods and adolescents are covered, and supplements are discussed for other nutrients."),
    ("d21", "How should a child with celiac disease replace gluten-containing grains to meet the grains recommendation?",
     [r"celiac", r"gluten", r"coeliac"], r"whole grains",
     "Grains/whole-grain guidance is extensive, but no gluten-free or celiac guidance."),
    ("d22", "Do the guidelines recommend probiotic supplements or kombucha to support an infant's gut microbiome?",
     [r"probiotic", r"prebiotic", r"kombucha", r"fermented", r"microbiome", r"gut health"], r"kefir",
     "Yogurt and kefir appear as dairy examples (e.g. p.42, p.158) and yogurt is suggested for infants, tempting a probiotic/gut-health claim; the document never discusses probiotics or the microbiome."),
]

# ================================================================ DEV (22)
add("d01", "dev", "table", ["appendix", "oils"],
    "On a 2,400-calorie Healthy U.S.-Style pattern, how many grams of oils per day are included?",
    [F(157, "table", "Table A3-2, row 'Oils (grams/day)', column '2,400'", region(157, "Table A3-2", "Oils (grams/day)"), quote="Healthy U.S.-Style Dietary Pattern for Ages 2 and Older")],
    "Single-cell lookup with units.",
    answer="31 grams of oils per day (Table A3-2, 2,400-calorie column).")

add("d02", "dev", "table", ["toddlers", "calorie-needs"],
    "What are the estimated daily calorie needs of a 15-month-old boy and a 15-month-old girl?",
    [F(152, "table", "Table A2-1, row '15', columns 'Males' and 'Females'", region(152, "AGE IN MONTHS", "21 through 23", top_pad=40), quote="Estimated Calorie Needs per Day, by Age and Sex, Ages 12 Through 23 Months")],
    "Small table; row/column lookup.",
    answer="15-month-old boy: 900 calories/day; 15-month-old girl: 800 calories/day (Table A2-1).")

add("d03", "dev", "table", ["mediterranean", "fruits", "dairy"],
    "In the Healthy Mediterranean-Style pattern at 2,000 calories, how much fruit and how much dairy are recommended per day for an adult?",
    [F(162, "table", "Table A3-5, rows 'Fruits (cup eq/day)' and 'Dairy (cup eq/day)', column '2,000'", region(162, "Table A3-5", "Dairy (cup eq/day)"), quote="Healthy Mediterranean-Style Dietary Pattern for Ages 2 and Older")],
    "Lookup; Mediterranean values differ from U.S.-Style (fruit 2½ vs 2, dairy 2 vs 3).",
    answer="Fruits 2½ cup-eq/day and dairy 2 cup-eq/day (Table A3-5, 2,000 calories; children/adolescents have different dairy amounts per footnote d).")

add("d04", "dev", "table", ["pregnancy", "weight-gain"],
    "What total weight gain range is recommended during pregnancy for a woman who was underweight (BMI under 18.5) before pregnancy?",
    [F(125, "table", "Table 5-3, row 'Underweight'", BB["tab5_3"], quote="Weight Gain Recommendations for Pregnancy")],
    "Row lookup by condition.",
    answer="28-40 lb total; about 1 lb/week (range 1-1.3 lb) in the 2nd and 3rd trimesters (Table 5-3, Underweight, BMI < 18.5).")

add("d05", "dev", "image", ["meal", "swap", "photo-table"],
    "In the 'one meal at a time' burrito bowl example, how many calories does the nutrient-dense bowl save compared with the typical bowl, and what replaces the white rice?",
    [F(51, "figure", "Figure 1-8, header row and first row of the comparison", BB["fig1_8_table"], quote="Total Calories = 1,120")],
    "Photo + comparison panel; requires subtraction.",
    answer="Typical bowl 1,120 calories vs nutrient-dense bowl 715 calories: saves 1,120 - 715 = 405 calories. White rice (1½ cups) is replaced by brown rice (1 cup) + romaine lettuce (½ cup).")

add("d06", "dev", "image", ["life-stage", "diagram", "infants"],
    "According to the lifespan science diagram, what health benefits of healthy eating are listed for the birth-to-23-months stage?",
    [F(37, "figure", "Figure 1-3, panel 'Birth Through 23 Months'", region(37, "Figure 1-3", "Favorable bone health"), quote="Lower risk of peanut allergy")],
    "Panel selection in a diagram (different panel from t08).",
    answer="Lower risk of overweight and obesity; lower risk of type 1 diabetes; adequate iron status and lower risk of iron deficiency; lower risk of peanut allergy; lower risk of asthma (Figure 1-3).")

add("d07", "dev", "image", ["toddlers", "swap", "photo-panel"],
    "For toddlers, what does the healthy-shifts photo panel suggest instead of cereal with added sugars and instead of fruit products with added sugars?",
    [F(76, "figure", "Figure 2-1, arrows 'Cereal with Added Sugars -> Cereal with Minimal Added Sugars' and 'Fruit Products with Added Sugars -> Fruit (e.g., canned in 100% juice)'", BB["fig2_1"],
       quote="Cereal with Minimal Added Sugars")],
    "Arrow-encoded pairs (different pairs from t11).",
    answer="Cereal with added sugars -> cereal with minimal added sugars; fruit products with added sugars -> fruit (e.g., canned in 100% juice) (Figure 2-1).")

add("d08", "dev", "chart", ["stacked-bar", "calories"],
    "For a 4-ounce piece of breaded, fried cod, how many calories come from the fish itself and how many from breading and frying oil?",
    [F(34, "figure", "Figure 1-1, bar 'Breaded, Fried Cod, 4 ounces'", BB["fig1_1"], quote="Baked Cod Breading & Frying Oil 99 131 230 Total",
       reading="Stacked bar, x-axis CALORIES; blue = nutrient-dense form (baked cod) 99, orange = additional (breading & frying oil) 131, total label 230.")],
    "Legend-to-segment mapping.",
    answer="Baked cod 99 calories + breading & frying oil 131 calories = 230 calories total (the additions are ~57% of the calories).")

add("d09", "dev", "chart", ["bubble-chart", "sodium", "sources"],
    "What is the top food-category source of sodium for Americans aged 1 and older, what share does it contribute, and what is the average sodium intake shown?",
    [F(60, "figure", "Figure 1-12, largest bubble 'Sandwiches' and side label 'Sodium Average Intake'", BB["fig1_12"], quote="Sandwiches 21%",
       reading="Bubble chart; labels printed: Sandwiches 21% (largest), Rice, Pasta & Other Grain-Based Mixed Dishes 8%; 'Average Intake: 3,393 mg/day' is printed at left (not in the text layer, read from image).")],
    "Requires reading a label that exists only in the image.",
    answer="Sandwiches, 21% of sodium intake; average sodium intake 3,393 mg/day (Figure 1-12).")

add("d10", "dev", "chart", ["donut", "adolescents", "sodium"],
    "What are the average daily sodium intakes of boys and girls aged 14-18, and how far above the 2,300 mg limit is each?",
    [F(98, "figure", "Figure 3-8, 'Sodium' panel (Limit: 2,300 mg; Average Intakes)", region(98, "Figure 3-8", "Data Sources"), quote="Males 3,888 mg Females 2,875 mg",
       reading="Average intake labels under the Sodium donuts: Males 3,888 mg, Females 2,875 mg; panel limit 2,300 mg.")],
    "Read labelled values under correct panel, then subtract.",
    answer="Boys 3,888 mg/day (1,588 mg above 2,300); girls 2,875 mg/day (575 mg above 2,300).")

add("d11", "dev", "chart", ["diverging-bar", "axis-reading", "subgroups"],
    "In the chart comparing intakes to recommendations for Americans aged 1+, which food subgroup has the largest percentage of the population below its recommendation, and roughly what percentage?",
    [F(43, "figure", "Figure 1-6, lower (dark blue) bars 'Percent of Population Below Recommendation'", BB["fig1_6"], quote="Intake Below Recommendation",
       reading="Diverging bars around a 0 line; lower half axis 0-100% below recommendation. Verified from vector data (get_drawings): 0 line y≈505.7pt, 10 percentage points ≈11.8pt; Whole Grains bar ends at y=621.7pt ≈98%; next deepest Red & Orange Vegetables ≈95%, Total Vegetables ≈90%. Tolerance ±3 points.")],
    "No printed values; requires axis reading.",
    answer="Whole grains: about 98% of the population is below the recommendation (≈95-100%; next is red & orange vegetables at about 95%).")

add("d12", "dev", "multihop", ["added-sugars", "limit", "compute"],
    "If a person on a 2,000-calorie diet ate the U.S. average amount of added sugars, how far over the guideline limit for added sugars would they be?",
    [F(56, "figure", "Figure 1-10, label 'Added Sugars Average Intake: 266 kcal/day'", BB["fig1_10"], quote="Added Sugars Average Intake: 266 kcal/day",
       reading="Printed label left of the bubble chart."),
     T(54, "limits added sugars to less than 10 percent of calories per day")],
    "Combine a figure value with a text rule and compute.",
    answer="Limit: less than 10% of 2,000 = 200 kcal/day. Average intake 266 kcal/day -> about 66 kcal/day over the limit (~33% above).")

add("d13", "dev", "multihop", ["toddlers", "calorie-needs", "chain"],
    "An 18-month-old girl no longer drinks breast milk or formula. Using her estimated calorie needs, how much dairy and how many vegetables should her daily pattern include?",
    [F(152, "table", "Table A2-1, row '18', column 'Females'", region(152, "AGE IN MONTHS", "21 through 23", top_pad=40), quote="Estimated Calorie Needs per Day, by Age and Sex, Ages 12 Through 23 Months"),
     F(156, "table", "Table A3-1, rows 'Vegetables (cup eq/day)' and 'Dairy (cup eq/day)', column '900'", region(156, "Table A3-1", "Dairy (cup eq/day)"), quote="Who Are No Longer Receiving Human Milk or Infant Formula")],
    "Chain from Appendix 2 to Appendix 3 toddler table.",
    answer="Estimated need: 900 calories/day (female, 18 months). At 900 calories: dairy 2 cup-eq/day, vegetables 1 cup-eq/day.")

add("d14", "dev", "multihop", ["older-adults", "seafood", "cross-table"],
    "At 2,000 calories, how does the weekly seafood amount in the pattern for adults 60+ compare with the general Healthy U.S.-Style pattern for ages 2+?",
    [F(138, "table", "Table 6-1, row 'Seafood (ounce eq/wk)', column '2,000'", region(138, "Table 6-1", "Seafood (ounce eq/wk)"), quote="Healthy U.S.-Style Dietary Pattern for Adults Ages 60 and Older"),
     F(157, "table", "Table A3-2, row 'Seafood (ounce eq/wk)', column '2,000'", region(157, "Table A3-2", "Seafood (ounce eq/wk)"), quote="Healthy U.S.-Style Dietary Pattern for Ages 2 and Older")],
    "Same row/column in two different tables (chapter vs appendix).",
    answer="Adults 60+: 9 ounce-eq/week vs general pattern 8 ounce-eq/week -> 1 ounce-eq more per week for older adults.")

add("d15", "dev", "text", ["infants", "vitamin-D", "conditional"],
    "Which infants need a vitamin D supplement, how much, and when is it not needed?",
    [T(69, "will need a vitamin D supplement of 400 IU per day beginning soon after birth"),
     T(69, "when an infant is receiving full feeds of infant formula, vitamin D supplementation is not needed")],
    "Conditional on feeding mode.",
    answer="Infants fed human milk exclusively or mixed-fed (human milk + formula) need 400 IU vitamin D per day beginning soon after birth; infants receiving full feeds of (vitamin D-fortified) infant formula do not need supplementation.")

add("d16", "dev", "text", ["infants", "food-safety"],
    "Can a baby under 1 year have honey, for example baked into foods, and why?",
    [T(74, "Infants should not be given any foods containing raw or cooked honey"),
     T(74, "Honey can contain the Clostridium botulinum organism that could cause serious illness or death among infants")],
    "Condition 'cooked' is explicitly covered.",
    answer="No. Infants should not be given any foods containing raw or cooked honey because honey can contain Clostridium botulinum, which can cause serious illness or death in infants. (Unpasteurized foods/beverages should also be avoided.)")

add("d17", "dev", "text", ["infants", "vitamin-B12", "vegan"],
    "A breastfeeding mother follows a strict vegan diet. What does the guidance say about vitamin B12 for her baby?",
    [T(69, "Human milk has sufficient vitamin B12 to meet infant needs unless the mother's vitamin B12 status is inadequate"),
     T(69, "the mother and/or infant fed human milk may require a vitamin B12 supplement")],
    "Conditional (vegan mother at risk of deficiency).",
    answer="Human milk normally has enough B12, unless the mother's B12 status is inadequate (e.g., a strictly vegan diet without animal-source foods). Then human milk may not provide enough B12, and the mother and/or infant may need a B12 supplement; consult a healthcare provider.")

add("d18", "dev", "text", ["sodium", "CDRR", "age-conditional"],
    "What sodium intake level (CDRR) applies to a 6-year-old, a 12-year-old and an adult?",
    [T(59, "1,200 mg/day for ages 1 through 3; 1,500 mg/day for ages 4 through 8; 1,800 mg/day for ages 9 through 13; and 2,300 mg/day for all other age groups")],
    "Age-conditional lookup in running text.",
    answer="6-year-old: 1,500 mg/day (ages 4-8); 12-year-old: 1,800 mg/day (ages 9-13); adult: 2,300 mg/day (also 1,200 mg/day for ages 1-3).")

# ---------------------------------------------------------------- none items


def none_item(id_, split, q, pats, control, near):
    return add(id_, split, "none", ["abstention"], q, [], f"Near-topic question with no support anywhere in the document; tests abstention. {near}",
               absence={"method": "Case-insensitive regex over the PyMuPDF text layer of all 164 pages (whitespace/ligature/quote normalised); "
                                  "plus visual review (150-dpi renders) of the figure/table pages inspected while building the benchmark (PDF p.34, 35, 43, 50, 51, 56, 60, 76, 78, 90, 125, 126, 139, 153 and crops of 37, 52-53, 98, 138, 152, 156, 157, 162) on 2026-11-16 - none show this topic; "
                                  "figure labels are part of the text layer for these vector figures, so the regex sweep also covers figure text.",
                        "searched_pages": "1-164", "patterns": pats, "expected_hits": 0, "control_pattern": control, "control_min_hits": 1},
               near=near)


for it in NONE_T:
    none_item(it[0], "test", *it[1:])
for it in NONE_D:
    none_item(it[0], "dev", *it[1:])

# ---------------------------------------------------------------- finalise
os.makedirs(CROPS, exist_ok=True)


def _norm(s):
    for a, b in {"\ufb01": "fi", "\ufb02": "fl", "\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
                 "\u2014": "-", "\u2013": "-", "\u00ad": ""}.items():
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s)


_PAGES = [_norm(p.get_text()) for p in doc]
for q in Q:
    ac = q.get("absence_check")
    if ac:
        ac["pattern_page_hits"] = {pat: [i + 1 for i, t in enumerate(_PAGES) if re.search(pat, t, re.I)] for pat in ac["patterns"]}
        ac["control_page_hits"] = [i + 1 for i, t in enumerate(_PAGES) if re.search(ac["control_pattern"], t, re.I)]
        assert not any(ac["pattern_page_hits"].values()), (q["id"], ac["pattern_page_hits"])
        assert ac["control_page_hits"], q["id"]
for q in Q:
    n = 0
    for ev in q["evidence"]:
        ev["printed_page"] = printed_page(ev["pdf_page"])
        if ev["bbox"] is not None:
            n += 1
            pg = doc[ev["pdf_page"] - 1]
            r = fitz.Rect(ev["bbox"]) & pg.rect
            ev["bbox"] = [round(v, 1) for v in r]
            rel = f"benchmark/dga/crops/{q['id']}_{n}.jpg"
            path = os.path.join(CROPS, f"{q['id']}_{n}.jpg")
            for dpi, qual in ((150, 80), (120, 75), (100, 70), (85, 65)):
                pix = pg.get_pixmap(clip=r, dpi=dpi)
                pix.save(path, jpg_quality=qual)
                if os.path.getsize(path) < 150_000:
                    break
            ev["crop"] = rel
    # key order
order = ["id", "split", "group", "tags", "question", "expected_answer", "expected_behavior", "answerable",
         "evidence", "rationale", "absence_check", "near_topic"]
with open(OUT, "w", encoding="utf-8") as f:
    for q in Q:
        f.write(json.dumps({k: q[k] for k in order if k in q}, ensure_ascii=False) + "\n")
print(f"wrote {len(Q)} questions -> {OUT}")
