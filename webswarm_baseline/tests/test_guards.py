"""Unit tests for the deterministic reliability guards (no model, no network).

Strings marked REAL are copied from the baseline benchmark runs of 2026-10-11 (saved under
examples/ and experiments/results/): they are the outputs that went wrong.
"""
import pytest

from webswarm_baseline import guards as g

# ---- REAL: D1, baseline. The DEEP manager sent D1_CLAIM to the verifier, which returned "survived".
D1_STEP1 = ("Amkor is the primary supplier of advanced packaging technology for NVIDIA's latest AI accelerator "
            "chips, evidenced by a $1.5 billion deal signed on October 23 to expand US production [S1]. The "
            "partnership involves jointly developing packaging and testing technology to combine different chip "
            "types into single packages [S1].")
D1_STEP2 = ("The provided findings do not state a specific maximum advanced-packaging capacity figure for Amkor's "
            "NVIDIA chips, nor do they include a projected annual growth rate. They only confirm a $1.5 billion "
            "multi-year agreement [S2] to expand U.S. capacity with NVIDIA prepayments [S2], aiming to strengthen "
            "domestic manufacturing capabilities [S2].")
D1_CLAIM = ("The provided findings do not contain specific advanced-packaging capacity figures (units per year) or "
            "a projected annual growth rate for Amkor's $1.5 billion deal with NVIDIA. The text confirms the deal "
            "value, location (Arizona), and timing (late July 2026) but lacks quantitative production data or "
            "growth projections.")
D1_VERIFIER_ANSWER = ("The findings confirm the deal value ($1.5 billion) [S6], location (Arizona) [S7], and timing "
                      "(late July 2026) [S4]. However, none of the sources provide specific advanced-packaging "
                      "capacity figures in units per year or projected annual growth rates. The text lacks these "
                      "quantitative production data points as claimed.")

# ---- REAL: W1, baseline. NVIDIA's CFO commentary as extracted from the PDF (one table cell per line).
NVDA_TABLE = """Fiscal 2025 Summary
GAAP
($ in millions, except earnings
per share)
FY25
FY24
Y/Y
Revenue
$130,497
$60,922
Up 114%
Gross margin
75.0%
72.7%
Up 2.3 pts
Operating income
$81,453
$32,972
Up 147%
Non-GAAP
($ in millions, except earnings
per share)
FY25
FY24
Y/Y
Revenue
$130,497
$60,922
Up 114%
Gross margin
75.5%
73.8%
Up 1.7 pts
Operating income
$86,789
$37,134
Up 134%"""
NVDA_QUOTE = "FY25 FY24 Y/Y Revenue $130,497 $60,922 Up 114% Gross margin 75.5% 73.8% Up 1.7 pts"
NVDA_F3 = ("For fiscal year 2025, NVIDIA's GAAP gross margin was 75.5%, representing an increase of 1.7 percentage "
           "points compared to the prior year.")      # the finding that mislabelled the non-GAAP figure
NVDA_F5 = "NVIDIA's non-GAAP gross margin for fiscal year 2025 was 75.5%, up 1.7 percentage points from the prior year."

AMD_PAGE = ("AMD (NASDAQ:AMD) today announced financial results for the fourth quarter and full year of 2024. Fourth "
            "quarter revenue was a record $7.7 billion, gross margin was 51%, operating income was $871 million, net "
            "income was $482 million and diluted earnings per share was $0.29. On a non-GAAP(*) basis, gross margin "
            "was 54%, operating income was a record $2.0 billion.\n"
            "For the full year 2024, AMD reported record revenue of $25.8 billion, gross margin of 49%, operating "
            "income of $1.9 billion, net income of $1.6 billion, and diluted earnings per share of $1.00. On a "
            "non-GAAP(*) basis, gross margin was a record 53%, operating income was $6.1 billion.")
AMD_QUOTE = "For the full year 2024, AMD reported record revenue of $25.8 billion, gross margin of 49%..."
AMD_F1 = ("AMD's GAAP gross margin for the full year 2024 was 49%, which represents an increase of 1 percentage "
          "point compared to the previous quarter.")

