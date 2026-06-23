# Plan (STUB): B-LS (Lighting Supervisor) — C++ example

> **STATUS: STUB.** Seed facts below. Expand from
> [`bacnet-profile-plan-template.md`](../../bacnet-profile-plan-template.md) after the
> sample plans ([B-LD](../../BACnetProfileExample-B-LD-CPP/docs/plan.md),
> [B-BC](../../BACnetProfileExample-B-BC-CPP/docs/plan.md)) are reviewed.

**Profile:** B-LS · **Family:** Annex L.11 (Lighting Controller) · **Role:** B
(with A-side write-out) · **Archetype:** Specialized-object · **Difficulty:** 4/5 ·
**Build wave:** 2 (builds on B-LD)

**Thesis:** a lighting supervisor — commands lighting in **other** devices via a
**Channel** object + **WriteGroup**, and runs lighting schedules. This example =
B-LD + Channel/WriteGroup + (read-only) Schedule.

## Required BIBBs (profiles.md L.11)
`DS-RP-B, DS-WP-A,B, DS-WG-E-B, DS-ALO-A; SCHED-E-B; DM-DDB-A,B, DM-DOB-B,
DM-DCC-B, (DM-TS-B or DM-UTC-B)`.

## Services to enable
- ReadProperty (1), WriteProperty (15), WriteGroup, DCC (17), TimeSync (24/25).

## Objects (baseline + )
- Channel 1 (`OBJECT_TYPE_CHANNEL`) — `List_Of_Object_Property_References`,
  `Channel_Number`, commandable Present_Value.
- Lighting Output 1 "Amber" (reuse F-LIGHT from B-LD).
- Schedule 1 + Calendar 1 (read-only — see gap).

## Shared features
- **DEFINE:** F-CHANNEL (Channel + WriteGroup), F-EXTWRITE (DS-WG-E-B external write
  dispatch — `CallbackChannelSendWritePropertyToRemote`, profiles.md S77),
  F-SCHED (read-only Schedule — see gap).
- **REUSE:** F-LIGHT (B-LD), F-OUTPUTS (B-SA), F-DCC (B-ASC), F-TIMESYNC (B-LD).

## Known stack gaps
- **SCHED-E-B needs the Schedule execution engine**, which the standard DLL lacks
  (B-AAC TODO §1) → serve a **read-only** Schedule object + `TODO.md`. Master plan
  §7 risk 1.
- Confirm `CallbackChannelSendWritePropertyToRemote` (DS-WG-E-B) is in the standard
  DLL (profiles.md: ✅ S77, 5 new gtests). DS-ALO-A initiate via
  `BACnetStack_SendWriteProperty` (B-OD pattern).

## Notes / open questions
- Build **after** B-LD (depends on F-LIGHT/F-TIMESYNC). The WriteGroup/Channel
  external-write is the genuinely new mechanism — spike it first.
