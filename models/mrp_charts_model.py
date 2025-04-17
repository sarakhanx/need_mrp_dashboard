from datetime import date, timedelta
from odoo import models, fields, api

class MoDashboard(models.Model):
    _name = 'custom.mo.dashboard'
    _description = 'MO Status Count by Date'

    date = fields.Date(string="Date")
    draft = fields.Integer(string="Draft")
    confirmed = fields.Integer(string="Confirmed")
    progress = fields.Integer(string="In Progress")
    done = fields.Integer(string="Done")
    cancel = fields.Integer(string="Cancelled")

    @api.model
    def generate_data(self, start_date, end_date):
        # Convert string dates to date objects if needed
        if isinstance(start_date, str):
            start_date = fields.Date.from_string(start_date)
        if isinstance(end_date, str):
            end_date = fields.Date.from_string(end_date)

        # Delete existing records in the date range
        self.search([
            ('date', '>=', start_date),
            ('date', '<=', end_date)
        ]).unlink()

        # Generate data for each day in the range
        current_date = start_date
        while current_date <= end_date:
            domain = [
                ('create_date', '>=', current_date),
                ('create_date', '<', current_date + timedelta(days=1))
            ]
            mos = self.env['mrp.production'].search(domain)

            state_counts = {
                'draft': 0,
                'confirmed': 0,
                'progress': 0,
                'done': 0,
                'cancel': 0,
            }
            for mo in mos:
                if mo.state in state_counts:
                    state_counts[mo.state] += 1

            self.create({
                'date': current_date,
                'draft': state_counts['draft'],
                'confirmed': state_counts['confirmed'],
                'progress': state_counts['progress'],
                'done': state_counts['done'],
                'cancel': state_counts['cancel'],
            })

            current_date += timedelta(days=1)
