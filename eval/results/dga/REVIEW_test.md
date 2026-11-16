# Duyệt tay benchmark test DGA (cấu hình chốt `vision`)

Mỗi câu: câu hỏi, đáp án gold + vùng bằng chứng (crop trong `benchmark/dga/crops/`), câu trả lời và citation của agent,
nhãn tự động (DRAFT: kiểm citation tất định + judge Sonnet 5.5) và nhãn duyệt tay (`manual_review_test.json`).

## Tổng hợp

| Nhãn | Đạt | table | image | chart | multihop | text | none |
|---|---|---|---|---|---|---|---|
| Tự động (DRAFT) | 26/30 (86.7%) | 6/6 | 4/5 | 4/5 | 2/4 | 4/4 | 6/6 |
| Tự động + đề xuất sau khi xem crop gốc (chưa duyệt tay) | 29/30 (96.7%) | 6/6 | 4/5 | 5/5 | 4/4 | 4/4 | 6/6 |
| Duyệt tay (30/30 câu đã duyệt) | 29/30 (96.7%) | 6/6 | 4/5 | 5/5 | 4/4 | 4/4 | 6/6 |

Câu chưa duyệt tay: không

## t01 · table

**Hỏi:** For a client on an 1,800-calorie Healthy U.S.-Style eating pattern (age 2+), how many cup-equivalents per week of red & orange vegetables and of dark-green vegetables does the pattern call for?

**Gold:** Red & orange vegetables: 5½ cup eq per week; dark-green vegetables: 1½ cup eq per week (Table A3-2, 1,800-calorie column; subgroup amounts are weekly).

**Bằng chứng gold:** p.157 Table A3-2, rows 'Red and Orange Vegetables (cup eq/wk)' and 'Dark-Green Vegetables (cup eq/wk)', column '1,800' ([crop](../../../benchmark/dga/crops/t01_1.jpg))

**Agent (answered, 4.6 s, $0.0181):** At the 1,800-calorie level, the Healthy U.S.-Style Dietary Pattern for ages 2 and older (Table A3-2, printed p. 144) calls for: - **Dark-green vegetables:** 1 ½ cup-equivalents per week [cite:dga:p157:r1] - **Red and orange vegetables:** 5 ½ cup-equivalents per week. The table text I retrieved was cut off before the 1,800 value for this row. I took 5 ½ from the adult and adolescent tables for the same calorie level, where it is stated. [cite:dga:p097:r1] [cite:dga:p109:r1]

**Citation:** dga:p157:r1, dga:p097:r1, dga:p109:r1

**Nhãn tự động:** ĐẠT — The values 1½ cup eq/wk dark-green and 5½ cup eq/wk red & orange at 1,800 kcal match the gold answer. The cited p157 table supports dark-green, and its indexed text and crop also show 5½ for red & orange, so the agent's claim of truncated text is wrong but harmless. The p097 and p109 tables support 5½ as well.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — Dark-green 1½ cup eq/tuần cite đúng Table A3-2 (p.157). Red & orange 5½: agent nói phần bảng A3-2 bị cắt nên lấy từ Table 4-1 (p.109, cùng mẫu U.S.-Style, cột 1.800 = 5½ — đã xem crop) và Table 3-3; số đúng, bằng chứng tương đương. BIÊN — người duyệt cân nhắc.

**Nhãn duyệt tay:** ĐẠT — Dark-green 1½ cup eq/tuần cite đúng Table A3-2 (p.157). Red & orange 5½: agent nói phần bảng A3-2 bị cắt nên lấy từ Table 4-1 (p.109, cùng mẫu U.S.-Style, cột 1.800 = 5½ — đã xem crop) và Table 3-3; số đúng, bằng chứng tương đương. BIÊN — người duyệt cân nhắc. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t02 · table

**Hỏi:** A moderately active 16-year-old boy and a moderately active 16-year-old girl: what are their estimated daily calorie needs, and how big is the gap?

**Gold:** Boy: 2,800 calories/day; girl: 2,000 calories/day; difference = 2,800 - 2,000 = 800 calories/day (Table A2-2, age 16, moderately active).

**Bằng chứng gold:** p.153 Table A2-2, row '16', columns Males 'Moderately Active' and Females 'Moderately Active' ([crop](../../../benchmark/dga/crops/t02_1.jpg))

**Agent (answered, 4.7 s, $0.0198):** At age 16 and moderately active, the boy needs an estimated 2,800 calories per day and the girl needs 2,000 calories per day. The gap is 2,800 − 2,000 = 800 calories per day, with the boy needing more. [cite:dga:p153:r1] This comes from Table A2-2, "Estimated Calorie Needs per Day, by Age, Sex, and Physical Activity Level," on printed page 140. [cite:dga:p153:r1]

**Citation:** dga:p153:r1

**Nhãn tự động:** ĐẠT — The answer gives 2,800 (boy) and 2,000 (girl) calories/day with an 800 gap, matching the gold answer. The cited Table A2-2 row for age 16 shows Males Moderately Active 2,800 and Females Moderately Active 2,000, and the printed page 140 / PDF p.153 reference is correct.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — 2.800 vs 2.000 kcal, chênh 800; cite Table A2-2 p.153 đúng vùng.

**Nhãn duyệt tay:** ĐẠT — 2.800 vs 2.000 kcal, chênh 800; cite Table A2-2 p.153 đúng vùng. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t03 · table

**Hỏi:** How many extra calories per day does a breastfeeding woman with a healthy pre-pregnancy weight need in the first 6 months postpartum, and how is that figure derived?

**Gold:** +330 calories/day vs pre-pregnancy needs (applies to women with a healthy pre-pregnancy weight). Derivation (footnote b): +500 calories/day for milk production minus 170 calories/day for weight loss in the first 6 months postpartum = 330.

**Bằng chứng gold:** p.125 Table 5-2, row 'Lactation: 1st 6 months' + footnote b ([crop](../../../benchmark/dga/crops/t03_1.jpg))

**Agent (answered, 6.1 s, $0.0303):** A breastfeeding woman with a healthy pre-pregnancy weight needs about **330 extra calories per day** in the first 6 months postpartum, compared with her pre-pregnancy needs [cite:dga:p125:r1]. **How it is derived:** - The document adds 500 calories/day to pre-pregnancy needs to cover the energy needed for milk production. - It then subtracts 170 calories/day to account for weight loss in the first 6 months postpartum. - The arithmetic is 500 − 170 = 330 calories/day [cite:dga:p125:r1]. For comparison, the second 6 months adds 400 calories/day for milk production. Weight is assumed to be stable after 6 months postpartum, so nothing is subtracted [cite:dga:p125:r1]. The estimates are based on the Institute of Medicine's Estimated Energy Requirements. They apply only to women with a healthy pre-pregnancy weight [cite:dga:p125:r1]. The source is Table 5-2 on printed page 112 (repeated as Table A2-3 on printed page 141).

**Citation:** dga:p125:r1

**Nhãn tự động:** ĐẠT — The answer gives +330 calories/day and the derivation 500 − 170, which matches the gold. The cited Table 5-2 crop and its footnotes support all claims, including the 400 calories for the second 6 months, the IOM EER basis, and the healthy-weight condition. The mention of Table A2-3 on printed page 141 is not in the cited unit, but it is a minor extra detail.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — +330 kcal = 500 − 170, đúng điều kiện cân nặng khỏe mạnh; cite Table 5-2 p.125.

