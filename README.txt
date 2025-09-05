# Bundles App

## RepairShopr Export

The app includes a CLI to export data from RepairShopr.

### Full export

```
flask rs-export full
```

Results are written as newline-delimited JSON files in the directory given by `EXPORT_DIR` (default `./exports`). A checkpoint file tracks progress so rerunning the command resumes where it left off.

Use `--include-serials` to fetch product serial numbers in a second phase at a lower rate.

### Database upsert

Set `REPAIRSHOPR_EXPORT_TO_DB=true` to upsert records into the SQL database using minimal tables defined in `app.models`.

### Incremental follow-up

Tickets and invoices automatically use the last `updated_at` value seen in prior runs as a `since_updated_at` cursor, allowing incremental exports.
