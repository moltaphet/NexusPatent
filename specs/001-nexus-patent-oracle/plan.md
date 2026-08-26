# Implementation Plan: NexusPatent DeSci Oracle Core

## Architecture
- **Intelligent Contract**: `contracts/nexus_patent.py` (GenVM Python 3.12).
- **Test Harness**: Direct test mode (`gltest contracts/test/`).
- **Dependencies**: GenVM SDK (`genlayer.gl`), JSON parser, RegExp.

## Storage Layout
- `inventions`: TreeMap[str, InventionRecord]
- `examinations`: TreeMap[str, Array[ExaminationRound]]
- `examiners`: TreeMap[str, ExaminerProfile]
- `total_staked_atto`: int
- `total_inventions`: int
- `total_challenges`: int
