# MRP Dashboard Module

## 📋 Overview
Custom Manufacturing Resource Planning (MRP) Dashboard module for Odoo 17 Community Edition. This module provides comprehensive manufacturing analytics, reporting, and workflow enhancements.

---

## 🎯 Features & File Locations

### 1. **MRP Dashboard with KPI Cards**
- **What**: Main dashboard showing manufacturing statistics with clickable cards
- **Location**: `models/mrp_dashboard.py`
- **View**: `views/mrp_dashboard_views.xml`
- **Features**:
  - Ready to Produce count
  - Waiting for Materials count  
  - Late Operations count
  - In Progress count

### 2. **Charts Dashboard**
- **What**: Manufacturing analytics with interactive charts
- **Location**: `models/mrp_charts_model.py`
- **View**: `views/mrp_charts_dashboard.xml`
- **JavaScript**: `static/src/js/charts.js`
- **Template**: `static/src/xml/chart_templates.xml`

### 3. **BOM Materials Report with Print Tracking**
- **What**: Detailed BOM materials report with automatic print status tracking
- **Report Parser**: `report/mrp_bom_materials_parser.py`
- **Report Definition**: `report/mrp_bom_materials_report.xml`
- **Print Tracking Model**: `models/mrp_production_auto_close.py` (lines 45-70)

### 4. **Size Label Report (4x1 Layout)**
- **What**: Product labels with barcodes in 4 vertical labels per page
- **Report Template**: `report/size_label_template.xml`
- **Report Definition**: `report/size_label_report.xml`
- **Features**: Barcode generation, product details, category info

### 5. **Manufacturing Order Enhancements**
- **What**: Enhanced MO form and list views with print tracking
- **Location**: `views/mrp_production_inherit.xml`
- **Features**:
  - Print status toggle button
  - Smart button showing print date
  - Print info section
  - List view status indicator

### 6. **Workorder Dashboard**
- **What**: Work order management and tracking
- **Location**: `models/mrp_workorder_dashboard.py`
- **View**: `views/mrp_workorder_dashboard_views.xml`
- **Controller**: `controllers/workorder_controller.py`

### 7. **Operation Dashboard**
- **What**: Manufacturing operations overview
- **Location**: `models/mrp_operation_dashboard.py`
- **View**: `views/mrp_operation_dashboard_views.xml`

### 8. **Material Overview**
- **What**: Material requirements and availability tracking
- **Location**: `models/mrp_material_overview.py`

### 9. **Auto Close Production**
- **What**: Automatic production order closing functionality
- **Location**: `models/mrp_production_auto_close.py`
- **Data**: `data/mrp_auto_close_data.xml`

---

## 📁 File Structure Reference

### **Models** (`models/`)
| File | Purpose |
|------|---------|
| `mrp_dashboard.py` | Main dashboard KPI calculations |
| `mrp_charts_model.py` | Charts data preparation |
| `mrp_production_auto_close.py` | Print tracking & auto-close logic |
| `mrp_workorder_dashboard.py` | Workorder management |
| `mrp_operation_dashboard.py` | Operations overview |
| `mrp_material_overview.py` | Material tracking |
| `mrp_bom_report.py` | BOM reporting logic |

### **Views** (`views/`)
| File | Purpose |
|------|---------|
| `mrp_dashboard_views.xml` | Main dashboard interface |
| `mrp_charts_dashboard.xml` | Charts dashboard layout |
| `mrp_production_inherit.xml` | Enhanced MO forms & lists |
| `mrp_workorder_dashboard_views.xml` | Workorder interfaces |
| `mrp_operation_dashboard_views.xml` | Operations interfaces |

### **Reports** (`report/`)
| File | Purpose |
|------|---------|
| `mrp_bom_materials_parser.py` | BOM report logic & print tracking |
| `mrp_bom_materials_report.xml` | BOM report definition |
| `size_label_template.xml` | Product label template |
| `size_label_report.xml` | Product label report definition |
| `mo_worksheet_report_parser.py` | MO worksheet logic |
| `mo_worksheet_report.xml` | MO worksheet report |

### **Static Assets** (`static/src/`)
| File | Purpose |
|------|---------|
| `css/dashboard_styles.css` | Dashboard & toggle styling |
| `js/charts.js` | Chart.js integration |
| `xml/chart_templates.xml` | Chart QWeb templates |

### **Controllers** (`controllers/`)
| File | Purpose |
|------|---------|
| `workorder_controller.py` | Workorder web endpoints |

### **Data** (`data/`)
| File | Purpose |
|------|---------|
| `mrp_dashboard_data.xml` | Dashboard menu items |
| `mrp_auto_close_data.xml` | Auto-close configurations |

### **Security** (`security/`)
| File | Purpose |
|------|---------|
| `ir.model.access.csv` | Model access permissions |
| `mrp_security.xml` | Security groups & rules |

---

## 🔧 Key Customizations

### **Print Status Tracking**
- **Files**: `models/mrp_production_auto_close.py`, `views/mrp_production_inherit.xml`
- **Features**: Auto-marking, user tracking, date logging
- **Visual**: Toggle buttons, status indicators, smart buttons

### **Dashboard KPIs**
- **Files**: `models/mrp_dashboard.py`
- **Calculations**: 
  - Waiting for Materials: `reservation_state = 'waiting'`
  - Late Operations: `date_start < now()`
  - In Progress: `state in ['progress', 'to_close']`

### **Report Enhancements**
- **BOM Materials**: Auto print tracking in `mrp_bom_materials_parser.py`
- **Size Labels**: 4x1 vertical layout with barcodes
- **Styling**: Custom CSS for professional appearance

---

## 🎨 UI Enhancements

### **Toggle Buttons**
- **Location**: `static/src/css/dashboard_styles.css`
- **Features**: Green/red indicators, muted text labels
- **Views**: Both list and form views

### **Dashboard Cards**
- **Styling**: Hover effects, shadows, responsive design
- **Colors**: Professional color scheme
- **Layout**: Grid-based responsive layout

---

## 📊 Reports Available

1. **BOM Materials Report** - Material requirements with print tracking
2. **Size Label (4x1)** - Product labels with barcodes
3. **MO Worksheet** - Manufacturing order worksheets

---

## 🔍 Quick Reference

**Need to modify dashboard KPIs?** → `models/mrp_dashboard.py`

**Need to change toggle button appearance?** → `static/src/css/dashboard_styles.css`

**Need to modify print tracking logic?** → `models/mrp_production_auto_close.py`

**Need to update MO form layout?** → `views/mrp_production_inherit.xml`

**Need to modify size label layout?** → `report/size_label_template.xml`

**Need to add new charts?** → `models/mrp_charts_model.py` + `static/src/js/charts.js`

---

*This module is designed for Odoo 17 Community Edition and provides comprehensive manufacturing management enhancements.*
