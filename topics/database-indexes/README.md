# Database Indexes

## The Interview Question

> "A database query is timing out. Would you add an index on the status column?"

The instinct is yes. The correct answer is: **it depends on the cardinality — and for a status column, probably no.**

---

## The Library Analogy

Imagine a library with a million books, sorted randomly on shelves.

- **No index** → you walk down every single aisle looking for the book you want. That's a **full table scan**.
- **With an index** → you check the card catalog, it tells you the exact shelf and position, you go straight there. That's an **index lookup**.

An index is just a **sorted shortcut** the database maintains on the side. It trades extra write cost and storage for dramatically faster reads.

---

## What Is an Index, Really?

Under the hood, most databases implement indexes as a **B-Tree** — a self-balancing tree where every lookup, insert, and delete runs in `O(log n)`.

```
             [50]
           /       \
       [20]         [80]
      /    \       /    \
   [10]   [35]  [65]   [95]
```

When you query `WHERE user_id = 65`, the database walks this tree in milliseconds instead of scanning all million rows.

The index stores `(column_value → row_location)` pairs in sorted order, so range queries like `WHERE created_at BETWEEN '2024-01-01' AND '2024-06-01'` are also fast — the database jumps to the start of the range and reads sequentially.

---

## Cardinality: The Most Important Concept

**Cardinality** = the number of distinct values in a column.

| Column | Distinct Values | Cardinality |
|---|---|---|
| `user_id` | ~1,000,000 (one per row) | Very high |
| `email` | ~1,000,000 (unique) | Very high |
| `country` | ~200 | Medium |
| `status` | 3 (pending, processing, completed) | Very low |

**High cardinality → index is powerful.** Each value narrows the result down to a tiny slice of rows.

**Low cardinality → index is useless (or worse).** Each value still matches hundreds of thousands of rows. The database engine often looks at the index, realizes it won't help, and **ignores it entirely** — scanning the full table anyway.

```mermaid
flowchart LR
    Q["WHERE status = 'pending'"] --> I["Index lookup"]
    I --> R["Returns 330,000 rows\n out of 1,000,000"]
    R --> S["Database gives up,\n does full scan instead"]
    style S fill:#ff6b6b,color:#fff
```

---

## The Hidden Write Tax

Every index you add is an extra data structure the database must **keep in sync** on every `INSERT`, `UPDATE`, and `DELETE`.

A low-cardinality index gives you:
- **Zero read performance gain** (engine ignores it)
- **Real write performance loss** (engine updates it on every write)

That's the worst trade-off in databases.

---

## When to Use an Index

### ✅ Good candidates

| Scenario | Why |
|---|---|
| `WHERE email = ?` | Emails are unique — one row returned instantly |
| `WHERE user_id = ?` | Primary key lookup — classic index use case |
| `WHERE created_at > ?` | Range query on a timestamp — B-Tree handles this perfectly |
| `JOIN` on a foreign key | e.g., `orders.user_id` joining to `users.id` |
| `ORDER BY` on a large table | Index pre-sorts the data, skips the sort step |

### ❌ Poor candidates

| Scenario | Why |
|---|---|
| `WHERE status = ?` (3 values) | Low cardinality — engine scans anyway |
| `WHERE is_active = true` (boolean) | Only 2 values — useless |
| Small tables (< a few thousand rows) | Full scan is fast enough; index adds overhead |
| Columns that are rarely queried | Pays the write tax for nothing |

---

## Composite Indexes

Sometimes a single column isn't enough, but the **combination** is highly selective.

```sql
-- This index is useless alone (status is low cardinality)
CREATE INDEX ON orders (status);

-- But this composite index is powerful:
-- "Give me all PENDING orders for user 42"
CREATE INDEX ON orders (user_id, status);
```

A composite index narrows first by `user_id` (high cardinality), then by `status` within that user's rows — now you're filtering a handful of rows, not hundreds of thousands.

> **Rule of thumb:** put the highest-cardinality column first in a composite index.

---

## Checking Cardinality Before Indexing

Before adding any index, run this:

```sql
-- PostgreSQL / MySQL
SELECT COUNT(DISTINCT status) AS distinct_values,
       COUNT(*)               AS total_rows
FROM   orders;
```

If `distinct_values / total_rows` is close to **1.0** → high cardinality, good index candidate.
If it's close to **0.0** → low cardinality, skip the index.

---

## TL;DR

- An index is a **sorted shortcut** (B-Tree) that avoids full table scans.
- **Cardinality** determines whether an index actually helps — low cardinality columns will be ignored by the query planner.
- Every index adds a **write tax** — only add them when the read gain is worth it.
- Index **high-cardinality columns**: user IDs, emails, foreign keys, timestamps.
- **Avoid** indexing booleans and status columns with only a few distinct values.
- Use **composite indexes** to make low-cardinality columns useful by pairing them with high-cardinality ones.
