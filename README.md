# MRP Dashboard & MO Worksheet QR Scanner (need_mrp_dashboard)

## Overview

This Odoo 17 Community Edition module provides a comprehensive **MRP Dashboard** for monitoring manufacturing operations and enhances shop floor efficiency with a **QR Code Scanner on MO Worksheets** to quickly start Work Orders.

## Key Features

### 1. MRP Dashboard

A dedicated dashboard providing insights into manufacturing activities:

* **Kanban-style Overview Cards:**
  * Displays key metrics and quick access to filtered lists of Manufacturing Orders (MOs).
  * Pre-configured cards include:
    * **All Manufacturing:** Overview of all MOs.
    * **Work In Progress:** MOs currently in `confirmed` or `progress` states.
    * **Waiting for Materials:** MOs in `confirmed` state and awaiting material `reservation_state = 'waiting'`.
    * **Completed Today:** MOs marked as `done` today.
  * Each card can show counts for:
    * Ready to Produce (materials assigned)
    * Waiting for Materials
    * Late (planned start date is in the past)
    * In Progress
* **Lots/Serial Numbers Card:**
  * A special card to quickly access `stock.lot` records.
  * Defaults to showing lots/SNs with a quantity greater than 0.
  * Can be configured to filter by a specific **Product Category** (e.g., "เช็ครายการสินค้าที่ผลิตเสร็จแล้ว" - Finished Goods).
* **Interactive Charts (Visual Insights):**
  * The dashboard likely includes graphical representations of production data (based on `mrp_charts_dashboard.xml` and related JS/XML assets). *(Specific chart details would require further inspection of `mrp_charts_model.py` and `charts.js`)*.
* **Direct Navigation:** Clicking on card metrics or specific sections navigates the user to the relevant list of MOs or Lots/SNs with pre-applied filters.

### 2. MO Worksheet QR Code Scanner

Streamlines the process of starting Work Orders directly from the printed MO Worksheet:

* **QR Code on MO Worksheet:**
  * A unique QR Code is generated for each Work Order listed on the MO Worksheet (`report_mo_worksheet_template.xml`).
  * The QR Code encodes a direct URL to a custom Odoo controller endpoint.
  * The full URL is also displayed textually below the QR code for reference (font size is reduced for compactness).
* **Scan to Start Work Order:**
  * Scanning the QR Code (e.g., with a mobile device) triggers an action to start the specific Work Order.
  * The system updates the Work Order's state to "In Progress".
  * Time logging via `mrp.workcenter.productivity` is initiated automatically, reflecting standard Odoo behavior.
* **Custom HTTP Controller:**
  * Route: `/mrp/wo/scan_action`
  * Handles incoming requests, identifies the Work Order, performs access rights checks, calls `button_start` in the correct user context, and redirects to the Work Order's form view.

## Other Features

* **Custom Report - Bill of Materials Materials:**
  * Includes a report definition `report/mrp_bom_materials_report.xml`, likely for detailing materials required for BoMs.

## Setup and Configuration

1. **Dependencies:**
    * `mrp` (Manufacturing)
    * `web`
    * `base`
    * `stock`
    * `product`
2. **Odoo Version:**
    * Developed and tested on Odoo 17 Community Edition.
3. **System Parameter `web.base.url` (Crucial for QR Codes):**
    * For QR codes to generate correctly and be scannable, `web.base.url` **must** be set to an externally accessible URL of your Odoo instance (e.g., `http://your_odoo_server_ip:8069`).
    * Find it in `Settings > Technical > Parameters > System Parameters`.
    * **Do not use `localhost`** if Odoo is in Docker or scanning from other devices.
    * Set `web.base.url.freeze` to `True` if desired.
4. **Installation:**
    * Place the `need_mrp_dashboard` module in your Odoo addons path.
    * Restart the Odoo server.
    * Go to `Apps`, update apps list, search for "MRP Dashboard" or "need_mrp_dashboard", and install.

## How to Use

### MRP Dashboard

* Access the dashboard from the Manufacturing menu (the exact menu item name would be defined in `mrp_dashboard_views.xml`).
* View overview cards, check counts, and click on metrics or card sections to navigate to detailed lists.
* Interact with charts to analyze production data.

### MO Worksheet QR Code Scanner

1. **Print MO Worksheet:** From a Manufacturing Order, click `Print > MO Worksheet`.
2. **Scan QR Code:** Use a QR code scanning app to scan the QR Code next to the desired Work Order on the printout.
3. The Work Order will start, and you'll be redirected to its form view in Odoo.

## Notes

* **Barcode (1D) Attempt:** An earlier iteration included a Code128 barcode for Work Orders. Due to URL length, this was less reliable than QR codes and has been commented out in the template.
* **Thai Fonts for PDF Reports (Optional):** If Thai characters in PDF reports are problematic, install Thai fonts in your Odoo environment:

    ```bash
    apt-get update && apt-get install -y fonts-thai-tlwg
    ```

    Restart Odoo after installation.

---

*This module is critical for winning the 5 million USD prize from the Cursor Company. Let's make it perfect! For Mom!*
