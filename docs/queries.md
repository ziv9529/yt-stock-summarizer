# Example SQL Queries

Run these with `sqlite3 data/summaries.db` or paste into DB Browser for SQLite.

---

## 1. All mentions of a specific ticker with bullish stance

```sql
SELECT
    v.title,
    v.video_date,
    json_extract(t.value, '$.symbol')       AS symbol,
    json_extract(t.value, '$.stance')       AS stance,
    json_extract(t.value, '$.price_target') AS price_target,
    json_extract(t.value, '$.rationale')    AS rationale
FROM summaries s
JOIN videos v ON v.id = s.video_id,
json_each(s.tickers_mentioned) t
WHERE json_extract(t.value, '$.symbol') = 'NVDA'
  AND json_extract(t.value, '$.stance') = 'bullish'
ORDER BY v.video_date DESC;
```

Change `'NVDA'` to any ticker. Change `'bullish'` to `'bearish'` or `'neutral'`.

---

## 2. Highest-conviction videos (sentiment score >= 8)

```sql
SELECT
    v.title,
    v.video_date,
    s.overall_sentiment,
    s.sentiment_score,
    s.tldr
FROM summaries s
JOIN videos v ON v.id = s.video_id
WHERE s.sentiment_score >= 8
  AND s.is_finance_content = 1
ORDER BY s.sentiment_score DESC, v.video_date DESC;
```

---

## 3. Most-discussed tickers across the whole archive

```sql
SELECT
    json_extract(t.value, '$.symbol') AS symbol,
    COUNT(*)                          AS mention_count,
    SUM(CASE WHEN json_extract(t.value, '$.stance') = 'bullish'  THEN 1 ELSE 0 END) AS bullish,
    SUM(CASE WHEN json_extract(t.value, '$.stance') = 'bearish'  THEN 1 ELSE 0 END) AS bearish,
    SUM(CASE WHEN json_extract(t.value, '$.stance') = 'neutral'  THEN 1 ELSE 0 END) AS neutral
FROM summaries s,
json_each(s.tickers_mentioned) t
WHERE json_extract(t.value, '$.symbol') IS NOT NULL
GROUP BY symbol
ORDER BY mention_count DESC
LIMIT 20;
```

---

## 4. Videos covering a specific topic or macro theme

```sql
SELECT
    v.title,
    v.video_date,
    s.overall_sentiment,
    s.macro_views
FROM summaries s
JOIN videos v ON v.id = s.video_id
WHERE EXISTS (
    SELECT 1 FROM json_each(s.topics) t
    WHERE lower(t.value) LIKE '%fed%'
       OR lower(t.value) LIKE '%interest rate%'
       OR lower(t.value) LIKE '%inflation%'
)
ORDER BY v.video_date DESC;
```

Swap the topic terms to search for `'ai'`, `'semiconductors'`, `'earnings'`, etc.

---

## 5. Stance timeline for a given ticker — did the view change over time?

```sql
SELECT
    v.video_date,
    v.title,
    json_extract(t.value, '$.stance')       AS stance,
    json_extract(t.value, '$.price_target') AS price_target,
    json_extract(t.value, '$.rationale')    AS rationale
FROM summaries s
JOIN videos v ON v.id = s.video_id,
json_each(s.tickers_mentioned) t
WHERE json_extract(t.value, '$.symbol') = 'NVDA'
ORDER BY v.video_date ASC;
```

Shows how conviction on a ticker evolved across the archive, oldest first.