# ---- REAL: W2, baseline. Three correct figures, then a wrong ranking.
W2_QUESTION = "Compare the total annual revenue of Microsoft (fiscal year 2024), Alphabet (2024) and Amazon (2024)."
W2_CHILDREN = [
    ("Microsoft's total annual revenue for fiscal year 2024",
     "Microsoft's total annual revenue for fiscal year 2024 was $245.12 billion [S1].", False),
    ("Alphabet's total annual revenue for calendar year 2024",
     "Alphabet's total annual revenue for calendar year 2024 was $350.018 billion [S2], representing a 13.87% "
     "increase from the previous year [S2]. This figure is also described as approximately $350 billion following "
     "a 14% climb in 2024 [S3].", False),
    ("Amazon's total annual revenue for calendar year 2024",
     "Amazon's total annual revenue for calendar year 2024 was $638 billion [S5].", False)]
W2_ANSWER = ("Microsoft reported total annual revenue of $245.12 billion for fiscal year 2024 [S1]. Alphabet generated "
             "approximately $350.018 billion (or roughly $350 billion) in calendar year 2024, reflecting a 13.87% to "
             "14% increase from the prior year [S2][S3]. Amazon's total annual revenue for calendar year 2024 was "
             "$638 billion [S5].\n\nBased on these figures, Alphabet generated the highest revenue at approximately "
             "$350 billion, followed by Amazon at $638 billion. Microsoft recorded the lowest revenue among the three "
             "companies at roughly $245 billion.")

W1_QUESTION = "Compare the gross margins of NVIDIA (fiscal year 2025), AMD (fiscal year 2024) and Intel (fiscal year 2024)."
W1_CHILDREN = [
    ("NVIDIA gross margin performance for fiscal year 2025",
     "NVIDIA's GAAP gross margin for fiscal year 2025 was 75.5%, an increase of 1.7 percentage points from the prior "
     "year [S2]. The non-GAAP gross margin for the same period also reached 75.5% [S2]. In the fourth quarter of "
     "fiscal year 2025, GAAP gross margin stood at 73.0%, which was 1.6 percentage points lower than the previous "
     "quarter [S2].", False),
    ("AMD gross margin performance for fiscal year 2024",
     "AMD's GAAP gross margin for fiscal year 2024 was 49% [S1]. This represented a 1 percentage point increase "
     "compared to the previous quarter and a 4 percentage point year-over-year increase from the fourth quarter of "
     "2023, which stood at 51% [S1].", False),
    ("Determine AMD's GAAP gross margin for Q3 and Q4 of fiscal year 2024.",
     "AMD's GAAP gross margin for Q3 of fiscal year 2024 was 50% [S6], and for Q4 of the same fiscal year it was "
     "51% [S5].", True),
    ("Retrieve Intel's GAAP gross margin for fiscal year 2024.",
     "The provided findings do not state the specific GAAP gross margin percentage for Intel's fiscal year 2024. "
     "They only confirm that the margin was negatively impacted by lower revenue [S4].", True)]


# =================================================================================================
# statements about missing information
# =================================================================================================

@pytest.mark.parametrize("text", [
    D1_CLAIM,
    "The provided findings do not specify the magnitude of Amkor's advanced-packaging capacity gap for NVIDIA in "
    "wafers per month, nor do they state the projected annual growth rate of the new Arizona facility.",   # REAL
    "Intel's specific GAAP gross margin percentage for fiscal year 2024 could not be established from the provided results.",
    "No exact numerical figure was reported.",
    "The research failed to retrieve the specific GAAP gross margin percentage for Intel for fiscal year 2024.",
    "Apple's annual Services revenue for fiscal 2024 was not found.",
    "The company has not disclosed capacity figures.",
    "None of the sources provide projected annual growth rates.",
    "There is no evidence that TSMC plans to double capacity.",
    "Capacity growth remains unclear.",
])
def test_statements_about_missing_information_are_recognised(text):
    assert g.is_absence_statement(text)
    assert g.verifiable_part(text) == "" and g.is_non_answer(text)


@pytest.mark.parametrize("text", [
    "TSMC plans to double CoWoS capacity in 2025.",
    "Intel does not manufacture the processors Apple designs for the iPhone.",       # a negative fact is checkable
    "AMD holds an estimated 6 to 8 percent share of the AI accelerator market.",     # REAL (M1 verifier claim)
    '"Samsung" belongs in the answer to: Which companies manufacture high-bandwidth memory (HBM) chips used in AI accelerators?',
    "Borealis Semiconductor will double advanced packaging capacity by the end of next year.",
    "Amkor has no advanced packaging plants in Taiwan.",
])
def test_ordinary_claims_including_negative_facts_stay_verifiable(text):
    assert not g.is_absence_statement(text)
    assert g.verifiable_part(text)


