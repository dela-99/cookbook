# Composite Indexes — The Multi-Column Index Trap

## The Interview Question

> "How would you speed up a query that filters by both `first_name` and `last_name`?"

The instinct: "Easy — put an index on each column."

```sql
CREATE INDEX ON users (first_name);
CREATE INDEX ON users (last_name);
```

Then the kill-shot:

> "Your database can only use one index per table access here. Which one wins, and what does it do with the other condition?"

Most candidates freeze. They assumed the database would magically combine both indexes. It doesn't — at least not the way they think.

---

## Why Two Single-Column Indexes Lose

When you write `WHERE first_name = 'Alice' AND last_name = 'Smith'`, the query planner has three options:

1. Use the `first_name` index to find all the "Alices," then filter for `last_name = 'Smith'` row-by-row
2. Use the `last_name` index to find all the "Smiths," then filter for `first_name = 'Alice'` row-by-row
3. Use *both* indexes and intersect their results (only some databases do this, only sometimes, and only when the cost estimate looks favorable)

In practice, the planner picks **one** index, walks it, then does a post-filter scan over whatever it found. The "other" index sits on disk doing nothing for this query — except costing you write performance on every insert (see [Bulk Loads & Indexes](../bulk-loads-and-indexes/) for that write tax).

If "Alice" matches 50,000 rows and only 12 of them are Smiths, the database fetches 50,000 rows and discards 49,988. That's not an index lookup — that's a slightly cheaper full scan.

---

## The Composite Index — One Sorted Structure for Both Columns

A **composite index** (also called a *multi-column index*) is a single B-Tree built over multiple columns at once:

```sql
CREATE INDEX ON users (first_name, last_name);
```

Internally, the index entries are sorted **first by `first_name`, then by `last_name` within each first-name group**:

```
Index entries (in sorted order):

  Alice,   Brown
  Alice,   Smith       ←  WHERE first_name = 'Alice' AND last_name = 'Smith'
  Alice,   Wilson           jumps straight here in O(log n)
  Bob,     Anderson
  Bob,     Smith
  Charlie, Brown
  Charlie, Smith
  Charlie, Wilson
```

Now `WHERE first_name = 'Alice' AND last_name = 'Smith'` is a single index lookup — the database walks the tree once and lands on the exact row. From 49,988 wasted fetches down to zero.

---

## The Catch — Column Order Matters (The Left-to-Right Rule)

This is where most engineers get tripped up. A composite index on `(first_name, last_name)` is **not the same** as one on `(last_name, first_name)`. The order of columns in `CREATE INDEX` determines which queries the index can serve.

The rule:

> **A composite index can only be used if your `WHERE` clause filters on a contiguous left-to-right prefix of its columns.**

| Query | Uses the index `(first_name, last_name)`? |
|---|---|
| `WHERE first_name = 'Alice' AND last_name = 'Smith'` | ✅ Yes — exact match, full prefix |
| `WHERE first_name = 'Alice'` | ✅ Yes — uses the leading column |
| `WHERE last_name = 'Smith'` | ❌ No — skips the leading column, index is useless |
| `WHERE first_name LIKE 'Al%' AND last_name = 'Smith'` | ⚠️ Partial — uses the index up through `first_name`, then post-filters `last_name` |
| `WHERE last_name = 'Smith' AND first_name = 'Alice'` | ✅ Yes — order *in the query* doesn't matter, only order *in the index definition* |

---

## The Phone Book Analogy

A composite index on `(first_name, last_name)` is exactly like a phone book printed alphabetically by **last name first, then first name** — but with the columns flipped.

If I ask you to find **"Smith, Alice"**, you flip to the S section in seconds. Done.

If I ask you to find **everyone named "Alice"** (any last name), you can't — the book isn't sorted by first name. You'd have to read every page from cover to cover. *That's* the left-to-right rule. The index physically sorts the data in one direction; queries that don't start at the leftmost column can't take the shortcut.

A real phone book is `(last_name, first_name)`. If your queries are always "look up the family name first, then narrow by first name," that order is right. If your queries are "find me all the Alices," you need a different index — one that leads with `first_name`.

---

## Picking the Column Order

The rule of thumb everyone repeats — *"put the highest-cardinality column first"* — is **only half the story**. The real rule is:

