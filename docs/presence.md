# Collaborative workspace presence

*Design + MVP for [#30](https://github.com/mergeos-bounties/Lappa/issues/30).*

Presence answers one question for a shared workspace: **who else is in here
right now, and what are they touching?** It is deliberately the smallest thing
that answers it — no server, no ports, no database, no new dependency.

Today Lappa is single-user by construction. Two people who point their IDEs at
the same `packages/` tree (a network share, a mounted NAS, a synced folder, or
two IDE processes on one machine) cannot see each other at all: `PUT /api/files`
writes the file and the second save silently replaces the first, with no signal
anywhere. Presence makes the other person visible *before* that happens.

---

## Model

Every IDE session is a **peer**. A peer writes one small JSON record into a
shared **presence directory** and refreshes it on a heartbeat. Discovery is
listing that directory. That is the entire protocol.

```
<workspace root>/.lappa/presence/
├── peer-a17f3c9d2e01.json     # alice, editing launch/sim.launch.py
├── peer-51bb0f7743aa.json     # bob, sim running
└── peer-9d0e2c118f34.json     # carol, idle
```

The presence directory is resolved in this order:

| # | Source | Use |
| --- | --- | --- |
| 1 | `--dir` / explicit argument | tests, scripts |
| 2 | `LAPPA_PRESENCE_DIR` | a share that is *not* the workspace root |
| 3 | `<first workspace root>/.lappa/presence` | **default** — collaborators already share this |
| 4 | `<app data>/workspaces/presence` | no workspace configured yet |

Choosing the workspace root as the default is the whole reason this works
without new infrastructure: if two people can open the same package, they can
already read and write the same folder.

### Record

```json
{
  "version": 1,
  "session_id": "a17f3c9d2e01",
  "user": "alice",
  "host": "alice-thinkpad",
  "pid": 48213,
  "package": "diff_drive_2w",
  "file": "launch/sim.launch.py",
  "sim": true,
  "joined_at": 1753370000.12,
  "seen_at": 1753370042.87,
  "extra": {}
}
```

Records are written to a temp file and moved into place with `os.replace`, so a
reader either sees the whole previous record or the whole new one — never half
of one. Nothing is appended, nothing is shared-locked, so two peers writing at
the same instant cannot corrupt each other: they write different files.

### Lifecycle

| Step | Call | Effect |
| --- | --- | --- |
| Join | `POST /api/presence/join` | writes the record |
| Heartbeat | `POST /api/presence/heartbeat` | refreshes it, updates the fields you send |
| Look around | `GET /api/presence` | lists peers — **never creates a record** |
| Leave | `POST /api/presence/leave` | deletes the record |

Suggested heartbeat: **15 s**, TTL **45 s**. Two missed heartbeats still leave a
peer online, so a slow share does not make the list blink.

---

## The two things that make this non-trivial

### 1. Clocks disagree, so freshness comes from mtime

The obvious implementation compares `seen_at` (written by the peer) against
`now` (read by you). On a shared drive that is wrong: hosts drift, and a laptop
whose clock is five minutes behind would look permanently offline to everyone —
present, heartbeating, invisible.

Freshness is therefore taken from the record file's **mtime as the reading
machine sees it**. Both numbers then come from the same clock — the filesystem's
— so drift cancels out. `seen_at` is still stored and surfaced as
`clock_skew_s`, so the UI can *report* a badly-set clock instead of hiding the
person behind it.

### 2. A crashed IDE leaves a fresh-looking record

If the process dies, nothing deletes the record; it stays "online" until the TTL
expires. When the record claims **our own host**, the pid is checked directly,
so a crashed session drops out immediately instead of haunting the list for
another 45 seconds. A pid from another host is never second-guessed — it means
nothing in our process table. A recycled pid can only make a dead peer look
alive, which is the safe direction to be wrong in.

Long-abandoned records (older than `TTL × 10`, ~7.5 min) are removed by
`lappa presence reap`. Records that are merely *stale* are kept: a peer on a
laggy share is offline, not gone, and deleting the file would make them come
back as a brand-new session on the next heartbeat.

---

## Save conflicts

`PUT /api/files` now answers with whoever else has that file open:

```json
{
  "ok": true,
  "path": "launch/sim.launch.py",
  "conflicts": [{"user": "bob", "host": "bob-nuc", "session_id": "51bb0f7743aa", "age_s": 3.1}]
}
```

This is **advisory**. The save always happens; presence never takes a lock and
never blocks an edit. Existing clients that ignore the new field behave exactly
as before.

`GET /api/presence/file?path=...` answers the same question without writing
anything, so the IDE can show "bob is in this file" the moment it is opened.

---

## CLI

```bash
lappa presence list                    # who is here
lappa presence list --json --stale     # machine-readable, including expired records
lappa presence where launch/sim.launch.py
lappa presence session --user alice --hold 60   # join, heartbeat, leave on exit
lappa presence reap                    # drop records from long-dead sessions
lappa presence dir                     # which directory is actually being used
```

Two terminals on one machine are enough to see it work:

```bash
# terminal 1
LAPPA_PRESENCE_DIR=/tmp/lappa-presence lappa presence session --user alice \
  --package diff_drive_2w --file launch/sim.launch.py --hold 60
# terminal 2
LAPPA_PRESENCE_DIR=/tmp/lappa-presence lappa presence list
```

`session` leaves on Ctrl-C as well as on timeout, so a demo does not leave a
ghost peer behind.

---

## Failure modes

| Situation | Behaviour |
| --- | --- |
| Presence directory unreachable / read-only | `join` returns **503**; saving files and every other endpoint keep working |
| Share disappears mid-session | Heartbeats fail silently; peers see the record expire |
| Torn, empty, or foreign file in the directory | Skipped; the rest of the list is still returned |
| Someone drops `README.txt` in there | Ignored — only `peer-*.json` is read |
| Two peers write simultaneously | Different files; `os.replace` keeps each atomic |
| Peer's clock is minutes off | Still online, skew reported |
| IDE crashes | Same host: gone at once (pid check). Other host: gone at TTL |
| Session id containing `../` | Rejected outright — a record can never be written outside the directory |

---

## Deliberately not in scope

- **Not a lock.** Presence tells you somebody is there; it never stops you.
- **Not co-editing.** No OT, no CRDT, no character-level merge.
- **No lost-update protection yet.** `PUT /api/files` is still last-write-wins;
  presence only makes the collision *visible*. The natural next step is
  optimistic concurrency on the write endpoint (send the mtime/hash you loaded,
  get a **409** if it moved), which is a change to the file API rather than to
  presence and is best reviewed on its own.
- **Not a chat or notification channel.** `extra` exists for a client that wants
  to attach a status string, and nothing reads it.

## Privacy and scale

Records carry a user name, host name, pid and the relative path being edited, in
plain text, in a directory everyone in the workspace can read. That is the same
trust boundary as the workspace itself — anyone who can read the presence
directory can already read the code. `LAPPA_USER` overrides the OS user name for
anyone who would rather not publish it.

Listing costs one `stat` + one small read per peer, on a directory sized by the
number of people in the workspace. That is right for a team; it is not a design
for hundreds of concurrent peers, and it is not meant to be.