def test_verifiable_part_keeps_the_positive_claim_and_drops_citations_and_meta_remarks():
    assert g.verifiable_part(D1_STEP1).startswith("Amkor is the primary supplier of advanced packaging technology")
    assert "[S1]" not in g.verifiable_part(D1_STEP1)
    assert g.verifiable_part(D1_STEP2) == ""          # "They only confirm ..." is a remark about the findings
    assert g.verifiable_part(D1_VERIFIER_ANSWER) == ""
    mixed = "Amkor is the primary packaging partner for these chips, but its capacity figures were not disclosed."
    assert g.verifiable_part(mixed) == "Amkor is the primary packaging partner for these chips."


def test_checked_verdict_never_lets_a_missing_information_claim_survive():
    assert g.checked_verdict(D1_CLAIM, "survived", D1_VERIFIER_ANSWER, cited=True)[0] == "unverifiable"   # REAL case
    assert g.checked_verdict("TSMC plans to double CoWoS capacity in 2025.", "survived",
                             "TSMC said it will double CoWoS capacity [S3].", cited=True) == ("survived", "")
    assert g.checked_verdict("TSMC plans to double CoWoS capacity in 2025.", "survived",
                             "TSMC said it will double CoWoS capacity.", cited=False)[0] == "unverifiable"
    assert g.checked_verdict("TSMC plans to double CoWoS capacity in 2025.", "survived",
                             "None of the sources provide capacity figures [S3].", cited=True)[0] == "unverifiable"
    assert g.checked_verdict("TSMC plans to double CoWoS capacity in 2025.", "refuted",
                             "TSMC guided to 30% growth, not a doubling [S2].", cited=True) == ("refuted", "")
    assert g.checked_verdict(D1_CLAIM, "unverifiable", "", cited=False) == ("unverifiable", "")


# =================================================================================================
# quantities
# =================================================================================================

def test_quantities_are_parsed_with_kind_and_scale():
    qs = {q.raw: q for q in g.quantities("Revenue was $245.12 billion [S1], up 16%; margin rose 1.7 percentage "
                                         "points to 75.5% on $130,497 in FY25 and $575B in 2024.")}
    assert qs["$245.12 billion"].kind == "amount" and qs["$245.12 billion"].value == pytest.approx(245.12e9)
    assert qs["16%"].kind == "percent" and qs["1.7 percentage points"].kind == "points"
    assert qs["$130,497"].kind == "amount" and qs["$130,497"].grouped
    assert qs["$575B"].value == pytest.approx(575e9)
    assert qs["2024"].kind == "plain"
    assert "25" not in {q.raw for q in qs.values()} and "1" not in {q.raw for q in qs.values()}   # FY25, [S1]


# =================================================================================================
# claim checks (W1)
# =================================================================================================

def test_w1_gaap_label_on_the_non_gaap_figure_is_rejected():
    """REAL: the baseline stored 'NVIDIA's GAAP gross margin was 75.5%'. The quoted row sits under the
    'Non-GAAP' heading of the table; GAAP was 75.0%."""
    assert g.basis_evidence(NVDA_QUOTE, NVDA_TABLE) == ({"non-gaap"}, "heading")
    chk = g.check_claim(NVDA_F3, NVDA_QUOTE, NVDA_TABLE)
    assert not chk.ok and "non-gaap" in chk.reason
    ok = g.check_claim(NVDA_F5, NVDA_QUOTE, NVDA_TABLE)
    assert ok.ok and ok.basis == "non-gaap" and ok.claim == NVDA_F5
    gaap_quote = "FY25 FY24 Y/Y Revenue $130,497 $60,922 Up 114% Gross margin 75.0% 72.7% Up 2.3 pts"
    good = g.check_claim("NVIDIA's GAAP gross margin for fiscal year 2025 was 75.0%.", gaap_quote, NVDA_TABLE)
    assert good.ok and good.basis == "gaap"