**Nhãn duyệt tay:** ĐẠT — +330 kcal = 500 − 170, đúng điều kiện cân nặng khỏe mạnh; cite Table 5-2 p.125. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t04 · table

**Hỏi:** In the eating pattern for adults 60 and older at 2,000 calories, how many calories per day are left for 'other uses' and what share of the total is that? How much protein foods is recommended at that level?

**Gold:** 240 kcal/day for other uses, which is 12% of calories; protein foods 5½ ounce-eq per day (Table 6-1, 2,000-calorie column).

**Bằng chứng gold:** p.138 Table 6-1, rows 'Limit on Calories for Other Uses (kcal/day)', '(%/day)', 'Protein Foods (ounce eq/day)', column '2,000' ([crop](../../../benchmark/dga/crops/t04_1.jpg))

**Agent (answered, 7.2 s, $0.0333):** At the 2,000-calorie level, the Healthy U.S.-Style Dietary Pattern for adults 60 and older leaves 240 kcal/day for other uses. That is 12% of the day's calories. The table lists this as the "limit on calories for other uses" in kcal/day and as a percentage per day. As a check, 240 ÷ 2,000 = 12%. [cite:dga:p138:r1] Recommended protein foods at that level are 5 ½ ounce equivalents per day. [cite:dga:p138:r1] The source is Table 6-1 on printed page 125 (Chapter 6, Older Adults).

**Citation:** dga:p138:r1

**Nhãn tự động:** ĐẠT — The answer gives 240 kcal/day, 12%, and 5½ ounce-eq protein foods at the 2,000-calorie level for adults 60+, matching the gold answer. The cited Table 6-1 (pdf p.138, printed p.125) shows these values in the 2,000 column, so the citation supports every claim.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — 240 kcal = 12%, đạm 5½ oz eq; cite Table 6-1 p.138.

**Nhãn duyệt tay:** ĐẠT — 240 kcal = 12%, đạm 5½ oz eq; cite Table 6-1 p.138. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t05 · table

**Hỏi:** A woman whose pre-pregnancy BMI is 27 asks how much weight she should gain in total during pregnancy and per week in the 2nd and 3rd trimesters. What does the guidance table say?

**Gold:** BMI 27 falls in the Overweight category (BMI 25-29.9): total gain 15-25 lb; weekly gain in the 2nd and 3rd trimesters 0.6 lb on average (range 0.5-0.7 lb/week). (Calculations assume 1.1-4.4 lb gained in the first trimester.)

**Bằng chứng gold:** p.125 Table 5-3, row 'Overweight' (BMI 25-29.9) ([crop](../../../benchmark/dga/crops/t05_1.jpg))

**Agent (answered, 4.5 s, $0.0137):** A BMI of 27 falls in the "Overweight" category, which covers BMI 25–29.9. For that category, Table 5-3 ("Weight Gain Recommendations for Pregnancy," printed p. 112) gives: - **Total weight gain:** 15–25 lb. [cite:dga:p125:r2] - **Weekly gain in the 2nd and 3rd trimesters:** a mean of 0.6 lb per week, with a range of 0.5–0.7 lb per week. [cite:dga:p125:r2]

**Citation:** dga:p125:r2

**Nhãn tự động:** ĐẠT — The answer correctly identifies BMI 27 as Overweight with total gain of 15-25 lb and weekly gain of 0.6 lb (range 0.5-0.7) in the 2nd and 3rd trimesters, matching the gold answer; the cited Table 5-3 supports every value. The first-trimester footnote is omitted, but the gold treats it as a parenthetical assumption.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — BMI 27 = Overweight, 15–25 lb, 0,6 lb/tuần (0,5–0,7); cite Table 5-3 p.125. Không nêu giả định 1,1–4,4 lb quý 1 — không được hỏi.

**Nhãn duyệt tay:** ĐẠT — BMI 27 = Overweight, 15–25 lb, 0,6 lb/tuần (0,5–0,7); cite Table 5-3 p.125. Không nêu giả định 1,1–4,4 lb quý 1 — không được hỏi. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t06 · table

**Hỏi:** For a toddler (12-23 months) who no longer drinks breast milk or formula, eating on the 1,000-calorie pattern, how much dairy, fruit and grains are recommended per day?

**Gold:** Dairy 2 cup eq/day, fruits 1 cup eq/day, grains 3 ounce eq/day (Table A3-1, 1,000-calorie column).

**Bằng chứng gold:** p.156 Table A3-1, rows 'Dairy (cup eq/day)', 'Fruits (cup eq/day)', 'Grains (ounce eq/day)', column '1,000' ([crop](../../../benchmark/dga/crops/t06_1.jpg))

**Agent (answered, 5.6 s, $0.0163):** On the 1,000-calorie Healthy U.S.-Style Dietary Pattern for toddlers aged 12 through 23 months who no longer receive human milk or infant formula, the daily amounts are: - **Dairy:** 2 cup eq/day [cite:dga:p156:r1] - **Fruits:** 1 cup eq/day [cite:dga:p156:r1] - **Grains:** 3 ounce eq/day. This is made up of 2 ounce eq of whole grains and 1 ounce eq of refined grains [cite:dga:p156:r1]. These values come from Table A3-1 on printed page 143. Table 2-1 on printed page 64 gives the same pattern [cite:dga:p077:r1].

**Citation:** dga:p156:r1, dga:p077:r1

**Nhãn tự động:** ĐẠT — The values (dairy 2 cup eq/day, fruits 1 cup eq/day, grains 3 ounce eq/day) match the gold answer, and the whole/refined split of 2 and 1 ounce eq is also correct. Both cited tables (A3-1 on p.156 and Table 2-1 on p.77) show these 1,000-calorie values.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — Sữa 2 cup, trái cây 1 cup, ngũ cốc 3 oz eq; cite Table A3-1 p.156.

**Nhãn duyệt tay:** ĐẠT — Sữa 2 cup, trái cây 1 cup, ngũ cốc 3 oz eq; cite Table A3-1 p.156. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t07 · image

**Hỏi:** In the guidelines' side-by-side photo panel of 'typical' versus nutrient-dense single choices, what is shown as the better choice instead of butter, and instead of soda?

**Gold:** Butter -> vegetable oil; soda -> sparkling water (Figure 1-2: the top 'Nutrient-dense' row pairs with the bottom 'Typical' row in each column).

**Bằng chứng gold:** p.35 Figure 1-2 (Making Nutrient-Dense Choices: One Food or Beverage At a Time), columns 4 and 5 ([crop](../../../benchmark/dga/crops/t07_1.jpg))

**Agent (answered, 3.1 s, $0.0101):** In Figure 1-2, "Making Nutrient-Dense Choices: One Food or Beverage At a Time" (printed p. 22), the panel pairs nutrient-dense choices (top, blue band) with typical choices (bottom, orange band) [cite:dga:p035:r1]. - **Instead of butter (typical):** vegetable oil is the nutrient-dense choice [cite:dga:p035:r1]. - **Instead of soda (typical):** sparkling water is the nutrient-dense choice [cite:dga:p035:r1].

**Citation:** dga:p035:r1

