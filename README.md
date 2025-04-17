# Odoo 17 Need MRP Dashboard Module

## 📊 ภาพรวม

โมดูลนี้เป็น Custom Dashboard สำหรับ Odoo 17 Community Edition ที่แสดงข้อมูล MRP และรายงานการผลิตสำหรับ:

- รายงานวัสดุที่ต้องสั่งซื้อ (Materials Purchase List)
- กราฟแสดงข้อมูลการผลิต (Production Line Chart)
- การติดตามการผลิตแบบ Real-time

## 📁 โครงสร้างไฟล์

```bash
need_mrp_dashboard/
├── models/
│   ├── __init__.py                # Import models
│   └── mrp_production.py          # โมเดลสำหรับการผลิต
│
├── report/
│   └── mrp_bom_materials_report.xml  # รายงานวัสดุที่ต้องสั่งซื้อ
│
├── views/
│   └── mrp_dashboard_views.xml    # มุมมองของ Dashboard
│
├── security/
│   └── ir.model.access.csv        # กำหนดสิทธิ์การเข้าถึง
│
├── static/
│   └── src/
│       └── js/
│           └── dashboard.js        # Logic ของ Dashboard
│
├── __init__.py                    # Root init file
├── __manifest__.py                # Module manifest
└── README.md                      # Documentation
```

## 🛠 การพัฒนา

โมดูลนี้พัฒนาด้วย:

- Odoo 17 Community Framework
- Python 3.10+
- PostgreSQL 12+
- QWeb Reports

### **พัฒนาโดย แอ๋ม (Sarawut Khantiyoo)**

- Website: `https://erp.needshopping.co`
- Email: `sarawut.khan@hotmail.com`
# need_mrp_dashboard