def test_unlabelled_figure_followed_by_a_non_gaap_sentence_is_gaap_by_contrast():
    assert g.basis_evidence(AMD_QUOTE, AMD_PAGE) == ({"gaap"}, "contrast")
    wrong = g.check_claim("AMD's non-GAAP gross margin for the full year 2024 was 49%.", AMD_QUOTE, AMD_PAGE)
    assert not wrong.ok


def test_w1_clause_with_a_figure_that_is_not_in_the_quote_is_dropped():
    """REAL: the claim attached a quarter-on-quarter change to the full-year margin."""
    chk = g.check_claim(AMD_F1, AMD_QUOTE, AMD_PAGE)
    assert chk.ok and chk.claim == "AMD's GAAP gross margin for the full year 2024 was 49%."
    assert "1 percentage point" in chk.reason and chk.basis == "gaap"


def test_invented_figure_in_the_main_clause_rejects_the_finding():
    """The A2 pattern: a real sentence quoted, a figure that is not in it claimed."""
    chk = g.check_claim("Apple's Services revenue was $23.1 billion in the fourth quarter.",
                        "Services revenue reached an all-time record during the quarter", "x")
    assert not chk.ok and "$23.1 billion" in chk.reason


def test_rounding_and_change_of_scale_are_not_treated_as_unsupported():
    table = "Revenue $130,497 $60,922 Up 114%"
    assert g.check_claim("NVIDIA's revenue was $130.5 billion in fiscal 2025, up 114%.", table, table).ok
    assert g.check_claim("Alphabet's revenue reached about $350 billion in 2024.",
                         "Alphabet annual revenue for 2024 was $350.018B, a 13.87% increase from 2023.", "").ok
    assert not g.check_claim("NVIDIA's revenue was $131.5 billion in fiscal 2025.", table, table).ok
    assert g.check_claim("Fiscal year 2024 ended on December 28, 2024.", "full-year 2024 financial results", "").ok


def test_a_basis_label_the_passage_does_not_show_is_removed_not_trusted():
    text = "Gross margin was 61.5% in the quarter, the company said in its release."
    chk = g.check_claim("Acme's GAAP gross margin was 61.5%.", "Gross margin was 61.5% in the quarter", text)
    assert chk.ok and chk.basis == "" and "GAAP gross" not in chk.claim
    assert chk.claim.startswith("Acme's gross margin was 61.5%") and "not shown" in chk.claim


# =================================================================================================
# comparisons (W2, W1)
# =================================================================================================

def test_w2_figures_are_lined_up_and_sorted_by_code():
    cmp = g.build_comparison(W2_QUESTION, W2_CHILDREN)
    assert cmp.kind == "amount" and [r.entity for r in cmp.ranked()] == ["Amazon", "Alphabet", "Microsoft"]
    assert cmp.order_text() == "Amazon ($638 billion) > Alphabet ($350.018 billion) > Microsoft ($245.12 billion)"
    block = cmp.prompt_block()
    assert "1. Amazon: $638 billion" in block and "3. Microsoft: $245.12 billion" in block and not cmp.warnings


def test_w2_wrong_ranking_is_caught_with_and_without_the_lined_up_figures():
    cmp = g.build_comparison(W2_QUESTION, W2_CHILDREN)
    with_table = g.ordering_issues(W2_ANSWER, cmp.ranking(), cmp.metric)
    assert {i["check"] for i in with_table} == {"superlative", "ranking"}
    assert "Alphabet is called the highest, but by the figures it is Amazon" in [i["detail"] for i in with_table]
    alone = g.ordering_issues(W2_ANSWER)                 # what the v2 grader sees: just the answer text
    assert [i["check"] for i in alone] == ["superlative"] and "$638 billion" in alone[0]["detail"]
    note = g.correction_note(with_table, cmp)
    assert note.startswith("Correction (computed from the figures, not written by the model)")
    assert "Amazon ($638 billion) > Alphabet ($350.018 billion) > Microsoft ($245.12 billion)" in note


def test_a_correct_ranking_raises_nothing():
    cmp = g.build_comparison(W2_QUESTION, W2_CHILDREN)
    right = ("Amazon generated the highest revenue at $638 billion, followed by Alphabet at $350 billion. Microsoft "
             "recorded the lowest revenue of the three at $245 billion, less than Alphabet's $350 billion.")
    assert g.ordering_issues(right, cmp.ranking(), cmp.metric) == []