**Nhãn tự động:** ĐẠT — The answer gives vegetable oil for butter and sparkling water for soda, matching the gold. The cited Figure 1-2 crop shows these as column pairs, with Vegetable Oil above Butter and Sparkling Water above Soda.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — Bơ → dầu thực vật, soda → nước có ga; đã xem crop Figure 1-2 p.35.

**Nhãn duyệt tay:** ĐẠT — Bơ → dầu thực vật, soda → nước có ga; đã xem crop Figure 1-2 p.35. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t08 · image

**Hỏi:** According to the diagram summarising the science on healthy eating across the lifespan, what benefits are listed for women who are pregnant or lactating?

**Gold:** Two benefits: favorable cognitive development in the child, and favorable folate status in women during pregnancy and lactation (Figure 1-3).

**Bằng chứng gold:** p.37 Figure 1-3, panel 'Women Who Are Pregnant or Lactating' ([crop](../../../benchmark/dga/crops/t08_1.jpg))

**Agent (answered, 4.9 s, $0.0154):** Figure 1-3 (printed p. 24) lists two benefits for women who are pregnant or lactating: - Favorable cognitive development in the child. [cite:dga:p037:r1] - Favorable folate status in women during pregnancy and lactation. [cite:dga:p037:r1]

**Citation:** dga:p037:r1

**Nhãn tự động:** ĐẠT — The agent lists both benefits from the gold answer (favorable cognitive development in the child, favorable folate status during pregnancy and lactation). The cited crop of Figure 1-3 on pdf p.37 shows exactly these two items in the 'Women Who Are Pregnant or Lactating' panel.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — Hai lợi ích (phát triển nhận thức của trẻ, tình trạng folate của mẹ); cite Figure 1-3 p.37.

**Nhãn duyệt tay:** ĐẠT — Hai lợi ích (phát triển nhận thức của trẻ, tình trạng folate của mẹ); cite Figure 1-3 p.37. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t09 · image

**Hỏi:** In the 85-15 guide graphic, what share of daily calories is needed to meet food group needs in nutrient-dense forms, and what is the remaining share available for?

**Gold:** About 85% of daily calories are needed to meet food group recommendations in nutrient-dense forms; the remaining ~15% is available for other uses, including added sugars and saturated fat (the text adds: eating more than the recommended amount of a food group, or alcohol), about 250-350 calories for most Americans' calorie patterns.

**Bằng chứng gold:** p.50 Figure 1-7 (The 85-15 Guide) ([crop](../../../benchmark/dga/crops/t09_1.jpg)); p.50 PDF p.50 body text

**Agent (answered, 3.5 s, $0.0091):** About 85% of daily calories are needed to meet food group recommendations in nutrient-dense forms. The remaining 15% is available for other uses, including added sugars and saturated fat. [cite:dga:p050:r1] This comes from Figure 1-7, "The 85-15 Guide," on printed page 37. [cite:dga:p050:r1]

**Citation:** dga:p050:r1

**Nhãn tự động:** ĐẠT — The answer gives 85% for nutrient-dense food group needs and 15% for other uses including added sugars and saturated fat, matching the figure. The 250-350 calorie detail is extra and not required; the cited Figure 1-7 supports every claim made.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — 85% / 15% cho mục đích khác gồm đường bổ sung, chất béo bão hoà; cite Figure 1-7 p.50. Không nêu 250–350 kcal — không bắt buộc với câu hỏi.

**Nhãn duyệt tay:** ĐẠT — 85% / 15% cho mục đích khác gồm đường bổ sung, chất béo bão hoà; cite Figure 1-7 p.50. Không nêu 250–350 kcal — không bắt buộc với câu hỏi. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t10 · image

**Hỏi:** The guidelines show a sample day of nutrient-dense meals that comes in under 2,000 calories. What are the calorie totals for breakfast, lunch, dinner and snacks, and what does the whole day add up to?

**Gold:** Breakfast 375, lunch 715, dinner 585, snacks 300 calories; day total = 375 + 715 + 585 + 300 = 1,975 calories (under 2,000).

**Bằng chứng gold:** p.52 Figure 1-9 (Making Healthy Choices: One Day At a Time), Breakfast and Lunch panels ([crop](../../../benchmark/dga/crops/t10_1.jpg)); p.53 Figure 1-9 (continued), Dinner and Snacks panels ([crop](../../../benchmark/dga/crops/t10_2.jpg))

**Agent (answered, 5.1 s, $0.0179):** The sample day in Figure 1-9, "Making Healthy Choices: One Day At a Time" (printed pp. 39–40), gives these calorie totals: - **Breakfast:** 375 calories [cite:dga:p052:c0] - **Lunch:** 715 calories [cite:dga:p052] - **Dinner:** 585 calories [cite:dga:p053:f0] - **Snacks:** 300 calories [cite:dga:p053:f0] The meals add up to 375 + 715 + 585 + 300 = 1,975 calories. That fits the text's "under 2,000 calories" [cite:dga:p052:c0]. The page's summary line says the sample meals illustrate a total of 2,000 calories for the day [cite:dga:p053:f0]. That is a rounded figure. The sum of the four meal totals is 1,975.

**Citation:** dga:p052:c0, dga:p052, dga:p053:f0

**Nhãn tự động:** KHÔNG ĐẠT — The answer gives 375, 715, 585 and 300 calories and a correct sum of 1,975, matching the gold. Each figure is backed by the cited units: p52 chunk for breakfast and lunch, p53 facts for dinner and snacks, and the 'under 2,000' wording. The page's 'total of 2,000' line is also in the cited facts, so the note about rounding is supported. · vùng gold chưa được cite: ['Figure 1-9 (Making Healthy Choices: One Day At a Time), Breakfast and Lunch panels', 'Figure 1-9 (continued), Dinner and Snacks panels']

**Đề xuất (chưa phải nhãn duyệt tay):** KHÔNG ĐẠT — Số liệu đúng (375/715/585/300, tổng 1.975) nhưng citation chỉ là trang và fact (dga:p052, dga:p052:c0, dga:p053:f0), không chỉ ra vùng Figure 1-9 → không đạt yêu cầu 'citation xác định được trang và vùng evidence'.

**Nhãn duyệt tay:** KHÔNG ĐẠT — Số liệu đúng (375/715/585/300, tổng 1.975) nhưng citation chỉ là trang và fact (dga:p052, dga:p052:c0, dga:p053:f0), không chỉ ra vùng Figure 1-9 → không đạt yêu cầu 'citation xác định được trang và vùng evidence'. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t11 · image

**Hỏi:** For toddlers, which healthier swaps does the guidelines' photo panel suggest for fried vegetables and for high-sodium meats?

**Gold:** Fried vegetables -> roasted vegetables; high-sodium meats -> ground lean meats (Figure 2-1).

**Bằng chứng gold:** p.76 Figure 2-1 (Make Healthy Shifts To Empower Toddlers ...), arrows 'Fried Vegetables -> Roasted Vegetables' and 'High-sodium Meats -> Ground Lean Meats' ([crop](../../../benchmark/dga/crops/t11_1.jpg))

