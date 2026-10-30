# COVID-19 Global Impact Dashboard

A reproducible Python/Streamlit project for cleaning and exploring a user-provided COVID-19 dataset. **No COVID dataset was present with the task description**, so this package contains no invented records, results, screenshots, or claims about real-world trends. Add your dataset at `data/raw/covid.csv` (or pass its path to the analysis script) before running the analysis.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python analysis.py --input data/raw/covid.csv
streamlit run app.py
```

The pipeline writes `data/processed/COVID_19_Cleaned_Data.csv`, charts and `reports/insights.md`. The dashboard reads the cleaned CSV and supports country and date filters. Run the notebook `COVID_19_Analysis.ipynb` after installing requirements for an interactive walkthrough.

## Dataset compatibility and limitations

The pipeline recognizes common column names such as `location`/`country`, `date`, `new_cases`, `total_cases`, `new_deaths`, `total_deaths`, `people_vaccinated`, `people_fully_vaccinated`, and `population`, including common title-case variants. It will report discovered fields and fail clearly if country/date fields cannot be identified. It does not merge external sources or infer missing population. If the input is synthetic, label it as synthetic in your submission; this project cannot determine provenance automatically.

Cumulative data can be revised and daily values may be missing. Negative daily corrections are preserved and flagged, not silently discarded. Missing numeric observations remain missing. Seven-day averages use available observations within each country; interpret cautiously when dates are sparse. Vaccination coverage is only calculated with a valid population. CFR is a descriptive ratio, not an infection-fatality rate. Doubling time is only estimated for positive growth and sufficient valid observations.

## Outputs

- `COVID_19_Cleaned_Data.csv`: cleaned input with available derived metrics.
- `reports/figures/*.png`: data-dependent plots (only applicable plots are produced).
- `reports/insights.md`: dataset profile, cleaning notes, and conservative computed insights.
- `reports/COVID_19_Executive_Summary.pdf`: generated only when running pipeline with valid data and reportlab installed (one-page summary).

## Metrics

- Seven-day rolling average of daily new cases, grouped by country.
- CFR = total deaths / total cases × 100, where both values are present and cases > 0.
- Cases per million = total cases / population × 1,000,000, for positive population.
- Vaccination coverage = people vaccinated / population × 100, for positive population.
- Doubling-time estimate from two positive cumulative case observations at least 7 days apart, using exponential growth. Not available where criteria are unmet.

## Power BI

Import `data/processed/COVID_19_Cleaned_Data.csv` into Power BI Desktop. Use `date` as a date field, `location` as country, and add a date slicer plus country slicer. Build cards from maximum cumulative cases/deaths (avoid summing cumulative values), a line chart for `new_cases` and `new_cases_7d_avg`, a line for `total_deaths`, and a country bar chart for `cases_per_million`. Measures/aggregations should be checked against your selected date range; do not sum cumulative measures across dates.
