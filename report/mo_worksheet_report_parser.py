# File: need_mrp_dashboard/report/mo_worksheet_report_parser.py
from odoo import api, models

class MoWorksheetReportCustomParser(models.AbstractModel):
    _name = 'report.need_mrp_dashboard.report_mo_worksheet_template' # Matches your report_name in XML
    _description = 'Parser for MO Worksheet to add QR Code URL data for Work Orders'

    @api.model
    def _get_report_values(self, docids, data=None):
        # docids are the IDs of the mrp.production records being printed
        docs = self.env['mrp.production'].browse(docids)
        
        # Get the web.base.url system parameter
        web_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        # This dictionary is passed to the QWeb template
        return {
            'doc_ids': docids, # Standard, Odoo expects this
            'doc_model': 'mrp.production', # Standard, Odoo expects this
            'docs': docs, # Standard, Odoo expects this (the records themselves)
            'web_base_url': web_base_url, # Our custom value for QR code URLs
            # You can add more custom data here if needed for the template
        } 