> **Put the column you always filter on first. Within that constraint, prefer higher cardinality.**

A few patterns:

| Query pattern | Best index |
|---|---|
| Always filter by `tenant_id`, sometimes also by `created_at` | `(tenant_id, created_at)` — `tenant_id` is always present |
| Always filter by both `user_id` and `status` | `(user_id, status)` — `user_id` is higher cardinality |
| Sometimes by `user_id` alone, sometimes by `user_id + status` | `(user_id, status)` — still serves both queries because `user_id` is the leading column |
| Sometimes by `status` alone | Add a separate `(status, ...)` index — `(user_id, status)` won't help here |

The composite index serves the **leading-column-only** query for free. The reverse is not true: a composite index on `(A, B)` does **not** help queries that filter only on `B`. If you have both patterns, you need both indexes.

---

## Modern Caveat — Index Skip Scan

Some databases (Oracle, recent Postgres versions for certain shapes, MySQL 8.0+) can perform a *skip scan* on a composite index — essentially pretending the leading column has only a few distinct values and iterating through each one to use the index for the trailing column.

It works, but it's:
- Much slower than a proper index lookup
- Only chosen by the planner when the leading column has very low cardinality
- Not portable across databases

**Don't design around skip scan.** Treat the left-to-right rule as absolute and only fall back to skip scan as a last-resort optimization explained in `EXPLAIN ANALYZE`.

---

## Production Considerations

| Decision | What to think about |
|---|---|
| **One composite, not many single-column** | A composite index that matches your query shape is almost always faster than multiple single-column indexes the planner has to pick between. |
| **Don't over-index** | Each composite index has the same write tax as any other index — see [Bulk Loads & Indexes](../bulk-loads-and-indexes/). One well-designed composite beats five hopeful single-column ones. |
| **Read the EXPLAIN plan** | If `EXPLAIN ANALYZE` shows `Seq Scan` instead of `Index Scan`, your index isn't being used — usually because the leading column isn't in the `WHERE` clause. |
| **Watch column order in ORDER BY** | A composite index also accelerates `ORDER BY first_name, last_name`. But `ORDER BY last_name, first_name` won't use it — same left-to-right rule. |
| **Covering indexes** | If you can include every column the query reads inside the index itself (PostgreSQL `INCLUDE`, MySQL `USING INDEX`), the database can answer the query without touching the heap at all. |

---

## The Key Insight

The query planner doesn't combine indexes the way you intuitively think it should. It picks one, walks it, and filters the rest the slow way. The fix isn't "more indexes" — it's **one index designed for the actual query**.

And because the index is a single sorted structure, the order of its columns *is* the order in which the data is physically sorted. Your queries either start at the leftmost column or they get a full scan.

> Index design depends entirely on how you query the data — not on how the schema looks.

---

## TL;DR

- A query filtering on `WHERE a = ? AND b = ?` is **not** served by two single-column indexes — the database picks one and scans the rest.
- Use a **composite index**: `CREATE INDEX ON t (a, b)`. One B-Tree, sorted by `a` then `b`, single lookup.
- **Left-to-right rule:** the index only helps queries whose `WHERE` clause filters on a contiguous left-to-right prefix of its columns. `(a, b)` helps `a` and `a + b`. It does *not* help `b` alone.
- Put the column you **always** filter on first. Within that, prefer higher cardinality.
- A composite index has the same write cost as any other index — design for your real queries, don't speculate.

For multi-column queries: one composite index, leading column chosen for your query pattern, and read the `EXPLAIN` plan to prove the database is using it.

---

## Related

- [Database Indexes](../database-indexes/) — when to add an index in the first place, cardinality, and B-Tree fundamentals
- [Bulk Loads & Indexes](../bulk-loads-and-indexes/) — the write-side cost every composite index also pays

---

## Resources

### Docs
- [PostgreSQL — Multicolumn Indexes](https://www.postgresql.org/docs/current/indexes-multicolumn.html)
- [PostgreSQL — Index-Only Scans and Covering Indexes](https://www.postgresql.org/docs/current/indexes-index-only-scans.html)
- [MySQL — Multiple-Column Indexes](https://dev.mysql.com/doc/refman/8.0/en/multiple-column-indexes.html)
