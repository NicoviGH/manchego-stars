# Test fixtures

`timeline-*.jsonl`: filed traces (`references/sim/vanilla/<sha>/traces/`, gitignored) cut to the
events `timeline.lua` reads, for `test_timeline.lua` (#765). Each is one attempt:

| File | Run tag | Game |
|---|---|---|
| `timeline-ch14-x741c-a1.jsonl` | `x741c-b640e-cs-s4003` | vanilla Ch14 s4003 attempt 1 |
| `timeline-ch10-x741d-a1.jsonl` | `x741d-b640e-cs-s4002` | vanilla Ch10 s4002 attempt 1 |
| `timeline-ch10-fx730a-a1.jsonl` | `fx730a-b640e-cs-s4002` | vanilla Ch10 s4002 attempt 1 |

Cut with:

```sh
gzcat <trace>.jsonl.gz | jq -c 'select(.t=="phase" or .t=="act" or .t=="fell" or .t=="drop"
  or .t=="theft" or .t=="end" or (.t=="event" and .kind=="arrive"))
  | if .t=="phase" then {t,turn,phase,units:[.units[]|{id,charId,classId,faction,x,y,hp}
      + (if .fogged then {fogged} else {} end)]}
    elif .t=="act" then {t,turn,phase,id,to,fell}
    elif .t=="end" then {t,turn,record:(.record|{arrivals_seen,enemies_seen,explore,deaths,
      missed_recruits})}
    else . end'
```
