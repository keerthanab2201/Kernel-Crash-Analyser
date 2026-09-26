# Cellular study protocol (not executed)

This is a separate extension for the WTE role. No cellular diagnosis accuracy is
claimed. `cellular-timeline` recognizes selected UE/RAN event messages and correlates
timestamps; it does not infer a cause from a rejection alone.

Use a pinned UERANSIM build and compatible Open5GS deployment in a disposable Linux
lab. Record component commits, configuration hashes, clock synchronization, and one
UE/scenario per captured bundle. The radio interface is simulated; this study does
not measure physical-layer RF behavior or Apple modem performance.

Proposed controlled cases:

| Scenario | Controlled change | Evidence to collect |
|---|---|---|
| Healthy reference | Known matching subscriber/network config | Registration/session success plus user-plane connectivity test |
| Subscriber mismatch | One subscriber provisioning field changed | UE rejection and corresponding core-side decision |
| Session configuration mismatch | One DNN/slice setting changed | Successful registration and session rejection with core evidence |
| RAN/core reachability | Isolate the lab RAN from its core endpoint | RAN transport/NG setup events and connectivity checks |

Restore the healthy baseline between experiments. Retain failure and recovery
captures. Do not assume a particular configuration change always yields the same
message; verify the observed stage and exact cause for your pinned versions.

```
python -m src.cli cellular-timeline captures/ue.log captures/gnb.log captures/amf.log --output timeline.json
```

The current adapter recognizes bracketed ISO-like timestamps typical of UERANSIM.
Other formats remain untimestamped or unmatched; inspect those counts and implement
version-specific adapters before comparing results. Cross-log UE correlation and
automated Open5GS provisioning are not implemented.

Sources:
- https://github.com/aligungr/UERANSIM
- https://github.com/aligungr/UERANSIM/wiki/Feature-Set
- https://open5gs.org/open5gs/docs/

Review upstream software licenses before bundling binaries or configs; no upstream
source, credentials, or copied production captures are included here.
