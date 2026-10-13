import os
import duckdb

os.makedirs("output", exist_ok=True)

con = duckdb.connect("analytics.duckdb")

print("1. Ingesting and cleaning raw transaction data...")

# Note: We parse with try_strptime to handle both 4-digit and 2-digit years cleanly
con.execute("""
    CREATE OR REPLACE VIEW clean_transactions AS
    SELECT 
        Invoice AS invoice_no,
        StockCode AS stock_code,
        Description AS description,
        TRY_CAST(Quantity AS INTEGER) AS quantity,
        COALESCE(
            TRY_CAST(try_strptime(InvoiceDate, '%m/%d/%Y %H:%M') AS TIMESTAMP),
            TRY_CAST(try_strptime(InvoiceDate, '%d/%m/%Y %H:%M') AS TIMESTAMP),
            TRY_CAST(try_strptime(InvoiceDate, '%m/%d/%y %H:%M') AS TIMESTAMP),
            TRY_CAST(try_strptime(InvoiceDate, '%Y-%m-%d %H:%M:%S') AS TIMESTAMP),
            TRY_CAST(InvoiceDate AS TIMESTAMP)
        ) AS invoice_date,
        TRY_CAST(Price AS DOUBLE) AS unit_price,
        (TRY_CAST(Quantity AS INTEGER) * TRY_CAST(Price AS DOUBLE)) AS total_revenue,
        "Customer ID" AS customer_id,
        Country AS country
    FROM read_csv_auto('data/online_retail_II.csv', all_varchar=True)
    WHERE "Customer ID" IS NOT NULL
      AND TRY_CAST(Quantity AS INTEGER) > 0
      AND TRY_CAST(Price AS DOUBLE) > 0
      AND COALESCE(
            TRY_CAST(try_strptime(InvoiceDate, '%m/%d/%Y %H:%M') AS TIMESTAMP) + INTERVAL 2000 YEAR,
            TRY_CAST(try_strptime(InvoiceDate, '%d/%m/%Y %H:%M') AS TIMESTAMP) + INTERVAL 2000 YEAR,
            TRY_CAST(try_strptime(InvoiceDate, '%m/%d/%y %H:%M') AS TIMESTAMP),
            TRY_CAST(try_strptime(InvoiceDate, '%Y-%m-%d %H:%M:%S') AS TIMESTAMP),
            TRY_CAST(InvoiceDate AS TIMESTAMP)
        ) IS NOT NULL;
""")

print("2. Running Cohort Retention Analysis...")

cohort_query = """
    WITH customer_first_purchase AS (
        SELECT 
            customer_id,
            DATE_TRUNC('month', MIN(invoice_date)) AS cohort_month
        FROM clean_transactions
        GROUP BY customer_id
    ),
    cohort_activity AS (
        SELECT 
            t.customer_id,
            c.cohort_month,
            DATE_TRUNC('month', t.invoice_date) AS activity_month
        FROM clean_transactions t
        JOIN customer_first_purchase c ON t.customer_id = c.customer_id
        GROUP BY t.customer_id, c.cohort_month, DATE_TRUNC('month', t.invoice_date)
    ),
    cohort_indexed AS (
        SELECT 
            cohort_month,
            activity_month,
            customer_id,
            (EXTRACT(YEAR FROM activity_month) - EXTRACT(YEAR FROM cohort_month)) * 12 +
            (EXTRACT(MONTH FROM activity_month) - EXTRACT(MONTH FROM cohort_month)) AS cohort_index
        FROM cohort_activity
    )
    SELECT 
        REPLACE(strftime(cohort_month, '%Y-%m'), '00', '20') AS cohort_month,
        cohort_index,
        COUNT(DISTINCT customer_id) AS active_customers
    FROM cohort_indexed
    WHERE cohort_index >= 0 AND cohort_index <= 24
    GROUP BY cohort_month, cohort_index
    ORDER BY cohort_month, cohort_index
"""

con.execute(f"""
    COPY ({cohort_query}) TO 'output/cohort_retention.csv' (HEADER, DELIMITER ',');
""")
print("-> Saved output/cohort_retention.csv")

print("3. Running RFM Customer Segmentation...")

rfm_query = """
    WITH customer_stats AS (
        SELECT 
            customer_id,
            MAX(invoice_date) AS last_order_date,
            COUNT(DISTINCT invoice_no) AS frequency,
            SUM(total_revenue) AS monetary
        FROM clean_transactions
        GROUP BY customer_id
    ),
    rfm_scores AS (
        SELECT 
            customer_id,
            last_order_date,
            frequency,
            monetary,
            NTILE(5) OVER (ORDER BY last_order_date ASC) AS r_score,
            NTILE(5) OVER (ORDER BY frequency ASC) AS f_score,
            NTILE(5) OVER (ORDER BY monetary ASC) AS m_score
        FROM customer_stats
    )
    SELECT 
        customer_id,
        frequency,
        ROUND(monetary, 2) AS total_spend,
        r_score,
        f_score,
        m_score,
        CASE 
            WHEN (r_score >= 4 AND f_score >= 4) THEN 'Champions / VIP'
            WHEN (r_score >= 3 AND f_score >= 3) THEN 'Loyal Customers'
            WHEN (r_score <= 2 AND f_score >= 3) THEN 'At Risk'
            WHEN (r_score <= 2 AND f_score <= 2) THEN 'Lost'
            ELSE 'Potential Loyalist'
        END AS customer_segment
    FROM rfm_scores
"""

con.execute(f"""
    COPY ({rfm_query}) TO 'output/rfm_segments.csv' (HEADER, DELIMITER ',');
""")
print("-> Saved output/rfm_segments.csv")

con.close()
print("Analysis pipeline complete!")