@pytest.mark.parametrize("sentence", [
    # REAL answers from other arms that an earlier version of the checks flagged wrongly
    "NVIDIA achieved the highest gross margins among the three companies, with a GAAP margin of 75.0% and a "
    "Non-GAAP margin of 75.5% for fiscal year 2025 [S3].",
    "AMD reported a GAAP gross margin of 49% for fiscal year 2024, though its non-GAAP margin reached a record 53% "
    "[S2]; this full-year figure is lower than the 51% recorded in Q4 alone [S2].",
    "AMD had the lowest margin of the two at 49%, up from 46% a year earlier, while NVIDIA reported 75.5%.",
    "Alphabet reported $350 billion and Amazon more than $600 billion.",
    "Intel faced the largest excess capacity charges of the three companies.",
])
def test_sentences_that_are_not_wrong_rankings_are_left_alone(sentence):
    # the ranking holds only entities a figure was found for (here Intel's was not), as the engine builds it
    ranking = [(["NVIDIA"], 75.5), (["AMD"], 49.0)]
    assert g.ordering_issues(sentence, ranking, ["gross", "margi"]) == []
    assert g.ordering_issues(sentence) == []


def test_pairwise_comparative_the_wrong_way_round_is_caught():
    assert g.ordering_issues("Microsoft's $245 billion is higher than Alphabet's $350 billion.")[0]["check"] == "comparative"
    assert g.ordering_issues("Microsoft's $245 billion is lower than Alphabet's $350 billion.") == []


def test_w1_headline_figures_skip_quarters_follow_ups_and_missing_entities():
    cmp = g.build_comparison(W1_QUESTION, W1_CHILDREN)
    rows = {r.entity: r for r in cmp.rows}
    assert rows["NVIDIA"].raw == "75.5%" and not rows["NVIDIA"].ambiguous     # the 73.0% is a quarter
    assert rows["AMD"].raw == "49%" and not rows["AMD"].ambiguous             # not the follow-up's Q3 50%
    assert rows["Intel"].value is None
    assert "No figure was found for: Intel" in cmp.prompt_block()


def test_mixed_accounting_bases_and_periods_are_flagged():
    q = "Compare the gross margins of Acme and Borealis for fiscal year 2024."
    cmp = g.build_comparison(q, [
        ("Acme gross margin for fiscal year 2024", "Acme's GAAP gross margin for fiscal year 2024 was 49% [S1].", False),
        ("Borealis gross margin for fiscal year 2024", "Borealis reported a non-GAAP gross margin of 53% for fiscal year 2024 [S2].", False)])
    assert len(cmp.warnings) == 1 and "different accounting bases" in cmp.warnings[0]
    assert "Caution:" in cmp.prompt_block()
    cmp = g.build_comparison("Compare the revenue of Acme and Borealis.", [
        ("Acme revenue", "Acme's revenue was $4.2 billion in the fourth quarter [S1].", False),
        ("Borealis revenue", "Borealis reported full-year revenue of $9.1 billion [S2].", False)])
    assert len(cmp.warnings) == 1 and "different periods" in cmp.warnings[0]


def test_no_comparison_is_built_for_questions_that_are_not_comparisons():
    assert g.build_comparison("What are the main factors that could affect NVIDIA's data-center revenue growth?",
                              [("NVIDIA pricing", "Prices fell 10% [S1].", False)]) is None
    assert g.build_comparison("Compare Acme and Borealis.", W2_CHILDREN) is None      # no metric named


def test_basis_label_that_contradicts_the_cited_passage_is_reported():
    findings = [{"source_id": "S2", "claim": NVDA_F5, "quote": NVDA_QUOTE, "basis": "non-gaap"}]
    bad = g.basis_conflicts("NVIDIA's GAAP gross margin for fiscal year 2025 was 75.5% [S2].", findings, {"S2"})
    assert len(bad) == 1 and bad[0]["said"] == "gaap" and bad[0]["passage_shows"] == "non-gaap"
    assert g.basis_conflicts("NVIDIA's non-GAAP gross margin for fiscal year 2025 was 75.5% [S2].", findings, {"S2"}) == []
    audit = g.consistency_audit(W2_ANSWER, [], set())
    assert not audit["clean"] and len(audit["ordering_issues"]) == 1


