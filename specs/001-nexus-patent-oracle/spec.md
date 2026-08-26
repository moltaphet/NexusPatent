# Feature Specification: NexusPatent DeSci Oracle Core

## Overview
NexusPatent is an intelligent contract protocol on GenLayer that audits invention claims, crawls prior-art across global literature (Google Patents, USPTO, arXiv), and determines patentability via Multi-LLM Quorum consensus.

## Functional Requirements
- **FR-001: Invention Registration**: Register new invention commitments with category, claimed valuation, and abstract.
- **FR-002: Examiner Staking**: Examiners stake GEN collateral to submit technical evaluation proofs.
- **FR-003: Dual-Engine Audit**: Crawls Web2 registries and runs Multi-LLM consensus to compute Novelty, Inventive Step, and Collision scores.
- **FR-004: Invalidation Challenge**: Third-party challengers dispute verdicts with 3 GEN bond and prior-art citations.
- **FR-005: Fractional Licensing Approval**: Verified inventions issue licensing shares with capped supply.
