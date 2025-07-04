from odoo import models, fields, api, _
from datetime import datetime, timedelta
from odoo.tools.safe_eval import safe_eval

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
    
    # New configurable fields
    operation_type_id = fields.Many2one(
        'stock.picking.type', 
        string='Operation Type',
        domain="[('code', '=', 'mrp_operation')]",
        help="Filter Manufacturing Orders by specific operation type")
    custom_domain = fields.Text(
        string='Custom Domain',
        help="Custom domain filter for Manufacturing Orders. Example: [('state', '=', 'done')] Leave empty for all records.")
    
    # Production Orders Counts
    count_mo_ready = fields.Integer(compute='_compute_mo_count', string='Ready to Produce')
    count_mo_waiting = fields.Integer(compute='_compute_mo_count', string='Waiting for Materials')
    count_mo_late = fields.Integer(compute='_compute_mo_count', string='Late')
    count_mo_in_progress = fields.Integer(compute='_compute_mo_count', string='In Progress')

    def _get_mo_domain(self):
        """Get base domain for Manufacturing Orders"""
        base_domain = []
        
        # Add operation type filter if specified
        if self.operation_type_id:
            base_domain.append(('picking_type_id', '=', self.operation_type_id.id))
        
        # Add custom domain if specified
        if self.custom_domain:
            try:
                custom_domain = safe_eval(self.custom_domain)
                if isinstance(custom_domain, list):
                    base_domain.extend(custom_domain)
            except Exception as e:
                # Log error but continue with base domain
                pass
        
        # Fallback to legacy domain logic if no custom domain specified
        if not self.custom_domain:
            if self.name == 'All Manufacturing':
                pass  # No additional domain
            elif self.name == 'Work In Progress':
                base_domain.append(('state', 'in', ['confirmed', 'progress']))
            elif self.name == 'Waiting for Materials':
                base_domain.extend([('state', '=', 'confirmed'), ('reservation_state', '=', 'waiting')])
            elif self.name == 'Completed Today':
                today_start = datetime.now().replace(hour=0, minute=0, second=0)
                today_end = datetime.now().replace(hour=23, minute=59, second=59)
                base_domain.extend([('state', '=', 'done'), ('date_finished', '>=', today_start), ('date_finished', '<=', today_end)])
        
        return base_domain

    @api.depends('name', 'operation_type_id', 'custom_domain')
    def _compute_mo_count(self):
        for record in self:
            base_domain = record._get_mo_domain()
            
            if record.name == 'Completed Today' and not record.custom_domain:
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
        return {
            'name': 'Manufacturing Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.production',
            'view_mode': 'tree,form,kanban',
            'domain': self._get_mo_domain(),
            'context': {'search_default_todo': 1} if self.name != 'Completed Today' else {}
        }

    def get_action_mo_ready(self):
        self.ensure_one()
        if self.name == 'Completed Today' and not self.custom_domain:
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
        if self.name == 'Completed Today' and not self.custom_domain:
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
        if self.name == 'Completed Today' and not self.custom_domain:
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
        if self.name == 'Completed Today' and not self.custom_domain:
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
        # Build the action dictionary manually instead of reading the reference
        # action = self.env.ref('stock.action_production_lot_form').read()[0]

        # Base domain: only lots with positive quantity
        domain = [('product_qty', '>', 0)]
        action_name = _('All Lots/SN (Qty > 0)') 

        # Add category filter if specified on the dashboard card
        if self.product_category_id:
            domain.append(('product_id.categ_id', '=', self.product_category_id.id))
            action_name = _('เช็ครายการสินค้าที่ผลิตเสร็จแล้ว') # Using the Thai name you preferred
            # action_name = _('Lots/SN - %s') % self.product_category_id.display_name # Original alternative
        # else:
            # Optional: Define behavior if no category is set
            # Currently shows all lots with qty > 0
            # pass

        # Manually define the action dictionary
        action = {
            'name': action_name,
            'type': 'ir.actions.act_window',
            'res_model': 'stock.lot',
            'view_mode': 'tree,form,kanban', # Include desired views
            'domain': domain,
            'target': 'current', # Or 'new' if you prefer a dialog/new window
            'context': {} # Ensure clean context
        }

        # Optional: Reference a specific search view if needed and known to be accessible
        # try:
        #     search_view_id = self.env.ref('stock.view_production_lot_filter').id
        #     action['search_view_id'] = search_view_id
        # except ValueError:
        #     _logger.warning("Could not find search view 'stock.view_production_lot_filter' for dashboard action.")

        # action['domain'] = domain
        # Remove default filters from context if any were set by the original action
        # action['context'] = {}

        return action 