# =================================================================================================
# refinements made after replaying the checks over the 1,087 findings of the recorded runs
# =================================================================================================

def test_table_cells_glued_together_by_text_extraction_are_still_read():
    """REAL: 'Gross profit$17.34B32.7%'. The first version did not see 32.7% and would have rejected
    the only finding that carried Intel's gross margin."""
    assert [q.raw for q in g.quantities("Gross profit$17.34B32.7%")] == ["$17.34B", "32.7%"]
    chk = g.check_claim("Intel's gross margin for fiscal year 2024 was 32.7%, calculated from a gross profit of "
                        "$17.34 billion.", "Gross profit$17.34B32.7%", "Revenue$53.10B100.0%\nGross profit$17.34B32.7%")
    assert chk.ok and "32.7%" in chk.claim


def test_a_claim_more_precise_than_its_quote_is_still_backed_by_it():
    """REAL (A1): the claim said $115.186 billion, the quote $115.2 billion."""
    quote = "Data Center revenue for fiscal 2025 was $115.2 billion, up 142% from a year ago."
    claim = ("NVIDIA's Data Center revenue for fiscal year 2025 was $115.186 billion (rounded to $115.2 billion), "
             "representing a 142% increase from the prior year.")
    assert g.check_claim(claim, quote, quote).claim == claim


def test_a_figure_from_elsewhere_on_the_page_is_kept_in_the_main_clause_but_an_invented_one_is_not():
    """REAL (D1): '$1.5 billion' was in the headline, the quote came from a later paragraph."""
    page = ("Amkor Technology announces $1.5 billion multi-year strategic partnership with NVIDIA.\n" + "Filler. " * 80 +
            "\nUnder the agreement, NVIDIA will provide a prepayment to support the expansion of Amkor's U.S. "
            "advanced packaging capacity.")
    quote = "Under the agreement, NVIDIA will provide a prepayment to support the expansion of Amkor's U.S. advanced packaging capacity."
    kept = g.check_claim("The $1.5 billion multi-year agreement with NVIDIA supports the expansion of Amkor's U.S. "
                         "advanced packaging capacity.", quote, page)
    assert kept.ok and not kept.reason
    invented = g.check_claim("The $2.5 billion multi-year agreement with NVIDIA supports the expansion of Amkor's "
                             "U.S. advanced packaging capacity.", quote, page)
    assert not invented.ok and "not in the source text" in invented.reason
    dated = "The release is dated July 23, 2026.\n" + page         # a bare '23' on the page backs nothing
    assert not g.check_claim("Apple's Services revenue was $23.1 billion.", quote, dated).ok


def test_cutting_a_clause_never_leaves_a_claim_with_no_figure():
    """REAL (W2): the page showed 'almost billion U.S. dollars' with the number missing."""
    quote = "Amazon's net revenue for the fiscal year ending December 31, 2024, was almost billion U.S. dollars"
    chk = g.check_claim("Amazon's net revenue for the fiscal year ending December 31, 2024, was almost $500 billion "
                        "U.S. dollars.", quote, quote)
    assert not chk.ok and "$500 billion" in chk.reason


def test_while_x_y_sentences_are_split_so_the_positive_half_is_kept():
    s = ("While Amkor has committed to expanding U.S. capacity in Arizona, the specific annual growth rate of this "
         "capacity could not be established.")
    assert g.verifiable_part(s) == "Amkor has committed to expanding U.S. capacity in Arizona."
    assert g.positive_clauses(s) == ["Amkor has committed to expanding U.S. capacity in Arizona"]


# =================================================================================================
# quarter / full-year labels (added after the first live run of the patched configuration)
# =================================================================================================

# REAL, live run of the patched config on W1: with the mislabelled 75.5% finding gone, the answer
# step presented NVIDIA's fourth-quarter GAAP margin as its fiscal-year margin.
W1_Q4_FINDING = ("In the fourth quarter of fiscal year 2025 (ended January 26, 2025), NVIDIA's GAAP gross margin was "
                 "73.0%, which was 1.6 percentage points lower than the previous quarter.")
W1_LIVE_ANSWER = ("NVIDIA's GAAP gross margin for fiscal year 2025 was 73.0% [S2], while its non-GAAP gross margin "
                  "was 75.5% [S2].")
