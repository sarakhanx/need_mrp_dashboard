from odoo import models, fields, api, _
from datetime import datetime, timedelta

class MrpDashboard(models.Model):
    _name = 'mrp.dashboard'
    _description = 'สรุปการผลิตทั้งหมด'

    name = fields.Char('Name', required=True)
    color = fields.Integer('Color Index')
    card_type = fields.Selection([
        ('overview', 'Overview'), 
        ('lots', 'Lots/Serial Numbers')
        ], string='Card Type', default='overview', required=True)
    product_category_id = fields.Many2one(
        'product.category', 
        string='Target Product Category', 
        help="Specify the category for the 'Lots/Serial Numbers' card type.")
    
    # Production Orders Counts
    count_mo_ready = fields.Integer(compute='_compute_mo_count', string='Ready to Produce')
    count_mo_waiting = fields.Integer(compute='_compute_mo_count', string='Waiting for Materials')
    count_mo_late = fields.Integer(compute='_compute_mo_count', string='Late')
    count_mo_in_progress = fields.Integer(compute='_compute_mo_count', string='In Progress')

    def _get_mo_domain(self):
        # Get domain based on dashboard type
        if self.name == 'All Manufacturing':
            return []
        elif self.name == 'Work In Progress':
            return [('state', 'in', ['confirmed', 'progress'])]
        elif self.name == 'Waiting for Materials':
            return [('state', '=', 'confirmed'), ('reservation_state', '=', 'waiting')]
        elif self.name == 'Completed Today':
            today_start = datetime.now().replace(hour=0, minute=0, second=0)
            today_end = datetime.now().replace(hour=23, minute=59, second=59)
            return [('state', '=', 'done'), ('date_finished', '>=', today_start), ('date_finished', '<=', today_end)]
        return []

    @api.depends('name')
    def _compute_mo_count(self):
        for record in self:
            base_domain = record._get_mo_domain()
            
            if record.name == 'Completed Today':
                # For Completed Today, all counts should show the same completed orders
                record.count_mo_ready = self.env['mrp.production'].search_count(base_domain)
                record.count_mo_waiting = record.count_mo_ready
                record.count_mo_late = record.count_mo_ready
                record.count_mo_in_progress = record.count_mo_ready
            else:
                # Ready Manufacturing Orders
                ready_domain = base_domain + [
                    ('state', 'in', ['confirmed', 'planned', 'draft']),
                    ('reservation_state', '=', 'assigned')
                ]
                record.count_mo_ready = self.env['mrp.production'].search_count(ready_domain)
                
                # Waiting Manufacturing Orders
                waiting_domain = base_domain + [
                    ('state', 'in', ['confirmed', 'planned', 'draft']),
                    ('reservation_state', '=', 'waiting')
                ]
                record.count_mo_waiting = self.env['mrp.production'].search_count(waiting_domain)
                
                # Late Manufacturing Orders
                late_domain = base_domain + [
                    ('state', 'in', ['confirmed', 'planned', 'progress', 'to_close', 'draft']),
                    ('date_start', '<', fields.Datetime.now())
                ]
                record.count_mo_late = self.env['mrp.production'].search_count(late_domain)

                # In Progress Manufacturing Orders
                in_progress_domain = base_domain + [
                    ('state', 'in', ['progress', 'to_close'])
                ]
                record.count_mo_in_progress = self.env['mrp.production'].search_count(in_progress_domain)

    def get_mo_action(self):
        self.ensure_one()
        action = self.env.ref('mrp.mrp_production_action').read()[0]
        action.update({
            'domain': self._get_mo_domain(),
            'context': {'search_default_todo': 1} if self.name != 'Completed Today' else {}
        })
        return action

    def get_action_mo_ready(self):
        self.ensure_one()
        if self.name == 'Completed Today':
            today_start = datetime.now().replace(hour=0, minute=0, second=0)
            today_end = datetime.now().replace(hour=23, minute=59, second=59)
            domain = [
                ('state', '=', 'done'),
                ('date_finished', '>=', today_start),
                ('date_finished', '<=', today_end)
            ]
        else:
            domain = self._get_mo_domain() + [
                ('state', 'in', ['confirmed', 'planned', 'draft']),
                ('reservation_state', '=', 'assigned')
            ]
        return {
            'name': 'Ready to Process' if self.name != 'Completed Today' else 'Completed Today',
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.production',
            'view_mode': 'tree,form,kanban',
            'domain': domain,
            'context': {'search_default_todo': 1} if self.name != 'Completed Today' else {}
        }

    def get_action_mo_waiting(self):
        self.ensure_one()
        if self.name == 'Completed Today':
            today_start = datetime.now().replace(hour=0, minute=0, second=0)
            today_end = datetime.now().replace(hour=23, minute=59, second=59)
            domain = [
                ('state', '=', 'done'),
                ('date_finished', '>=', today_start),
                ('date_finished', '<=', today_end)
            ]
        else:
            domain = self._get_mo_domain() + [
                ('state', 'in', ['confirmed', 'planned', 'draft']),
                ('reservation_state', '=', 'waiting')
            ]
        return {
            'name': 'Waiting' if self.name != 'Completed Today' else 'Completed Today',
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.production',
            'view_mode': 'tree,form,kanban',
            'domain': domain,
        }

    def get_action_mo_late(self):
        self.ensure_one()
        if self.name == 'Completed Today':
            today_start = datetime.now().replace(hour=0, minute=0, second=0)
            today_end = datetime.now().replace(hour=23, minute=59, second=59)
            domain = [
                ('state', '=', 'done'),
                ('date_finished', '>=', today_start),
                ('date_finished', '<=', today_end)
            ]
        else:
            domain = self._get_mo_domain() + [
                ('state', 'in', ['confirmed', 'planned', 'progress', 'to_close', 'draft']),
                ('date_start', '<', fields.Datetime.now())
            ]
        return {
            'name': 'Late Operations' if self.name != 'Completed Today' else 'Completed Today',
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.production',
            'view_mode': 'tree,form,kanban',
            'domain': domain,
        }

    def get_action_mo_in_progress(self):
        self.ensure_one()
        if self.name == 'Completed Today':
            today_start = datetime.now().replace(hour=0, minute=0, second=0)
            today_end = datetime.now().replace(hour=23, minute=59, second=59)
            domain = [
                ('state', '=', 'done'),
                ('date_finished', '>=', today_start),
                ('date_finished', '<=', today_end)
            ]
        else:
            domain = self._get_mo_domain() + [
                ('state', 'in', ['progress', 'to_close'])
            ]
        return {
            'name': 'In Progress' if self.name != 'Completed Today' else 'Completed Today',
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.production',
            'view_mode': 'tree,form,kanban',
            'domain': domain,
        }

    # Action method for the 'Lots/Serial Numbers' card type
    def action_open_lots_for_category(self):
        self.ensure_one()
        action = self.env.ref('stock.action_production_lot_form').read()[0]

        # Base domain: only lots with positive quantity
        domain = [('product_qty', '>', 0)]

        # Add category filter if specified on the dashboard card
        if self.product_category_id:
            domain.append(('product_id.categ_id', '=', self.product_category_id.id))
            action['name'] = _('SN บ้านที่ผลิตแล้ว - %s') % self.product_category_id.display_name
        else:
            # Optional: Define behavior if no category is set
            # Could show all lots, or raise an error, or filter something else
            # For now, it will just show all lots with qty > 0
            action['name'] = _('All Lots/SN') 

        action['domain'] = domain
        # Remove default filters from context if any were set by the original action
        action['context'] = {}

        return action 