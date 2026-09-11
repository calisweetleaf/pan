# SCOPE — Master database CRDT pool

## Engagement Mode

- mode: COMPOSE
- target_module: PAN_SDK/master_db.py
- target_module_provenance: whitepaper section 6 + PANPersistenceStore
- justification: I am composing the nation's offline-first CRDT sqlite pool as the canon single-file master_db monolith. Documents, G-counters, and OR-sets join by commutative, associative, idempotent merge on the existing PANPersistenceStore. A wrapper around kv_state would duplicate the join. DHTNode binds MasterDatabase on the same sqlite connection so civic hydrate includes the national store without a second database engine.
- author: daeron
- date: 2026-09-10

## Targets

| Target | Owner | Consumed boundary |
|---|---|---|
| `PAN_SDK/master_db.py` | MasterDatabase | LWW docs, G-counter, OR-set, page-hash sync |
| `PAN_SDK/PAN_SDK.py` | DHTNode.master_db | same persistence connection, no extra sqlite |
| `test/master_db/test_master_db.py` | direct consumer | two offline nodes converge; three-way associativity |

## Direct-edit justification (PAN_SDK.py only)

Binding `MasterDatabase` onto `DHTNode` is the same seam as treasury. The CRDT must not open a second sqlite engine beside `PANPersistenceStore`.

## Out of scope this unit

- Orama dashboard / 1536-d vector spaces (named in the whitepaper, not this consumed path)
- Thyris VM owners
- sqlite3_rsync binary; page hashes are implemented in-process