W1_FINDINGS = [{"source_id": "S2", "claim": W1_Q4_FINDING, "quote": "", "basis": "gaap"},
               {"source_id": "S2", "claim": NVDA_F5, "quote": NVDA_QUOTE, "basis": "non-gaap"}]


def test_w1_live_quarterly_figure_presented_as_the_fiscal_year_figure_is_caught():
    hits = g.period_conflicts(W1_LIVE_ANSWER, W1_FINDINGS, {"S2"})
    assert len(hits) == 1 and (hits[0]["figure"], hits[0]["said"], hits[0]["finding_says"]) == ("73.0%", "annual", "quarter")
    assert g.describe_label_issue(hits[0]) == ("73.0% is given as a full-year figure, but the finding it comes "
                                               "from gives it for a quarter")
    right = ("NVIDIA's GAAP gross margin for the fourth quarter of fiscal year 2025 was 73.0% [S2], while its "
             "non-GAAP gross margin for fiscal year 2025 was 75.5% [S2].")
    assert g.period_conflicts(right, W1_FINDINGS, {"S2"}) == []
    assert not g.consistency_audit(W1_LIVE_ANSWER, W1_FINDINGS, {"S2"})["clean"]


@pytest.mark.parametrize("sentence, claims", [
    # REAL answers and findings from the recorded runs that earlier versions of the rule flagged wrongly
    ("AMD's GAAP gross margin for Q3 of fiscal year 2024 was 50% [S1], and for Q4 of the same fiscal year it was 51% [S1].",
     ["For Q4 of fiscal year 2024 (ended Dec 28, 2024), AMD's GAAP gross margin was 51%.",
      "For Q3 of fiscal year 2024 (ended Oct 29, 2024), AMD's GAAP gross margin was 50%."]),
    ("- AMD's FY2024 GAAP margin hit a record 49%, with Q4 reaching 51% driven by a favorable revenue mix [S1].",
     [AMD_F1, "AMD's GAAP gross margin for the fourth quarter of 2024 was 51%."]),
    ("AMD reported a GAAP gross margin of 49% for fiscal year 2024, though its non-GAAP margin reached a record 53% "
     "[S1]; this full-year figure is lower than the 51% recorded in Q4 alone [S1].",
     ["AMD's GAAP gross margin for the fourth quarter of 2024 was 51%.", "AMD's GAAP gross margin for the full year 2024 was 49%."]),
    ("Demand for its chips is surging; data center sales reached $193.7 billion in fiscal 2026 [S1], driven by "
     "Hyperscale customers generating $37.9 billion in Q1 2027 [S1].",
     ["Full-year fiscal 2026 revenue reached $215.9 billion, with data center sales of $193.7 billion accounting for "
      "roughly 90% of company revenue.",
      "In Q1 fiscal 2027, Hyperscale customers generated $37.9 billion in revenue (up 115% year over year)."]),
    ("This trajectory suggests an annualized run-rate of approximately $23.1 billion [S1], up significantly from the "
     "FY2025 total of $16.64 billion [S1].",
     ["Based on Q1 2026 results of $5.775 billion, the Data Center segment is tracking toward an annualized revenue "
      "run-rate of approximately $23.1 billion."]),
    ("In contrast, AMD saw a modest 1 percentage point year-over-year increase to reach 49%, reversing a previous "
     "quarter's dip from 51% [S1].", [AMD_F1]),
    # REAL, third live W1 run: a false alarm that cost one unnecessary synthesis retry before this was fixed
    ("However, even on a like-for-like basis (GAAP), NVIDIA's margin of approximately 73% in Q4 FY2025 [S1] remains "
     "substantially higher than AMD's 49% [S1] and Intel's 32.7% [S1] [S1].",
     ["AMD's GAAP gross margin for the full year 2024 was 49%.", W1_Q4_FINDING,
      "Intel's full-year 2024 GAAP gross margin was 32.7%, which represents a decrease of 7.3 percentage points."]),
])
def test_period_labels_that_agree_with_their_findings_are_left_alone(sentence, claims):
    findings = [{"source_id": "S1", "claim": c, "quote": "", "basis": ""} for c in claims]
    assert g.period_conflicts(sentence, findings, {"S1"}) == []
