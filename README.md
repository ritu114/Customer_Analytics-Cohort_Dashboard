# E-Commerce Cohort Retention & RFM Analytics Pipeline

An end-to-end data analytics pipeline that ingests and processes 500K+ transactional records via DuckDB, computes cohort retention decay and customer lifetime value (RFM segmentation), and delivers an executive Power BI dashboard.

![Dashboard Preview](dashboard/dashboard_preview.png)

## 📌 Project Architecture
1. **Analytical Database (OLAP):** DuckDB (local in-process execution)
2. **Data Transformation & Aggregation:** SQL (Window Functions, CTEs, Date Truncation)
3. **Pipeline Orchestration:** Python (`duckdb`, `os`)
4. **Business Intelligence:** Microsoft Power BI (Matrix Heatmaps, DAX Measures, Segment Slicing)

## 📊 Key Business Findings
* **Retention Drop-off:** The steepest customer churn occurs between **Month 0 and Month 1**, where active customer retention drops sharply, showing the critical need for a Day 14–Day 30 automated lifecycle email campaign.
* **Pareto Revenue Concentration:** The **Champions / VIP** segment represents **66.6% of total revenue**, despite accounting for roughly a quarter of the total customer base.
* **At-Risk Accounts:** 14% of the customer base consists of former repeat buyers who have not purchased recently, indicating an immediate target group for win-back discounts.

## 🛠️ Technical Implementation

### 1. Ingestion & Preprocessing
* Raw transactions are read directly via DuckDB's vectorized `read_csv_auto` parser.
* Addressed mixed date format anomalies (`MM/DD/YY` vs `MM/DD/YYYY`) dynamically using `COALESCE` with `try_strptime`.
* Filtered out negative quantities (returns/cancellations) and null customer identifiers.

### 2. SQL Window Functions & Metrics
* **Acquisition Cohort Identification:** Extracted customer initial purchase dates using `DATE_TRUNC('month', MIN(invoice_date))`.
* **Cohort Index Interval:** Computed elapsed months:
  ```sql
  (EXTRACT(YEAR FROM activity_month) - EXTRACT(YEAR FROM cohort_month)) * 12 +
  (EXTRACT(MONTH FROM activity_month) - EXTRACT(MONTH FROM cohort_month)) AS cohort_index
  ```
* **RFM Scoring:** Grouped transactions into quintiles using `NTILE(5)` over recency, order frequency, and monetary spend.

### 3. DAX Measures Used in Power BI
* **Champions Revenue Share:**
  ```dax
  Champions Rev Share = 
  VAR TotalRev = CALCULATE(SUM(rfm_segments[total_spend]), ALL(rfm_segments))
  VAR ChampionsRev = CALCULATE(SUM(rfm_segments[total_spend]), rfm_segments[customer_segment] = "Champions / VIP")
  RETURN 
  DIVIDE(ChampionsRev, TotalRev, 0)
  ```
## 🚀 How to Reproduce Locally

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/](https://github.com/)<your-username>/ecommerce-retention-analytics.git
   cd ecommerce-retention-analytics
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Add Data & Run Pipeline:**
   * Place the `online_retail_II.csv` dataset in `data/`.
   * Run the pipeline:
     ```bash
     python scripts/run_analysis.py
     ```
   * Outputs will be exported to `output/cohort_retention.csv` and `output/rfm_segments.csv`.

4. **View Dashboard:**
   * Open `dashboard/ecommerce_customer_analytics.pbix` in Power BI Desktop and hit **Refresh**.
