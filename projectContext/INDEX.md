# Xpert-ERP — Garage Management System

Project context, conception, and execution plan.

This folder contains the complete planning and design corpus for the Xpert-ERP Garage / Dealer Management System (GMS/DMS). Every document in this folder is a working document and should be kept in sync with the codebase as it evolves.

---

## Reference inputs

These are the raw inputs that drove the planning here. Treat them as the source of truth for business requirements; the planning documents below are derived artefacts.

- [Context.md](Context.md) — engineering rules of the project (logging, no hard-coded values, git conventions, documentation requirements).
- [ExplainProject.txt](ExplainProject.txt) — the full project brief, modules, workflows, and business flows in English.
- [Cahier_des_Charges_Garage_Complet_Dev_FINAL UPDATE.xml](Cahier_des_Charges_Garage_Complet_Dev_FINAL%20UPDATE.xml) — formal Cahier des Charges (French), Word XML format.
- [Cahier_des_Charges_Gestion_Garage_software.docx](Cahier_des_Charges_Gestion_Garage_software.docx) — the same Cahier des Charges as a `.docx` artefact.

---

## Planning corpus

Read in this order on first pass:

1. [00_PLAN_OF_EXECUTION.md](00_PLAN_OF_EXECUTION.md) — phased delivery roadmap and timeline.
2. [01_SOFTWARE_CONCEPTION.md](01_SOFTWARE_CONCEPTION.md) — vision, scope, design philosophy, non-functional requirements.
3. [02_MILESTONES.md](02_MILESTONES.md) — per-milestone scope, deliverables, exit criteria, effort estimates.
4. [03_ARCHITECTURE.md](03_ARCHITECTURE.md) — layered architecture, components, deployment topology.
5. [04_DATABASE_DESIGN.md](04_DATABASE_DESIGN.md) — entity-relationship model and conventions.
6. [05_API_DESIGN.md](05_API_DESIGN.md) — REST conventions, versioning, contract patterns.
7. [06_RBAC_DESIGN.md](06_RBAC_DESIGN.md) — roles, permissions, and security model.
8. [07_MODULE_BREAKDOWN.md](07_MODULE_BREAKDOWN.md) — per-module specifications.
9. [08_TECH_STACK.md](08_TECH_STACK.md) — technology choices and library shortlists with pros and cons.
10. [09_TESTING_STRATEGY.md](09_TESTING_STRATEGY.md) — unit, integration, end-to-end, and acceptance tests.
11. [10_DEPLOYMENT_DEVOPS.md](10_DEPLOYMENT_DEVOPS.md) — environments, CI/CD, backups, observability.
12. [11_RISK_REGISTER.md](11_RISK_REGISTER.md) — risks, likelihood, impact, mitigation.
13. [12_GLOSSARY.md](12_GLOSSARY.md) — domain and technical glossary.

---

## Diagrams

All diagrams are written in Mermaid. They render natively on GitHub, VSCode (with the Markdown Preview Mermaid Support extension), and most modern markdown viewers.

- [diagrams/system/](diagrams/system/) — system context, container, component, and deployment diagrams (C4 inspired).
- [diagrams/data/](diagrams/data/) — entity-relationship diagrams.
- [diagrams/flowcharts/](diagrams/flowcharts/) — one flowchart per business workflow.
- [diagrams/sequence/](diagrams/sequence/) — sequence diagrams for the critical end-to-end use cases.
- [diagrams/state/](diagrams/state/) — state machines for Repair Order, Invoice, Quotation, Purchase Order.

---

## Conventions used in this folder

- All dates and durations are absolute. Relative dates are converted to ISO 8601 (`YYYY-MM-DD`).
- Effort estimates are in person-weeks (PW), assuming one senior full-stack engineer at full capacity. Halve for two engineers in parallel where parallelizable; see [02_MILESTONES.md](02_MILESTONES.md) for the parallelism matrix.
- All identifiers in design documents use snake_case for tables/columns and camelCase for API fields.
- No emojis are used anywhere in planning documents or generated code, per [Context.md](Context.md).
- No hard-coded values appear in design specs; configurable thresholds are flagged as `CFG_*` and listed in [01_SOFTWARE_CONCEPTION.md](01_SOFTWARE_CONCEPTION.md).
