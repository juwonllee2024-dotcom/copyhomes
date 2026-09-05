# Example

From this directory:

```text
copyhomes plan sample.txt ./backup ./share
copyhomes save sample.txt ./backup ./share --receipt ./receipts/sample.json
copyhomes undo ./receipts/sample.json
```

The first command shows the destinations without writing anything. The second
creates `sample.txt` in both homes and records an undo receipt.
