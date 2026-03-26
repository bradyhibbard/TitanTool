LEGEND_PROMPT = """
You are analyzing a residential construction drawing.

Task:
Find the ELECTRICAL SYMBOLS legend on this page.

Instructions:
1. Look for a table, boxed region, or grouped region that contains electrical labels and matching symbols.
2. Return the bounding box for the FULL electrical legend region.
3. Be generous enough to include the title and all rows of the legend.
4. If there are multiple legends, choose the one specifically related to electrical symbols.
5. Return ONLY valid JSON.

Output format:
{
  "found": true,
  "legend_type": "electrical_symbols",
  "bbox_0_to_999": [x_min, y_min, x_max, y_max],
  "confidence": 0.0,
  "reason": "short reason"
}
"""

PLAN_REGION_PROMPT = """
You are analyzing a residential construction drawing page.

Task:
Find the main house plan / floor plan drawing area in the center of the page.

Instructions:
1. Identify the large central drawing region that contains the actual house plan linework.
2. Do NOT include page margins, notes, title blocks, legends, or schedules unless they overlap the drawing itself.
3. Return one bounding box for the main plan region only.
4. Return ONLY valid JSON.

Output format:
{
  "found": true,
  "region_type": "main_house_plan",
  "bbox_0_to_999": [x_min, y_min, x_max, y_max],
  "confidence": 0.0,
  "reason": "short reason"
}
"""