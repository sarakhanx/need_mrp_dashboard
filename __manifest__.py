{
    'name': 'MRP Dashboard',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Dashboard for Manufacturing Operations',
    'description': """
        This module adds a dashboard view to the Manufacturing (MRP) module,
        providing an overview of manufacturing operations similar to the inventory dashboard.
    """,
    'depends': ['mrp', 'web', 'base', 'stock', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'security/mrp_security.xml',
        'views/mrp_dashboard_views.xml',
        'views/mrp_production_inherit.xml',
        'data/mrp_dashboard_data.xml',
        'data/mrp_auto_close_data.xml',
        'views/mrp_operation_dashboard_views.xml',
        'views/mrp_workorder_dashboard_views.xml',
        'views/mrp_charts_dashboard.xml',
        'views/scan_error_template.xml',
        'views/scan_success_template.xml',
        'report/mrp_bom_materials_report.xml',
        'report/mo_worksheet_report.xml',
        'report/mo_worksheet_template.xml',
        'report/size_label_report.xml',
        'report/size_label_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Custom CSS files
            'need_mrp_dashboard/static/src/css/dashboard_styles.css',
            'need_mrp_dashboard/static/src/css/delivery_hierarchy.css',
            # Custom JS files
            'need_mrp_dashboard/static/src/js/charts.js',
            'need_mrp_dashboard/static/src/js/delivery_hierarchy_widget.js',
            # XML templates for backend
            'need_mrp_dashboard/static/src/xml/chart_templates.xml',
            'need_mrp_dashboard/static/src/xml/delivery_hierarchy_template.xml',
        ],
        'web.report_assets_common': [
            'need_mrp_dashboard/static/src/css/report_styles.css',
        ],
    },

    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'external_dependencies': {
        'python': ['xlsxwriter'],
    },
} 