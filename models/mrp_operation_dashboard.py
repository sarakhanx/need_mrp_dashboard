from odoo import models, fields, api

class MrpOperationDashboard(models.Model):
    _name = 'mrp.operation.dashboard'
    _description = 'Manufacturing Operation Type Dashboard'

    name = fields.Char('Name', required=True)
    operation_type_id = fields.Many2one('stock.picking.type', string='Operation Type', required=True)
    color = fields.Integer('Color Index')
    warehouse_id = fields.Many2one(related='operation_type_id.warehouse_id', string='Warehouse', store=True)
    
    # Operation Counts
    count_todo = fields.Integer(compute='_compute_operation_count', string='To Process')
    count_waiting = fields.Integer(compute='_compute_operation_count', string='Waiting')
    count_late = fields.Integer(compute='_compute_operation_count', string='Late')
    count_in_progress = fields.Integer(compute='_compute_operation_count', string='In Progress')

    @api.model
    def _init_dashboard_data(self):
        # Manufacturing Operations
        manu_type = self.env['stock.picking.type'].search([('code', '=', 'mrp_operation')], limit=1)
        if manu_type and not self.search_count([('operation_type_id', '=', manu_type.id)]):
            self.create({
                'name': 'Manufacturing Operations',
                'operation_type_id': manu_type.id,
                'color': 5
            })

        # Finished Products
        out_type = self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)
        if out_type and not self.search_count([('operation_type_id', '=', out_type.id)]):
            self.create({
                'name': 'Finished Products',
                'operation_type_id': out_type.id,
                'color': 6
            })

        # Raw Materials
        in_type = self.env['stock.picking.type'].search([('code', '=', 'incoming')], limit=1)
        if in_type and not self.search_count([('operation_type_id', '=', in_type.id)]):
            self.create({
                'name': 'Raw Materials',
                'operation_type_id': in_type.id,
                'color': 7
            })

    @api.depends('operation_type_id')
    def _compute_operation_count(self):
        for record in self:
            if not record.operation_type_id:
                record.count_todo = 0
                record.count_waiting = 0
                record.count_late = 0
                record.count_in_progress = 0
                continue

            if record.operation_type_id.code == 'mrp_operation':
                # Manufacturing Orders
                base_domain = [('picking_type_id', '=', record.operation_type_id.id)]
                record.count_todo = self.env['mrp.production'].search_count(base_domain + [
                    ('state', 'in', ['confirmed', 'planned']),
                    ('reservation_state', '=', 'assigned')
                ])
                record.count_waiting = self.env['mrp.production'].search_count(base_domain + [
                    ('state', 'in', ['confirmed', 'planned']),
                    ('reservation_state', '=', 'waiting')
                ])
                record.count_late = self.env['mrp.production'].search_count(base_domain + [
                    ('state', 'in', ['confirmed', 'planned', 'progress']),
                    ('date_start', '<', fields.Datetime.now())
                ])
                record.count_in_progress = self.env['mrp.production'].search_count(base_domain + [
                    ('state', '=', 'progress')
                ])
            else:
                # Stock Pickings
                base_domain = [('picking_type_id', '=', record.operation_type_id.id)]
                record.count_todo = self.env['stock.picking'].search_count(base_domain + [
                    ('state', 'in', ['assigned']),
                ])
                record.count_waiting = self.env['stock.picking'].search_count(base_domain + [
                    ('state', 'in', ['confirmed', 'waiting']),
                ])
                record.count_late = self.env['stock.picking'].search_count(base_domain + [
                    ('state', 'not in', ['done', 'cancel']),
                    ('scheduled_date', '<', fields.Datetime.now())
                ])
                record.count_in_progress = self.env['stock.picking'].search_count(base_domain + [
                    ('state', '=', 'assigned')
                ])

    def get_operation_action(self):
        self.ensure_one()
        if self.operation_type_id.code == 'mrp_operation':
            action = self.env.ref('mrp.mrp_production_action').read()[0]
            action.update({
                'domain': [('picking_type_id', '=', self.operation_type_id.id)],
                'context': {'search_default_todo': 1}
            })
        else:
            action = self.env.ref('stock.stock_picking_action_picking_type').read()[0]
            action.update({
                'domain': [('picking_type_id', '=', self.operation_type_id.id)],
                'context': {'search_default_available': 1}
            })
        return action

    def get_action_todo(self):
        self.ensure_one()
        if self.operation_type_id.code == 'mrp_operation':
            return {
                'name': 'Ready to Process',
                'type': 'ir.actions.act_window',
                'res_model': 'mrp.production',
                'view_mode': 'tree,form,kanban',
                'domain': [
                    ('picking_type_id', '=', self.operation_type_id.id),
                    ('state', 'in', ['confirmed', 'planned', 'draft']),
                    ('reservation_state', '=', 'assigned')
                ],
            }
        else:
            return {
                'name': 'Ready to Process',
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_mode': 'tree,form,kanban',
                'domain': [
                    ('picking_type_id', '=', self.operation_type_id.id),
                    ('state', 'in', ['assigned', 'confirmed']),
                ],
            }

    def get_action_waiting(self):
        self.ensure_one()
        if self.operation_type_id.code == 'mrp_operation':
            return {
                'name': 'Waiting',
                'type': 'ir.actions.act_window',
                'res_model': 'mrp.production',
                'view_mode': 'tree,form,kanban',
                'domain': [
                    ('picking_type_id', '=', self.operation_type_id.id),
                    ('state', 'in', ['confirmed', 'planned', 'draft']),
                    ('reservation_state', '=', 'waiting')
                ],
            }
        else:
            return {
                'name': 'Waiting',
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_mode': 'tree,form,kanban',
                'domain': [
                    ('picking_type_id', '=', self.operation_type_id.id),
                    ('state', 'in', ['confirmed', 'waiting', 'draft']),
                ],
            }

    def get_action_late(self):
        self.ensure_one()
        if self.operation_type_id.code == 'mrp_operation':
            return {
                'name': 'Late Operations',
                'type': 'ir.actions.act_window',
                'res_model': 'mrp.production',
                'view_mode': 'tree,form,kanban',
                'domain': [
                    ('picking_type_id', '=', self.operation_type_id.id),
                    ('state', 'in', ['confirmed', 'planned', 'progress', 'to_close', 'draft']),
                    ('date_start', '<', fields.Datetime.now())
                ],
            }
        else:
            return {
                'name': 'Late Operations',
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_mode': 'tree,form,kanban',
                'domain': [
                    ('picking_type_id', '=', self.operation_type_id.id),
                    ('state', 'not in', ['done', 'cancel']),
                    ('scheduled_date', '<', fields.Datetime.now())
                ],
            }

    def get_action_in_progress(self):
        self.ensure_one()
        if self.operation_type_id.code == 'mrp_operation':
            return {
                'name': 'In Progress',
                'type': 'ir.actions.act_window',
                'res_model': 'mrp.production',
                'view_mode': 'tree,form,kanban',
                'domain': [
                    ('picking_type_id', '=', self.operation_type_id.id),
                    ('state', 'in', ['progress', 'to_close'])
                ],
            }
        else:
            return {
                'name': 'In Progress',
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_mode': 'tree,form,kanban',
                'domain': [
                    ('picking_type_id', '=', self.operation_type_id.id),
                    ('state', '=', 'assigned')
                ],
            } 