**Agent (answered, 4.3 s, $0.014):** Figure 2-1 (printed p. 63) shows the two swaps you asked about: - **Fried vegetables:** swap them for roasted vegetables. [cite:dga:p076:r1] - **High-sodium meats:** swap them for ground lean meats. [cite:dga:p076:r1] Figure 2-1 is titled "Make Healthy Shifts To Empower Toddlers To Eat Nutrient-Dense Foods in Dietary Patterns." It has six photo pairs, and each pair shows a less nutrient-dense choice shifting to a more nutrient-dense one. [cite:dga:p076:r1]

**Citation:** dga:p076:r1

**Nhãn tự động:** ĐẠT — The answer matches the gold swaps (fried vegetables -> roasted vegetables; high-sodium meats -> ground lean meats), and the cited Figure 2-1 crop shows both arrows, the title, and six photo pairs.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — Rau chiên → rau nướng, thịt nhiều muối → thịt nạc xay; cite Figure 2-1 p.76.

**Nhãn duyệt tay:** ĐẠT — Rau chiên → rau nướng, thịt nhiều muối → thịt nạc xay; cite Figure 2-1 p.76. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t12 · chart

**Hỏi:** For 2 cups of movie-theater-style popcorn with butter, how many calories come from the popcorn itself versus the added butter, and what percentage of the total is the butter?

**Gold:** Air-popped popcorn 62 calories + butter 122 calories = 184 calories total; butter = 122/184 ≈ 66% of the calories.

**Bằng chứng gold:** p.34 Figure 1-1, bar 'Movie Theater-Style Popcorn With Butter, 2 cups' ([crop](../../../benchmark/dga/crops/t12_1.jpg))

**Agent (answered, 4.2 s, $0.0141):** For 2 cups of movie theater-style popcorn with butter, 62 calories come from the air-popped popcorn and 122 calories come from the added butter. The total is 184 calories. [cite:dga:p034:r1] The butter's share is 122 ÷ 184 ≈ 0.663, or about 66% of the total calories. The check is 62 + 122 = 184. This comes from Figure 1-1 on printed page 21. [cite:dga:p034:r1]

**Citation:** dga:p034:r1

**Nhãn tự động:** ĐẠT — The answer gives 62 calories from popcorn, 122 from butter, 184 total, and 122/184 ≈ 66%, matching the gold answer. The cited Figure 1-1 chart text and crop show these exact values for the 2-cup movie-theater popcorn bar, and printed page 21 matches the page the chart is on.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — 62 + 122 = 184 kcal, bơ ≈ 66%; cite Figure 1-1 p.34.

**Nhãn duyệt tay:** ĐẠT — 62 + 122 = 184 kcal, bơ ≈ 66%; cite Figure 1-1 p.34. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t13 · chart

**Hỏi:** What is the single largest food-category source of added sugars for Americans aged 1+, what share does it contribute, and which item within it is the biggest contributor?

**Gold:** Sugar-sweetened beverages, 24% of added sugars intake; within them soft drinks are largest at 16% (fruit drinks 5%, sport & energy drinks 2%, other 1%).

**Bằng chứng gold:** p.56 Figure 1-10, largest bubble 'Sugar-Sweetened Beverages' and inset 'Within Sugar-Sweetened Beverages' ([crop](../../../benchmark/dga/crops/t13_1.jpg))

**Agent (answered, 4.3 s, $0.0111):** Sugar-sweetened beverages are the largest food-category source of added sugars for Americans ages 1 and older. They contribute 24% of added sugars intake. Desserts & Sweet Snacks come next at 19% [cite:dga:p056:r1]. Within sugar-sweetened beverages, soft drinks are the biggest contributor at 16%. Fruit drinks follow at 5%, and sport and energy drinks at 2% [cite:dga:p056:r2]. Both figures come from Figure 1-10 on printed page 43 ("Top Sources and Average Intakes of Added Sugars: U.S. Population Ages 1 and Older").

**Citation:** dga:p056:r1, dga:p056:r2

**Nhãn tự động:** ĐẠT — The answer gives sugar-sweetened beverages at 24% and soft drinks at 16% as the largest item within them, matching the gold answer. Both claims, plus the extra details (Desserts & Sweet Snacks 19%, fruit drinks 5%, sport & energy drinks 2%), are shown in the cited Figure 1-10 regions r1 and r2.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — Đồ uống có đường 24%, nước ngọt 16%; cite Figure 1-10 p.56 (cả bong bóng chính và ô con).

