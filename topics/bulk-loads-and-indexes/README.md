# How Indexes Destroy Bulk Write Performance

## The Interview Question

> "Optimize a high-frequency insert query that loads millions of log rows into an indexed table."

The instinct: "Just run the `INSERT`." Maybe batch it. Maybe wrap it in a transaction.

Then the kill-shot:

> "What happens to the indexes during those millions of writes?"

If you don't know the answer, the interview ends there. Because every `INSERT` into an indexed table isn't one operation — it's **one row insert plus one full index update per index**. With five indexes on the table, every row is six writes, and several of those force the database to **rewalk and rebalance a B-Tree**.

Multiply by ten million rows. That's how a one-hour data load becomes an eight-hour incident.

---

## What Actually Happens on a Single Insert

When you insert a row into a table that has indexes, the database does *all* of this — every time:

```
Insert one row into a table with 5 indexes:

  1.  Write the row to the table heap         (1 disk write)
  2.  Walk index A's B-Tree, find slot         (~log(n) reads)
      Insert key, maybe split + rebalance      (1–2 writes + possible cascading splits)
  3.  Same for index B                         (...)
  4.  Same for index C                         (...)
  5.  Same for index D                         (...)
  6.  Same for index E                         (...)

Net cost: ~6 disk operations + 5 full B-Tree walks
                        per single inserted row
```

A B-Tree insert is `O(log n)` in the *best* case — but every so often the tree fills a node and has to **split**, which can cascade up the tree, lock pages, and trigger more disk I/O than a regular insert. The fuller the tree, the more often you pay that tax.

Five indexes? You pay it five times per row. Ten million rows? You're doing fifty million B-Tree walks before the load finishes.

This is why bulk inserts into indexed tables don't just feel slow — they completely **saturate disk I/O and tank the entire database** for everyone else.

---

## The Moving Truck Analogy

Loading rows one-by-one into an indexed table is like moving apartments by driving the truck **once per box**.

- Box 1 → drive to new place → drop it off → drive back
- Box 2 → drive to new place → drop it off → drive back
- Box 3 → ...

Every single insert forces the database to walk and possibly rebalance every index on the table. The trip is the cost, not the box.

The right move is to **load the truck once**. Pile every box in, drive the whole thing, unload at the destination. That's what "drop indexes → bulk load → rebuild indexes" does.

---

## The Pattern: Drop → Load → Rebuild

```sql
-- Step 1 — drop the indexes
DROP INDEX idx_logs_user_id;
DROP INDEX idx_logs_timestamp;
DROP INDEX idx_logs_status;
-- ... drop every non-essential index

-- Step 2 — bulk load (no per-row index updates to pay for)
COPY logs FROM '/tmp/logs.csv' WITH CSV;        -- PostgreSQL
-- or
LOAD DATA INFILE '/tmp/logs.csv' INTO TABLE logs; -- MySQL

-- Step 3 — rebuild the indexes from scratch
CREATE INDEX idx_logs_user_id    ON logs (user_id);
CREATE INDEX idx_logs_timestamp  ON logs (timestamp);
CREATE INDEX idx_logs_status     ON logs (status);
```

Three steps. Often **10–50× faster** than inserting into the indexed table directly.

---

## Why Rebuilding Beats Maintaining

This is the part that confuses people: *if rebuilding is so expensive, how is it faster than just inserting?*

Because building a B-Tree from scratch is a **completely different algorithm** than maintaining one row-at-a-time:

| Approach | What the DB does |
|---|---|
| **Maintain (row-by-row insert)** | For every row: walk the tree, find slot, insert, rebalance. `O(log n)` per row × `n` rows = `O(n log n)` with high constant factor and random disk I/O. |
| **Rebuild (one-shot build)** | Read all rows once, **sort them externally**, write the sorted leaves sequentially, build the upper tree on top. Almost entirely sequential disk I/O. No rebalancing — the tree is built balanced by design. |

