system_prompt = "You are an ESG data analyst with expertise in extracting and analyzing environmental, social, and governance (ESG) metrics."
match output_format:
    case "json":
        output_instructions = "output a table according to a json schema: {json_schema}"
    case "markdown":
        output_instructions = "output a table in markdown with the following columns: {columns}"

rules = """
- Ensure the 'Year' is in the format YYYY.
- Provide total amounts for each metric per 'Year' without a detailed breakdown.
- Convert units using simple multiplication factors:
    - Multiply by 1000 for "Thousands".
    - Multiply by 1000000 for "Millions".
- Use restated values if corrected post external audit.
- Focus on extracting information for the main company in the ESG report.
- Extract only explicitly mentioned information; do not make assumptions.
- Indicate "N/A" for any missing information.
- Ensure all years explicitly mentioned in the tables or figures are included.\n"""
rules += "- remove ',' in numbers" if output_format == "json" else ""

verification = """
**Verify Accuracy**:
   - Check that the data aligns with the provided 'Data Type', 'Unit of Measure', and 'Description' for each metric:
   {metrics_information}
"""

image_instructions = "Analyze images to ensure accuracy and match exact colors as per the legend and graph." if len(image_paths) > 0 else ""

context_preview = "Here is the extracted information from the report: {context}" if len(context) > 0 else ""