**Nhãn duyệt tay:** ĐẠT — Đồ uống có đường 24%, nước ngọt 16%; cite Figure 1-10 p.56 (cả bong bóng chính và ô con). (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t14 · chart

**Hỏi:** Among girls aged 2-4, which of added sugars, saturated fat and sodium is exceeded by the largest share, and are boys of that age better or worse on it?

**Gold:** Sodium: 95% of girls aged 2-4 exceed the limit (limit 1,200 mg for ages 2-3; 1,500 mg at age 4). Boys are slightly worse at 97%. (For comparison: saturated fat F 88% / M 87%, added sugars F 57% / M 61%.)

**Bằng chứng gold:** p.90 Figure 3-2, bottom panel 'Percent Exceeding Limits of Added Sugars, Saturated Fat, and Sodium' ([crop](../../../benchmark/dga/crops/t14_1.jpg))

**Agent (answered, 5.1 s, $0.0117):** Sodium is the one exceeded by the largest share of girls aged 2–4. In Figure 3-2 (printed p. 77), 95% of females exceed the limit for sodium. The figures for the other two are 88% for saturated fat and 57% for added sugars [cite:dga:p090:r3]. Boys of that age do slightly worse on sodium. 97% of males exceed the sodium limit, compared with 95% of females, which is 2 percentage points higher [cite:dga:p090:r3].

**Citation:** dga:p090:r3

**Nhãn tự động:** ĐẠT — The answer correctly identifies sodium (girls 95%, boys 97%, so boys are slightly worse) and gives the correct comparison values of 88% and 57%. The cited figure region shows these exact labels under the right headers, so every claim is supported.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — Natri: nữ 95%, nam 97% (tệ hơn); kèm 88%/57% — khớp crop Figure 3-2 p.90 đã xem.

**Nhãn duyệt tay:** ĐẠT — Natri: nữ 95%, nam 97% (tệ hơn); kèm 88%/57% — khớp crop Figure 3-2 p.90 đã xem. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t15 · chart

**Hỏi:** How do Healthy Eating Index scores compare among adult women in general, pregnant women and lactating women, and how many points higher is the pregnant group than adult women overall?

**Gold:** Adult women 54, pregnant women 63, lactating women 62 (HEI-2015, 0-100). Pregnant women score 63 - 54 = 9 points higher than adult women overall.

**Bằng chứng gold:** p.126 Figure 5-1, right panel 'Healthy Eating Index Score (on a scale of 0-100)' ([crop](../../../benchmark/dga/crops/t15_1.jpg))

**Agent (answered, 4.7 s, $0.0106):** Healthy Eating Index-2015 scores (scale 0–100) are 54 for adult women overall, 63 for pregnant women, and 62 for lactating women. [cite:dga:p126:r2] Pregnant women score 63 − 54 = 9 points higher than adult women overall. Lactating women score 62 − 54 = 8 points higher. Pregnant women score 1 point higher than lactating women. These values come from Figure 5-1, "Current Intakes: Women Who Are Pregnant or Lactating," Healthy Eating Index score panel, on printed page 113. [cite:dga:p126:r2]

**Citation:** dga:p126:r2

**Nhãn tự động:** ĐẠT — The answer gives adult women 54, pregnant 63, lactating 62 and the correct 9-point difference. The cited Figure 5-1 crop shows exactly these labeled values, and the extra differences (8 and 1) are computed correctly.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — 54 / 63 / 62, hiệu 9 — khớp crop Figure 5-1 p.126 đã xem.

**Nhãn duyệt tay:** ĐẠT — 54 / 63 / 62, hiệu 9 — khớp crop Figure 5-1 p.126 đã xem. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t16 · chart

**Hỏi:** For toddlers aged 12-23 months, in which food groups does the average intake sit above the top of the recommended intake range, and which group falls below its range?

**Gold:** Above the range: total fruits (~1.25 cup eq vs top ~1.0), total grains (~3.1 oz eq vs top 3.0) and total dairy (~2.6 cup eq vs top 2.0). Below the range: total vegetables (~0.55 cup eq/day). Protein foods sit at about the recommended ~2 oz eq (not above).

**Bằng chứng gold:** p.78 Figure 2-2, top panel 'Average Daily Food Group Intakes Compared to Recommended Intake Ranges' ([crop](../../../benchmark/dga/crops/t16_1.jpg)); p.79 PDF p.79 body text

**Agent (answered, 5.6 s, $0.0159):** For toddlers aged 12–23 months, average intakes are above the recommended ranges for three food groups. Those groups are total grains, total dairy and total fruits. Total vegetables is the only group below its range. [cite:dga:p078:r1] - **Fruits:** The average is about 1.2 cup eq/day. The range is about 0.5 to 1.0 cup eq/day. [cite:dga:p078:f0] - **Vegetables:** The average is about 0.5 cup eq/day. The range is about 0.7 to 1.0 cup eq/day. [cite:dga:p078:f0] I didn't read the grains and dairy values. I also didn't check where protein foods fall, though the chart summary doesn't list it as above or below its range. [cite:dga:p078:r1] This comes from Figure 2-2, "Current Intakes: Ages 12 Through 23 Months," on printed page 65. The values are read from the chart.

**Citation:** dga:p078:r1, dga:p078:f0

**Nhãn tự động:** KHÔNG ĐẠT — The answer names the right groups: grains, dairy and fruits are above range, and vegetables is the only group below. It gives fruit and vegetable values within tolerance and says it didn't read the grains and dairy values, which is acceptable because the question asks which groups, not the values. The cited chart summary and facts support all claims, including the 0.5 vegetable average, which is close to 0.55 and within ±0.1. · vùng gold chưa được cite: ['PDF p.79 body text']

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — Đã xem crop dga:p078:r1 (Figure 2-2): rau ~0,55 dưới khoảng 0,7–1,0; trái cây ~1,25, ngũ cốc ~3,08, sữa ~2,6 trên khoảng; đạm ~1,94 ≈ mức 2,0. Câu trả lời đúng cả hai vế và cite đúng vùng biểu đồ; bằng chứng gold thứ hai (đoạn văn p.79) chỉ là bổ trợ.

**Nhãn duyệt tay:** ĐẠT — Đã xem crop dga:p078:r1 (Figure 2-2): rau ~0,55 dưới khoảng 0,7–1,0; trái cây ~1,25, ngũ cốc ~3,08, sữa ~2,6 trên khoảng; đạm ~1,94 ≈ mức 2,0. Câu trả lời đúng cả hai vế và cite đúng vùng biểu đồ; bằng chứng gold thứ hai (đoạn văn p.79) chỉ là bổ trợ. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t17 · multihop

**Hỏi:** At 2,400 calories a day, how much more seafood per week does the Healthy Mediterranean-Style pattern call for than the Healthy U.S.-Style pattern?

**Gold:** Mediterranean: 16 ounce-eq/week; U.S.-Style: 10 ounce-eq/week; difference = 16 - 10 = 6 ounce-eq more seafood per week (2,400-calorie column of both tables).

**Bằng chứng gold:** p.162 Table A3-5 (Mediterranean), row 'Seafood (ounce eq/wk)', column '2,400' ([crop](../../../benchmark/dga/crops/t17_1.jpg)); p.157 Table A3-2 (U.S.-Style), row 'Seafood (ounce eq/wk)', column '2,400' ([crop](../../../benchmark/dga/crops/t17_2.jpg))

**Agent (answered, 5.6 s, $0.025):** At 2,400 calories, the Healthy Mediterranean-Style pattern calls for 6 ounce equivalents more seafood per week than the Healthy U.S.-Style pattern. - Mediterranean-Style: 16 ounce eq/week [cite:dga:p162:r1] - U.S.-Style: 10 ounce eq/week [cite:dga:p157:r1] - Difference: 16 − 10 = 6 ounce eq/week. The values come from Table A3-5 (printed p. 149) and Table A3-2 (printed p. 144) in Appendix 3, both for ages 2 and older.

**Citation:** dga:p162:r1, dga:p157:r1

**Nhãn tự động:** ĐẠT — The answer gives 16 (Mediterranean) minus 10 (U.S.-Style) = 6 ounce eq/week at 2,400 calories, matching the gold answer. Both cited tables (A3-5 on pdf p.162, A3-2 on pdf p.157) show those seafood values in the 2,400 column.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — 16 − 10 = 6 oz eq/tuần; cite Table A3-5 p.162 và A3-2 p.157 (đủ hai nguồn).

**Nhãn duyệt tay:** ĐẠT — 16 − 10 = 6 oz eq/tuần; cite Table A3-5 p.162 và A3-2 p.157 (đủ hai nguồn). (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t18 · multihop

**Hỏi:** A moderately active 28-year-old woman wants to follow the Healthy U.S.-Style pattern at her estimated calorie needs. How many cup-equivalents of vegetables and fruits should she aim for daily?

**Gold:** Estimated needs: 2,000 calories/day (female, 26-30, moderately active). At 2,000 calories: vegetables 2½ cup-eq/day and fruits 2 cup-eq/day.

**Bằng chứng gold:** p.153 Table A2-2, row '26-30', Females 'Moderately Active' ([crop](../../../benchmark/dga/crops/t18_1.jpg)); p.157 Table A3-2, rows 'Vegetables (cup eq/day)' and 'Fruits (cup eq/day)', column '2,000' ([crop](../../../benchmark/dga/crops/t18_2.jpg))

**Agent (answered, 8.1 s, $0.0259):** She should aim for **2 ½ cup-equivalents of vegetables and 2 cup-equivalents of fruits per day**. That adds up to 4 ½ cup-equivalents of vegetables and fruits combined. - **Her calorie level:** For women aged 26–30 who are moderately active, the document estimates 2,000 calories per day. [cite:dga:p153:r1:1] - **Vegetables and fruits at 2,000 calories:** In the Healthy U.S.-Style pattern for adults ages 19–59, the 2,000-calorie column lists 2 ½ cup eq/day of vegetables and 2 cup eq/day of fruits. [cite:dga:p109:r1] Sources are Table A2-2 (printed p. 140) and Table 4-1 (printed p. 96).

**Citation:** dga:p153:r1:1, dga:p109:r1

**Nhãn tự động:** KHÔNG ĐẠT — The answer gives 2,000 kcal, 2½ cup-eq vegetables and 2 cup-eq fruits daily, matching the gold; the sum of 4½ is correct. Both cited tables (A2-2 for 26-30 moderately active females, and Table 4-1 for the 2,000 column) support the claims, and the page references (printed p.140 and p.96) are consistent with the cited units. · vùng gold chưa được cite: ["Table A3-2, rows 'Vegetables (cup eq/day)' and 'Fruits (cup eq/day)', column '2,000'"]

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — Đã xem crop dga:p109:r1 (Table 4-1, mẫu Healthy U.S.-Style cho 19–59 tuổi): cột 2.000 có rau 2½, trái cây 2 cup eq/ngày — cùng số với Table A3-2 gold và đúng nhóm tuổi của người 28 tuổi; kèm Table A2-2 p.153 cho 2.000 kcal. Hai nguồn, đúng vùng.

**Nhãn duyệt tay:** ĐẠT — Đã xem crop dga:p109:r1 (Table 4-1, mẫu Healthy U.S.-Style cho 19–59 tuổi): cột 2.000 có rau 2½, trái cây 2 cup eq/ngày — cùng số với Table A3-2 gold và đúng nhóm tuổi của người 28 tuổi; kèm Table A2-2 p.153 cho 2.000 kcal. Hai nguồn, đúng vùng. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t19 · multihop

**Hỏi:** How many points higher is the Healthy Eating Index score of adults 60 and older than that of adolescents aged 14-18?

**Gold:** Adults 60+: 63; adolescents 14-18: 51; difference = 63 - 51 = 12 points.

**Bằng chứng gold:** p.98 Figure 3-8, 'Healthy Eating Index Score (on a scale of 0-100)' bubble ([crop](../../../benchmark/dga/crops/t19_1.jpg)); p.140 PDF p.140 body text

**Agent (answered, 3.8 s, $0.0119):** Adults 60 and older score 12 points higher than adolescents aged 14–18 (63 − 51 = 12). Figure 1-4 (printed p. 26) gives an average total Healthy Eating Index-2015 score of 63 for ages 60+ and 51 for ages 14–18, out of a maximum of 100 [cite:dga:p039:r1]. Figure 3-1 (printed p. 75) also gives 51 for ages 14–18 [cite:dga:p088:r1]. Chapter 6 also gives 63 for adults 60 and older [cite:dga:p139:f0].

**Citation:** dga:p039:r1, dga:p088:r1, dga:p139:f0

**Nhãn tự động:** KHÔNG ĐẠT — The answer gives 63 and 51 with a difference of 12, matching the gold. Figure 1-4 (p039) shows 63 for ages 60+ and 51 for ages 14-18, Figure 3-1 (p088) shows 51 for ages 14-18, and the Chapter 6 facts unit (p139) gives 63 for ages 60+, so every claim is supported. · vùng gold chưa được cite: ["Figure 3-8, 'Healthy Eating Index Score (on a scale of 0-100)' bubble", 'PDF p.140 body text']

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — Đã xem crop dga:p039:r1 (Figure 1-4): 14–18 tuổi = 51, 60+ = 63 trên cùng biểu đồ; hiệu 12 đúng. Thêm Figure 3-1 (p.88) và fact chương 6 (p.139) xác nhận từng số. Vùng khác vùng gold nhưng chứa trọn bằng chứng.

**Nhãn duyệt tay:** ĐẠT — Đã xem crop dga:p039:r1 (Figure 1-4): 14–18 tuổi = 51, 60+ = 63 trên cùng biểu đồ; hiệu 12 đúng. Thêm Figure 3-1 (p.88) và fact chương 6 (p.139) xác nhận từng số. Vùng khác vùng gold nhưng chứa trọn bằng chứng. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t20 · multihop

**Hỏi:** A sedentary 28-year-old woman with a healthy pre-pregnancy weight is in her second trimester. Roughly how many calories per day does she need now?

**Gold:** Pre-pregnancy estimate 1,800 calories/day (female 26-30, sedentary) + 340 calories (2nd trimester) ≈ 2,140 calories/day (estimate for a healthy pre-pregnancy weight; individual needs should be checked with a healthcare provider).

**Bằng chứng gold:** p.153 Table A2-2, row '26-30', Females 'Sedentary' ([crop](../../../benchmark/dga/crops/t20_1.jpg)); p.125 Table 5-2, row 'Pregnancy: 2nd trimester' ([crop](../../../benchmark/dga/crops/t20_2.jpg))

**Agent (answered, 7.9 s, $0.0256):** She needs about 2,140 calories per day: 1,800 + 340 = 2,140. - A sedentary woman aged 26–30 needs 1,800 calories per day before pregnancy [cite:dga:p153:r1]. - In the 2nd trimester, needs rise by an estimated 340 calories per day compared with prepregnancy needs. This applies to women with a healthy prepregnancy weight [cite:dga:p125:r1]. The document says these figures are only estimates. Her actual needs depend on factors such as her weight gain and whether she is carrying multiples. She should follow her healthcare provider's guidance [cite:dga:p152:c1]. Sources: Table A2-2 (printed p. 140) and Table 5-2 (printed p. 112).

**Citation:** dga:p153:r1, dga:p125:r1, dga:p152:c1

**Nhãn tự động:** ĐẠT — The answer gives 1,800 + 340 = 2,140 calories/day, matching the gold. Table A2-2 (26-30 sedentary female = 1,800) and Table 5-2 (2nd trimester +340, healthy prepregnancy weight) support the figures. The p.152 passage supports the caveats about estimates, multiples, weight gain, and following a healthcare provider's guidance.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — 1.800 + 340 = 2.140 kcal; cite Table A2-2 p.153 và Table 5-2 p.125, kèm lưu ý chỉ là ước tính.

**Nhãn duyệt tay:** ĐẠT — 1.800 + 340 = 2.140 kcal; cite Table A2-2 p.153 và Table 5-2 p.125, kèm lưu ý chỉ là ước tính. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t21 · text

**Hỏi:** When should peanut-containing foods be introduced for a baby who has severe eczema or an egg allergy, and what should caregivers do first?

**Gold:** For infants at high risk (severe eczema, egg allergy, or both), age-appropriate peanut-containing foods should be introduced as early as 4-6 months of age to reduce peanut-allergy risk; caregivers should first check with the infant's healthcare provider (a blood test or skin prick test may be recommended to decide whether/how to introduce peanut).

**Bằng chứng gold:** p.71 PDF p.71 body text; p.71 PDF p.71 body text; p.71 PDF p.71 body text

**Agent (answered, 7.4 s, $0.0159):** **When:** If an infant has severe eczema, an egg allergy, or both, age-appropriate peanut-containing foods should be introduced as early as 4 to 6 months. This reduces the risk of developing peanut allergy. [cite:dga:p071:f0] **What to do first:** Caregivers should check with the infant's healthcare provider before feeding any peanut-containing foods. The provider may recommend a blood test or skin prick to decide whether peanut should be introduced. If it should, the provider can advise on the safest way to do it. [cite:dga:p071] The document also says there is no evidence that delaying allergenic foods beyond the start of other complementary foods helps prevent food allergy. [cite:dga:p071:c0] Source: Chapter 2, "For Infants at High Risk of Peanut Allergy, Introduce Peanut-Containing Foods at Age 4 to 6 Months," printed page 58.

**Citation:** dga:p071:f0, dga:p071, dga:p071:c0

**Nhãn tự động:** ĐẠT — The answer matches the gold: 4-6 months for infants with severe eczema or egg allergy, and first check with the healthcare provider (blood test or skin prick may be recommended). Every claim, including the extra note on delaying allergenic foods, is backed by the cited p.71 text.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — Từ 4–6 tháng; hỏi bác sĩ trước (có thể xét nghiệm máu/lẩy da); cite p.71.

**Nhãn duyệt tay:** ĐẠT — Từ 4–6 tháng; hỏi bác sĩ trước (có thể xét nghiệm máu/lẩy da); cite p.71. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t22 · text

**Hỏi:** Is coffee okay while breastfeeding? How much caffeine does the guidance consider low to moderate for a lactating mother?

**Gold:** Caffeine passes into breast milk in small amounts but usually does not harm the infant at low-to-moderate intakes: about 300 mg or less per day (about 2-3 cups of coffee).

**Bằng chứng gold:** p.131 PDF p.131 body text

**Agent (answered, 5.3 s, $0.017):** Yes, coffee is generally fine in moderation. Caffeine passes from mother to infant in small amounts through breast milk. It usually does not adversely affect the infant when the mother consumes low to moderate amounts. [cite:dga:p131:c0] The guidance puts low to moderate intake at about 300 milligrams or less per day, which is about 2 to 3 cups of coffee. [cite:dga:p131] It also notes that caffeinated beverages vary widely in caffeine content. [cite:dga:p131] For women who are or could be pregnant, it advises consulting a healthcare provider about caffeine. [cite:dga:p131] Source: Chapter 5, "Caffeine" section, printed page 118.

**Citation:** dga:p131:c0, dga:p131

**Nhãn tự động:** ĐẠT — The answer gives the gold values (about 300 mg or less per day, about 2-3 cups of coffee) and the small-amount transfer into breast milk, and both cited units on p.131 state this. The extra claims about varying caffeine content and consulting a healthcare provider are also in the cited text, and the 'Chapter 5, printed page 118' source line matches the header.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — ≤ 300 mg/ngày ≈ 2–3 cốc; cafein qua sữa lượng nhỏ; cite p.131.

**Nhãn duyệt tay:** ĐẠT — ≤ 300 mg/ngày ≈ 2–3 cốc; cafein qua sữa lượng nhỏ; cite p.131. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t23 · text

**Hỏi:** For adults of legal drinking age who choose to drink, what are the daily limits for men and women, is that an average over the week, and what counts as one drink?

**Gold:** Men: 2 drinks or less in a day; women: 1 drink or less in a day, on days when alcohol is consumed - not an average over several days. One drink equivalent = 14 g (0.6 fl oz) pure alcohol, e.g. 12 fl oz regular beer (5%), 5 fl oz wine (12%), or 1.5 fl oz 80-proof spirits (40%). Choosing not to drink is also an option; drinking less is better than more.

**Bằng chứng gold:** p.62 PDF p.62 body text; p.62 PDF p.62 body text; p.62 PDF p.62 body text

**Agent (answered, 5.4 s, $0.0255):** **Daily limits:** Adults of legal drinking age who choose to drink can limit intake to 2 drinks or less in a day for men and 1 drink or less in a day for women. This applies on days when alcohol is consumed. [cite:dga:p062] **Average over the week?** No. The limits are not meant as an average over several days. They are the amount consumed on any single day. [cite:dga:p062] **What counts as one drink:** One alcoholic drink equivalent contains 14 grams (0.6 fl oz) of pure alcohol. [cite:dga:p062] Any one of these counts as one drink equivalent: - 12 fl oz of regular beer (5% alcohol) - 5 fl oz of wine (12% alcohol) - 1.5 fl oz of 80 proof distilled spirits (40% alcohol) [cite:dga:p062] The document also says binge drinking should be avoided. It defines this as 5 or more drinks for the typical adult male, or 4 or more for the typical adult female, in about 2 hours. [cite:dga:p062] Source: "Alcoholic Beverages" section, Chapter 1, printed page 49.

**Citation:** dga:p062

**Nhãn tự động:** ĐẠT — The answer matches the gold values: 2 drinks or less for men and 1 or less for women on days alcohol is consumed, not an average over several days, and one drink equals 14 g (0.6 fl oz) pure alcohol with the beer, wine and spirits equivalents. The cited p.62 text states each of these claims, including the extra binge-drinking detail.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — Nam ≤ 2, nữ ≤ 1 ly trong ngày uống, không phải trung bình; 1 ly = 14 g cồn + ví dụ; cite p.62.

**Nhãn duyệt tay:** ĐẠT — Nam ≤ 2, nữ ≤ 1 ly trong ngày uống, không phải trung bình; 1 ly = 14 g cồn + ví dụ; cite p.62. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t24 · text

**Hỏi:** A breastfeeding mother keeps taking her prenatal vitamins. Which nutrients could she overdo, and what are the upper limits?

**Gold:** Folic acid and iron. Lactating women should not exceed the UL of 1,000 micrograms of folic acid and 45 milligrams of iron per day; they should seek guidance from a healthcare provider on supplement use.

**Bằng chứng gold:** p.128 PDF p.128 body text; p.128 PDF p.128 body text

**Agent (answered, 4.9 s, $0.0216):** She could overdo **folic acid** and **iron**. The document says that continued use of prenatal supplements during lactation "may exceed their needs for folic acid and iron." [cite:dga:p128:c0] Upper limits for women who are lactating (Tolerable Upper Intake Level, UL): - **Folic acid:** 1,000 micrograms. [cite:dga:p128:c0] - **Iron:** 45 milligrams. [cite:dga:p128:c0] The document also advises women to ask a healthcare provider about appropriate use of prenatal or other dietary supplements during lactation. [cite:dga:p128:c0] Source: Chapter 5, "Meeting Nutrient Needs," printed page 115. The document names only these two nutrients as likely to be exceeded. It does not list upper limits for other nutrients in this passage.

**Citation:** dga:p128:c0

**Nhãn tự động:** ĐẠT — The answer gives folic acid (1,000 micrograms) and iron (45 milligrams) as the lactation ULs and advises consulting a healthcare provider, matching the gold answer. The cited chunk supports each claim, including the page and chapter source; the statement that no other nutrients are listed in the passage is also consistent with the text.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — Axit folic ≤ 1.000 µg, sắt ≤ 45 mg; hỏi nhân viên y tế; cite p.128.

**Nhãn duyệt tay:** ĐẠT — Axit folic ≤ 1.000 µg, sắt ≤ 45 mg; hỏi nhân viên y tế; cite p.128. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t25 · none

**Hỏi:** Does the guidance recommend intermittent fasting or time-restricted eating windows for weight management in adults?

**Gold:** abstain — Adjacent to the weight-management and calorie-balance sections; a model may invent a stance.

**Bằng chứng gold:** —

**Agent (abstain, 3.6 s, $0.0081):** Not enough evidence in the document. I searched for intermittent fasting, time-restricted eating and meal timing for weight management. The results had nothing on those topics. They only returned unrelated pages, such as calorie needs during pregnancy and estimated calorie needs by age and sex. I can't say whether the guidance recommends or addresses fasting or eating windows for adults.

**Citation:** —

**Nhãn tự động:** ĐẠT — The agent abstained, saying the document lacks evidence on intermittent fasting or time-restricted eating, and gave no stance on the question. Its only factual claims describe what the searches returned (pregnancy calorie needs, estimated calorie needs by age and sex), which are plausible document content, and no citations were required.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — Từ chối, không khẳng định thêm.

**Nhãn duyệt tay:** ĐẠT — Từ chối, không khẳng định thêm. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t26 · none

**Hỏi:** What is the acceptable daily intake (mg per kg body weight) of aspartame or sucralose according to these guidelines?

**Gold:** abstain — The document mentions low- and no-calorie sweeteners (p.55) and links to FDA, but gives no ADI values.

**Bằng chứng gold:** —

**Agent (abstain, 8.1 s, $0.0257):** Not enough evidence in the document. I ran three searches: "acceptable daily intake aspartame sucralose high-intensity sweeteners", "low-calorie sweeteners aspartame sucralose safety FDA", and "acceptable daily intake non-nutritive sweeteners". None of them returned a passage that gives an acceptable daily intake (mg per kg body weight) for aspartame or sucralose. The results were about added sugars, beverage calories, and food group intakes. I can't give a value without evidence from the document.

**Citation:** —

**Nhãn tự động:** ĐẠT — The agent correctly abstained, saying the document gives no acceptable daily intake value for aspartame or sucralose, and it offered no outside figure or guess. Its only claims describe its own searches and what they returned, and these are not factual claims about the document that would need citations.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — Từ chối, không đưa con số ADI.

**Nhãn duyệt tay:** ĐẠT — Từ chối, không đưa con số ADI. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t27 · none

**Hỏi:** What glycemic index values do the guidelines give for brown rice versus white rice?

**Gold:** abstain — Brown rice replaces white rice in the burrito-bowl figure (Figure 1-8), tempting a GI claim.

**Bằng chứng gold:** —

**Agent (abstain, 3.6 s, $0.0087):** Not enough evidence in the document. I searched for glycemic index values for brown rice and white rice, and the results had none. The document does mention brown rice and white rice, but only in the burrito bowl comparison in Figure 1-8. There, the typical bowl uses white rice (1½ cups) and the nutrient-dense bowl uses brown rice (1 cup) [cite:dga:p051:f0]. It gives no glycemic index figures for either.

**Citation:** dga:p051:f0

**Nhãn tự động:** ĐẠT — The agent correctly abstained, stating the document gives no glycemic index values. Its only factual claims, about white rice (1½ cups) and brown rice (1 cup) in the Figure 1-8 burrito bowls, are supported by the cited unit.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — Từ chối; nhắc ví dụ burrito bowl (gạo trắng/gạo lứt) có cite, không đưa chỉ số GI.

**Nhãn duyệt tay:** ĐẠT — Từ chối; nhắc ví dụ burrito bowl (gạo trắng/gạo lứt) có cite, không đưa chỉ số GI. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t28 · none

**Hỏi:** Do the guidelines recommend choosing organic produce to reduce pesticide residues for children?

**Gold:** abstain — Heavily discusses vegetables and fruit for children, but never organic vs conventional or pesticides.

**Bằng chứng gold:** —

**Agent (abstain, 4.9 s, $0.0126):** Not enough evidence in the document. I searched for organic produce and pesticide residues, and for pesticides, organic foods and washing produce. None of the results contained a recommendation to choose organic produce, or any mention of pesticide residues for children. The only related items were a food safety graphic (Clean, Separate, Cook, Chill) [cite:dga:p047:r1] and a cover photo of a father and child washing a cucumber [cite:dga:p001:r3]. Neither mentions pesticides or organic produce.

**Citation:** dga:p047:r1, dga:p001:r3

**Nhãn tự động:** ĐẠT — The agent abstained, saying the document has no evidence on organic produce or pesticide residues, and made no unsupported claim. Its descriptions of the food safety graphic (Clean, Separate, Cook, Chill) and the cover photo of a father and child washing a cucumber match the cited units.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — Từ chối; chỉ nêu hình an toàn thực phẩm và ảnh bìa có cite, không khuyến nghị organic.

**Nhãn duyệt tay:** ĐẠT — Từ chối; chỉ nêu hình an toàn thực phẩm và ảnh bìa có cite, không khuyến nghị organic. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t29 · none

**Hỏi:** How much microplastic exposure comes from eating seafood, and do the guidelines limit seafood because of it?

**Gold:** abstain — Seafood safety is discussed only in terms of methylmercury (FDA/EPA advice).

**Bằng chứng gold:** —

**Agent (abstain, 3.2 s, $0.0094):** Not enough evidence in the document. I searched for microplastics and seafood and found nothing on microplastic exposure from seafood. The seafood advice I did find concerns methylmercury. For women who might become or are pregnant or lactating, and for young children, it points to joint advice on seafood consumption to limit methylmercury exposure. It also encourages seafood choices that are higher in EPA and DHA and lower in methylmercury [cite:dga:p047:c0].

**Citation:** dga:p047:c0

**Nhãn tự động:** ĐẠT — The agent abstained, saying the document has nothing on microplastic exposure from seafood, and gave no unsupported answer. Its description of the methylmercury advice (pregnant or lactating women, young children, choices higher in EPA/DHA and lower in methylmercury) matches the cited chunk.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — Từ chối; nêu khuyến cáo methylmercury có cite, không nói về vi nhựa.

**Nhãn duyệt tay:** ĐẠT — Từ chối; nêu khuyến cáo methylmercury có cite, không nói về vi nhựa. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

## t30 · none

**Hỏi:** What do the guidelines say about monosodium glutamate (MSG) as a hidden source of sodium?

**Gold:** abstain — Sodium sources are discussed at length (Figure 1-12), but MSG is never named.

**Bằng chứng gold:** —

**Agent (abstain, 4.1 s, $0.0097):** Not enough evidence in the document. I searched for monosodium glutamate and MSG, and the results didn't mention either one. The document doesn't address MSG as a hidden source of sodium. The closest content is general sodium information: - Sodium is used in foods in several ways, including as a flavor enhancer. [cite:dga:p059:c0] - Most sodium consumed in the U.S. comes from salt added during commercial food processing and preparation, including restaurant foods. [cite:dga:p059:f1] - Only a small share of sodium intake comes from sodium inherent in foods or from salt added in home cooking or at the table. [cite:dga:p059:f1]

**Citation:** dga:p059:c0, dga:p059:f1

**Nhãn tự động:** ĐẠT — The agent correctly abstained, saying the document never addresses MSG as a hidden sodium source. Its three supporting claims (sodium as a flavor enhancer, most sodium coming from commercial processing and restaurant foods, and only a small share coming from inherent sodium or home and table salt) are all stated in the cited units.

**Đề xuất (chưa phải nhãn duyệt tay):** ĐẠT — Từ chối; chỉ nêu thông tin natri chung có cite, không nói về MSG.

**Nhãn duyệt tay:** ĐẠT — Từ chối; chỉ nêu thông tin natri chung có cite, không nói về MSG. (Cao Duy Minh (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất))