The bulk build is `O(n log n)` *algorithmically* — but the constant factor and the disk access pattern are an order of magnitude friendlier. Sequential I/O beats random I/O. Bulk sort beats incremental insert. Every time.

---

## Production Considerations

Dropping indexes in production is a **real** operation, not a free trick. Some things to plan for:

| Decision | What to think about |
|---|---|
| **Read traffic during the load** | Without indexes, every read on the table becomes a full scan. If reads are still hitting this table during the load, performance for *readers* collapses. Schedule loads during low-traffic windows, or load into a staging table and swap. |
| **Unique constraints** | A `UNIQUE` index is also a *correctness* constraint. Drop it and you can insert duplicates that the rebuild will fail on. Either deduplicate your input first or keep unique indexes in place. |
| **Foreign keys** | Same problem class. Validating FK references row-by-row is expensive; bulk loaders often skip FK checks. Re-enable + re-validate after the load. |
| **Locking on rebuild** | `CREATE INDEX` takes an exclusive lock by default. In PostgreSQL use `CREATE INDEX CONCURRENTLY` to build without blocking writes (slower, but no downtime). |
| **Staging-table pattern** | The cleanest pattern is: load into an *unindexed* staging table → validate → `INSERT INTO main_table SELECT *` (which can still be batched). Production tables never lose their indexes. |
| **Asynchronous / off-hours** | Bulk loads should run during maintenance windows when possible. Dropping indexes mid-day on a live table is rarely the right call. |

---

## When NOT to Drop Indexes

- **Small loads** (< ~100K rows) — the drop + rebuild overhead outweighs the savings. Just insert with indexes intact.
- **Continuous ingestion** (Kafka consumers, telemetry streams) — you can't drop indexes for traffic that never stops. Use partitioning, write-optimized storage (LSM-trees), or batch micro-inserts instead.
- **Tables under active reads** with no maintenance window — dropping indexes here punishes every user of the table until the rebuild finishes.

---

## Read-Side vs Write-Side

This piece is the *write* half of the indexing story. The *read* half — when to add an index, when an index is useless, the cardinality trap — lives in [Database Indexes](../database-indexes/). They're two sides of the same trade:

- An index is a **sorted shortcut** that speeds up reads.
- An index is a **maintenance contract** that the database pays on every write.

Adding indexes is a read-vs-write trade. Dropping them for bulk loads is the same trade — just temporarily reversed.

---

## The Key Insight

Indexes are not free. They are a **deal**: the database keeps a sorted shortcut for you so reads are fast, and you pay for it on every write.

For a normal OLTP workload (reads >> writes), that deal is worth it.

For a bulk load (millions of writes, zero reads during the operation), that deal **destroys you**. The fix isn't to make inserts faster — it's to temporarily cancel the deal, do the work, then sign it again at the end.

---

## TL;DR

- Every insert into an indexed table is **one row insert + one B-Tree walk per index** — plus occasional cascading rebalances.
- Five indexes means every row is six writes. Ten million rows means fifty million B-Tree walks.
- **Drop the non-essential indexes → bulk load → rebuild from scratch.** Building an index in one sorted pass is 10–50× faster than maintaining it row-by-row.
- Keep `UNIQUE` indexes if you depend on them for correctness. Watch out for read traffic during the load — without indexes, every reader gets a full scan.
- For continuous high-write workloads where you can't drop indexes, the answer is partitioning, LSM-tree storage engines, or staging tables — not the drop-rebuild pattern.

Indexes make reads lightning fast. They make writes painfully slow. The interview question isn't "do you know what an index is" — it's "do you know when to take one *off*."

---

## Resources

### Docs
- [PostgreSQL — Populating a Database (drop indexes, then COPY)](https://www.postgresql.org/docs/current/populate.html)
- [PostgreSQL — `CREATE INDEX CONCURRENTLY`](https://www.postgresql.org/docs/current/sql-createindex.html)
- [MySQL — Bulk Data Loading for InnoDB Tables](https://dev.mysql.com/doc/refman/8.0/en/optimizing-innodb-bulk-data-loading.html)
