# Diagrams

All diagrams are written in Mermaid. They render natively on GitHub, VSCode (with the Markdown Preview Mermaid Support extension), and most modern markdown viewers.

## System diagrams (C4-inspired)

- [system/c1_context.md](system/c1_context.md) — System context (Level 1).
- [system/c2_container.md](system/c2_container.md) — Container view (Level 2).
- [system/c3_backend_components.md](system/c3_backend_components.md) — Backend component view (Level 3).
- [system/c3_frontend_components.md](system/c3_frontend_components.md) — Frontend component view (Level 3).
- [system/c4_deployment.md](system/c4_deployment.md) — Deployment view (Level 4).
- [system/cross_cutting_request_flow.md](system/cross_cutting_request_flow.md) — End-to-end request flow with logging and audit.

## Data diagrams (ERD)

- [data/erd_top_level.md](data/erd_top_level.md) — Top-level ERD across modules.
- [data/erd_identity_rbac.md](data/erd_identity_rbac.md) — Identity, roles, permissions.
- [data/erd_customer_vehicle.md](data/erd_customer_vehicle.md) — Customer and vehicle.
- [data/erd_repair_order.md](data/erd_repair_order.md) — Repair Order and inspection.
- [data/erd_inventory.md](data/erd_inventory.md) — Parts, stock movements, supplier prices.
- [data/erd_quotation_invoice.md](data/erd_quotation_invoice.md) — Quotation, invoice, credit note.
- [data/erd_payments_cash.md](data/erd_payments_cash.md) — Payment, deposit, cash session.
- [data/erd_supplier.md](data/erd_supplier.md) — Supplier, PO, reception, supplier invoice.
- [data/erd_notifications.md](data/erd_notifications.md) — Notification and templates.
- [data/erd_documents_ocr.md](data/erd_documents_ocr.md) — Document and OCR extraction.
- [data/erd_audit.md](data/erd_audit.md) — Audit log.

## State machines

- [state/repair_order.md](state/repair_order.md) — Repair Order lifecycle.
- [state/quotation.md](state/quotation.md) — Quotation lifecycle.
- [state/invoice.md](state/invoice.md) — Invoice lifecycle.
- [state/purchase_order.md](state/purchase_order.md) — Purchase Order lifecycle.
- [state/cash_session.md](state/cash_session.md) — Cash session lifecycle.
- [state/notification.md](state/notification.md) — Notification delivery lifecycle.
- [state/ocr_extraction.md](state/ocr_extraction.md) — OCR extraction lifecycle.

## Flowcharts (one per business workflow)

Core flow:

- [flowcharts/wf_main_business_flow.md](flowcharts/wf_main_business_flow.md)
- [flowcharts/wf_vehicle_reception.md](flowcharts/wf_vehicle_reception.md)
- [flowcharts/wf_standard_repair_invoicing.md](flowcharts/wf_standard_repair_invoicing.md)
- [flowcharts/wf_quick_service.md](flowcharts/wf_quick_service.md)
- [flowcharts/wf_digital_inspection.md](flowcharts/wf_digital_inspection.md)
- [flowcharts/wf_media_management.md](flowcharts/wf_media_management.md)
- [flowcharts/wf_additional_repair_discovery.md](flowcharts/wf_additional_repair_discovery.md)
- [flowcharts/wf_comeback_and_failure.md](flowcharts/wf_comeback_and_failure.md)
- [flowcharts/wf_workshop_performance.md](flowcharts/wf_workshop_performance.md)
- [flowcharts/wf_vehicle_history.md](flowcharts/wf_vehicle_history.md)

Inventory and supplier:

- [flowcharts/wf_parts_inventory.md](flowcharts/wf_parts_inventory.md)
- [flowcharts/wf_part_reservation.md](flowcharts/wf_part_reservation.md)
- [flowcharts/wf_part_returns.md](flowcharts/wf_part_returns.md)
- [flowcharts/wf_low_stock_alert.md](flowcharts/wf_low_stock_alert.md)
- [flowcharts/wf_supplier_purchase_request.md](flowcharts/wf_supplier_purchase_request.md)
- [flowcharts/wf_supplier_price_comparison.md](flowcharts/wf_supplier_price_comparison.md)
- [flowcharts/wf_purchase_order_reception.md](flowcharts/wf_purchase_order_reception.md)
- [flowcharts/wf_supplier_invoice.md](flowcharts/wf_supplier_invoice.md)
- [flowcharts/wf_purchase_supplier_overview.md](flowcharts/wf_purchase_supplier_overview.md)

Commercial and finance:

- [flowcharts/wf_quotation_to_invoice.md](flowcharts/wf_quotation_to_invoice.md)
- [flowcharts/wf_customer_credit_limit.md](flowcharts/wf_customer_credit_limit.md)
- [flowcharts/wf_partial_payment.md](flowcharts/wf_partial_payment.md)
- [flowcharts/wf_advance_payment.md](flowcharts/wf_advance_payment.md)
- [flowcharts/wf_cash_register.md](flowcharts/wf_cash_register.md)
- [flowcharts/wf_cash_register_closing.md](flowcharts/wf_cash_register_closing.md)
- [flowcharts/wf_invoice_cancellation.md](flowcharts/wf_invoice_cancellation.md)
- [flowcharts/wf_customer_refund.md](flowcharts/wf_customer_refund.md)
- [flowcharts/wf_margin_calculation.md](flowcharts/wf_margin_calculation.md)
- [flowcharts/wf_fleet_billing.md](flowcharts/wf_fleet_billing.md)

CRM and notifications:

- [flowcharts/wf_customer_account_followup.md](flowcharts/wf_customer_account_followup.md)
- [flowcharts/wf_customer_segmentation.md](flowcharts/wf_customer_segmentation.md)
- [flowcharts/wf_customer_loyalty.md](flowcharts/wf_customer_loyalty.md)
- [flowcharts/wf_customer_notification.md](flowcharts/wf_customer_notification.md)

Documents, admin, reporting:

- [flowcharts/wf_document_generation.md](flowcharts/wf_document_generation.md)
- [flowcharts/wf_document_management.md](flowcharts/wf_document_management.md)
- [flowcharts/wf_accounting_export.md](flowcharts/wf_accounting_export.md)
- [flowcharts/wf_analytics_reporting.md](flowcharts/wf_analytics_reporting.md)
- [flowcharts/wf_admin_security.md](flowcharts/wf_admin_security.md)
- [flowcharts/wf_audit_traceability.md](flowcharts/wf_audit_traceability.md)

## Sequence diagrams

- [sequence/seq_login_and_refresh.md](sequence/seq_login_and_refresh.md)
- [sequence/seq_create_repair_order.md](sequence/seq_create_repair_order.md)
- [sequence/seq_quote_to_invoice.md](sequence/seq_quote_to_invoice.md)
- [sequence/seq_record_payment.md](sequence/seq_record_payment.md)
- [sequence/seq_cash_session_close.md](sequence/seq_cash_session_close.md)
- [sequence/seq_purchase_order_reception.md](sequence/seq_purchase_order_reception.md)
- [sequence/seq_ocr_pipeline.md](sequence/seq_ocr_pipeline.md)
- [sequence/seq_send_notification.md](sequence/seq_send_notification.md)
- [sequence/seq_kpi_refresh.md](sequence/seq_kpi_refresh.md)
