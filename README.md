# Odoo 17 Need MRP Dashboard Module

## 📊 ภาพรวม (Overview)

โมดูลนี้เป็น Custom Dashboard สำหรับ Odoo 17 Community Edition ที่แสดงข้อมูลภาพรวมของการผลิต (MRP) และให้ทางลัดไปยังข้อมูลสำคัญ:

- **มุมมอง Kanban Dashboard:** แสดงสถานะการผลิตผ่านการ์ดต่างๆ เช่น:
    - คำสั่งผลิตทั้งหมด (All Manufacturing)
    - กำลังดำเนินการ (Work In Progress)
    - รอวัตถุดิบ (Waiting for Materials)
    - เสร็จสิ้นวันนี้ (Completed Today)
    - ล็อต/ซีเรียลนัมเบอร์ (Lots/Serial Numbers): การ์ดพิเศษที่เชื่อมต่อไปยังรายการ Lot/SN ทั้งหมด โดยมีการกรองข้อมูลเริ่มต้น (เฉพาะ Category ที่กำหนดและมีจำนวนคงเหลือ)
- **รายงาน:** อาจรวมถึงรายงานอื่นๆ เช่น รายการวัสดุที่ต้องสั่งซื้อ (หากมี)
- **กราฟ:** อาจรวมถึงกราฟแสดงข้อมูลการผลิต (หากมี)

## 📁 โครงสร้างไฟล์ (File Structure)

```bash
need_mrp_dashboard/
├── models/                 # Python Models
│   ├── __init__.py
│   ├── mrp_dashboard.py     # โมเดลหลักสำหรับข้อมูล Dashboard Kanban
│   └── ...                 # (อาจมีโมเดลอื่นๆ เช่น mrp_charts_model)
│
├── views/                  # XML Views
│   ├── mrp_dashboard_views.xml # มุมมอง Kanban Dashboard หลัก
│   ├── stock_lot_actions.xml   # Action สำหรับเปิดหน้า Lot/SN พร้อม Filter
│   └── ...                 # (อาจมี View อื่นๆ เช่น mrp_charts_dashboard.xml)
│
├── data/                   # Data Files
│   └── mrp_dashboard_data.xml # ข้อมูลเริ่มต้นสำหรับ Kanban Cards
│
├── report/                 # Report Definitions
│   └── ...                 # (เช่น mrp_bom_materials_report.xml)
│
├── security/               # Security Files
│   └── ir.model.access.csv
│   └── mrp_security.xml
│
├── static/                 # Static Assets (JS, CSS, XML Templates)
│   ├── src/
│   │   ├── js/
│   │   │   └── charts.js    # (ถ้ามี Logic ของ Chart)
│   │   └── xml/
│   │       └── chart_templates.xml # (ถ้ามี Template ของ Chart)
│   └── ...
│
├── __init__.py             # Root init file
├── __manifest__.py         # Module manifest
└── README.md               # Documentation (ไฟล์นี้)
```
*(หมายเหตุ: โครงสร้างไฟล์อาจมีการเปลี่ยนแปลงตามการพัฒนา)*

## 🛠 การพัฒนา (Development)

โมดูลนี้พัฒนาด้วย:

- Odoo 17 Community Framework
- Python 3.10+
- PostgreSQL 12+
- XML (Views, Data, Actions)
- JavaScript (สำหรับฟีเจอร์ Dynamic เช่น กราฟ)
- QWeb Reports (สำหรับรายงาน PDF)

### **พัฒนาโดย แอ๋ม (Sarawut Khantiyoo)**

- Website: `https://erp.needshopping.co`
- Email: `sarawut.khan@hotmail.com`
