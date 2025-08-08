from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class MrpLaborTransaction(models.Model):
    _name = 'mrp.labor.transaction'
    _description = 'MRP Labor Cost Transaction'
    _order = 'transaction_date desc, id desc'
    
    production_id = fields.Many2one(
        'mrp.production', 
        string='Manufacturing Order', 
        required=True, 
        ondelete='cascade'
    )
    transaction_date = fields.Datetime(
        string='วันที่เบิก',
        default=fields.Datetime.now,
        required=True
    )
    amount = fields.Float(
        string='จำนวนเงิน (บาท)',
        required=True,
        help='จำนวนเงินค่าแรงที่เบิกในครั้งนี้'
    )
    description = fields.Char(
        string='รายละเอียด',
        help='รายละเอียดการเบิกค่าแรง เช่น เบิกครั้งที่ 1, ปรับปรุงงาน, เบิกเพิ่ม'
    )
    user_id = fields.Many2one(
        'res.users',
        string='ผู้บันทึก',
        default=lambda self: self.env.user,
        readonly=True
    )
    
    @api.model
    def create(self, vals):
        """Override create to log transaction creation"""
        result = super(MrpLaborTransaction, self).create(vals)
        _logger.info(f"Labor transaction created: {result.amount} THB for MO {result.production_id.name} by {result.user_id.name}")
        return result
    
    def write(self, vals):
        """Override write to log transaction updates"""
        old_amount = self.amount
        result = super(MrpLaborTransaction, self).write(vals)
        if 'amount' in vals:
            _logger.info(f"Labor transaction updated: {old_amount} -> {vals['amount']} THB for MO {self.production_id.name}")
        return result
    
    def unlink(self):
        """Override unlink to log transaction deletion"""
        for record in self:
            _logger.info(f"Labor transaction deleted: {record.amount} THB for MO {record.production_id.name}")
        return super(MrpLaborTransaction, self).unlink()

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    # Field for tracking BOM Materials Report printing
    bom_materials_printed = fields.Boolean(
        string='BOM Materials Printed',
        default=False,
        help='Indicates if BOM Materials Report has been printed for this MO'
    )
    bom_materials_print_date = fields.Datetime(
        string='BOM Materials Print Date',
        help='Date and time when BOM Materials Report was printed'
    )
    bom_materials_print_user_id = fields.Many2one(
        'res.users',
        string='Printed by',
        help='User who printed the BOM Materials Report'
    )
    
    # Computed field for display in list view
    bom_materials_print_status = fields.Char(
        string='Print Status',
        compute='_compute_bom_materials_print_status',
        help='Visual indicator for BOM Materials Report print status'
    )
    
    # Additional fields for MO tracking
    technician_team = fields.Char(
        string='ทีมช่างผู้รับผิดชอบ',
        help='ทีมช่างหรือผู้รับผิดชอบในการผลิต'
    )
    customer_name = fields.Char(
        string='ชื่อลูกค้า',
        help='ชื่อลูกค้าที่สั่งผลิตภัณฑ์นี้'
    )
    sales_team = fields.Char(
        string='ทีมขาย',
        help='ทีมขายหรือผู้รับผิดชอบการขาย'
    )
    shipping_cost = fields.Float(
        string='ค่าขนส่ง (บาท)',
        help='ค่าขนส่งสำหรับ MO นี้'
    )
    
    # Labor transaction fields
    labor_transaction_ids = fields.One2many(
        'mrp.labor.transaction',
        'production_id',
        string='รายการเบิกค่าแรง'
    )
    total_labor_cost = fields.Float(
        string='ค่าแรงรวม (บาท)',
        compute='_compute_total_labor_cost',
        store=True,
        help='ค่าแรงรวมจากการเบิกทั้งหมด'
    )

    @api.depends('bom_materials_printed')
    def _compute_bom_materials_print_status(self):
        """Compute print status indicator for list view"""
        for record in self:
            if record.bom_materials_printed:
                record.bom_materials_print_status = '🟢 Printed'
            else:
                record.bom_materials_print_status = '🔴 Not Printed'
    
    @api.depends('labor_transaction_ids.amount')
    def _compute_total_labor_cost(self):
        """Compute total labor cost from all transactions"""
        for record in self:
            record.total_labor_cost = sum(record.labor_transaction_ids.mapped('amount'))

    def _find_parent_mo(self):
        """Find parent MO for sub MO using multiple methods"""
        parent_mo = None
        
        # Method 1: Search by origin field
        if self.origin:
            parent_mo = self.search([
                ('name', '=', self.origin),
                ('id', '!=', self.id)
            ], limit=1)
            
            if parent_mo:
                _logger.info(f"Found parent MO {parent_mo.name} for sub MO {self.name} via origin field")
                return parent_mo
        
        # Method 2: Search by procurement group
        if self.procurement_group_id:
            parent_mo = self.search([
                ('procurement_group_id', '=', self.procurement_group_id.id),
                ('id', '!=', self.id),
                ('create_date', '<', self.create_date)  # Parent should be created before sub MO
            ], limit=1, order='create_date desc')
            
            if parent_mo:
                _logger.info(f"Found parent MO {parent_mo.name} for sub MO {self.name} via procurement group")
                return parent_mo
        
        # Method 3: Search by related stock moves
        try:
            # Find stock moves that reference this MO as destination
            related_moves = self.env['stock.move'].search([
                ('production_id', '=', self.id),
                ('state', '!=', 'cancel')
            ], limit=1)
            
            if related_moves:
                # Look for the source move that might be from parent MO
                source_moves = self.env['stock.move'].search([
                    ('move_dest_ids', 'in', related_moves.ids),
                    ('raw_material_production_id', '!=', False),
                    ('raw_material_production_id', '!=', self.id)
                ], limit=1)
                
                if source_moves:
                    parent_mo = source_moves.raw_material_production_id
                    _logger.info(f"Found parent MO {parent_mo.name} for sub MO {self.name} via stock moves")
                    return parent_mo
        except Exception as e:
            _logger.warning(f"Error searching parent MO via stock moves: {str(e)}")
        
        return None

    @api.model
    def create(self, vals):
        """Override create to copy fields from parent MO to sub MO"""
        # Create the MO first
        result = super(MrpProduction, self).create(vals)
        
        # Try to find parent MO and copy fields
        parent_mo = result._find_parent_mo()
        
        if parent_mo:
            # Copy additional fields from parent MO
            update_vals = {}
            if parent_mo.technician_team and not result.technician_team:
                update_vals['technician_team'] = parent_mo.technician_team
            if parent_mo.customer_name and not result.customer_name:
                update_vals['customer_name'] = parent_mo.customer_name
            if parent_mo.sales_team and not result.sales_team:
                update_vals['sales_team'] = parent_mo.sales_team
            if parent_mo.shipping_cost and not result.shipping_cost:
                update_vals['shipping_cost'] = parent_mo.shipping_cost
            
            # Update the sub MO with parent's fields
            if update_vals:
                result.write(update_vals)
                _logger.info(f"Sub MO {result.name} copied fields from parent MO {parent_mo.name}: {update_vals}")
        
        return result

    def action_update_sub_mo_fields(self):
        """Manual action to update fields in sub MOs"""
        child_mo_ids = []
        
        # Find all sub MOs using the existing method from mrp_material_overview
        if hasattr(self, '_get_child_manufacturing_orders'):
            child_mo_ids = self._get_child_manufacturing_orders()
        else:
            # Fallback: search by origin
            child_mos = self.env['mrp.production'].search([
                ('origin', '=', self.name),
                ('id', '!=', self.id)
            ])
            child_mo_ids = child_mos.ids
        
        if child_mo_ids:
            child_mos = self.env['mrp.production'].browse(child_mo_ids)
            updated_count = 0
            
            for child_mo in child_mos:
                update_vals = {}
                
                # Copy technician_team if parent has it and child doesn't
                if self.technician_team and not child_mo.technician_team:
                    update_vals['technician_team'] = self.technician_team
                
                # Copy customer_name if parent has it and child doesn't
                if self.customer_name and not child_mo.customer_name:
                    update_vals['customer_name'] = self.customer_name
                
                # Copy sales_team if parent has it and child doesn't
                if self.sales_team and not child_mo.sales_team:
                    update_vals['sales_team'] = self.sales_team
                
                # Copy shipping_cost if parent has it and child doesn't
                if self.shipping_cost and not child_mo.shipping_cost:
                    update_vals['shipping_cost'] = self.shipping_cost
                
                if update_vals:
                    child_mo.write(update_vals)
                    updated_count += 1
                    _logger.info(f"Updated sub MO {child_mo.name} with fields: {update_vals}")
            
            # Show notification to user
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sub MO Fields Updated',
                    'message': f'Updated {updated_count} sub MO(s) with team info, customer name, and costs.',
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Sub MOs Found',
                    'message': 'No sub manufacturing orders found for this MO.',
                    'type': 'info',
                    'sticky': False,
                }
            }

    def mark_bom_materials_printed(self):
        """Mark this MO as having BOM Materials Report printed"""
        self.write({
            'bom_materials_printed': True,
            'bom_materials_print_date': fields.Datetime.now(),
            'bom_materials_print_user_id': self.env.user.id,
        })
        return True

    def reset_bom_materials_printed(self):
        """Reset the BOM Materials Report printed status"""
        self.write({
            'bom_materials_printed': False,
            'bom_materials_print_date': False,
            'bom_materials_print_user_id': False,
        })
        return True

    def action_view_bom_materials_print_info(self):
        """Show BOM Materials Print Information"""
        return {
            'name': 'BOM Materials Print Information',
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.production',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('mrp.mrp_production_form_view').id,
            'target': 'new',
            'context': {'default_bom_materials_printed': self.bom_materials_printed}
        }

    def action_reset_bom_materials_printed(self):
        """Action to reset BOM Materials printed status"""
        self.reset_bom_materials_printed()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    @api.model
    def auto_close_to_done(self):
        """Automatically mark 'to_close' manufacturing orders as 'done'"""
        to_close_orders = self.search([('state', '=', 'to_close')])
        success_count = 0
        error_count = 0
        
        _logger.info(f"Found {len(to_close_orders)} orders in to_close state")
        
        for order in to_close_orders:
            try:
                # Use the standard button_mark_done method to ensure proper stock handling
                order.button_mark_done()
                success_count += 1
                _logger.info(f"Successfully closed MO {order.name}")
            except Exception as e:
                error_count += 1
                _logger.warning(f"Failed to close MO {order.name}: {str(e)}")
        
        if success_count > 0 or error_count > 0:
            _logger.info(f"Auto close completed: {success_count} success, {error_count} errors")
        
        return True

    def _check_company(self):
        """Override to trigger auto-close check"""
        result = super(MrpProduction, self)._check_company()
        self._auto_close_if_needed()
        return result

    def _auto_close_if_needed(self):
        """Check and auto-close if all conditions are met"""
        # Prevent recursion by checking context
        if self.env.context.get('auto_closing_in_progress'):
            return
            
        skip_to_close = self.env['ir.config_parameter'].sudo().get_param('mrp.skip_to_close_state', 'False')
        
        if skip_to_close.lower() == 'true':
            for production in self:
                # Check if all work orders are done and production should be closed
                if production.state in ['progress', 'to_close']:
                    all_workorders_done = all(wo.state == 'done' for wo in production.workorder_ids)
                    if all_workorders_done and production.workorder_ids:
                        _logger.info(f"All work orders done for MO {production.name}, auto-closing")
                        try:
                            # Use context to prevent recursion
                            production_with_context = production.with_context(auto_closing_in_progress=True)
                            # Always use button_mark_done to ensure proper stock handling
                            production_with_context.button_mark_done()
                            _logger.info(f"Successfully auto-closed MO {production.name}")
                        except Exception as e:
                            _logger.error(f"Failed to auto-close MO {production.name}: {str(e)}")

    def _set_qty_producing(self):
        """Override to auto-close after setting qty producing"""
        result = super(MrpProduction, self)._set_qty_producing()
        self._auto_close_if_needed()
        return result

    def button_mark_done(self):
        """Override button_mark_done to handle auto-close properly"""
        _logger.info(f"button_mark_done called for MO {self.name}, current state: {self.state}")
        
        # Check if we should skip to_close state
        skip_to_close = self.env['ir.config_parameter'].sudo().get_param('mrp.skip_to_close_state', 'False')
        
        # If skip_to_close is enabled and we're not already auto-closing
        if skip_to_close.lower() == 'true' and not self.env.context.get('auto_closing_in_progress'):
            # Use context to prevent auto-close recursion
            self_with_context = self.with_context(auto_closing_in_progress=True)
            
            # Call parent method
            result = super(MrpProduction, self_with_context).button_mark_done()
            
            # If we ended up in to_close, call again to complete to done
            if self.state == 'to_close':
                _logger.info(f"MO {self.name} in to_close, completing to done")
                result = super(MrpProduction, self_with_context).button_mark_done()
            
            _logger.info(f"button_mark_done completed for MO {self.name}, final state: {self.state}")
            return result
        else:
            # Normal processing without auto-close
            result = super(MrpProduction, self).button_mark_done()
            _logger.info(f"button_mark_done completed for MO {self.name}, new state: {self.state}")
            return result

    def write(self, vals):
        """Override write to auto-close when state changes to to_close"""
        result = super(MrpProduction, self).write(vals)
        
        # Check if we should auto-close to_close orders
        if 'state' in vals and vals['state'] == 'to_close':
            skip_to_close = self.env['ir.config_parameter'].sudo().get_param('mrp.skip_to_close_state', 'False')
            
            if skip_to_close.lower() == 'true':
                for record in self:
                    if record.state == 'to_close' and not self.env.context.get('auto_closing_in_progress'):
                        _logger.info(f"Auto-closing MO {record.name} that was set to to_close")
                        try:
                            # Use context to prevent recursion
                            record_with_context = record.with_context(auto_closing_in_progress=True)
                            # Use button_mark_done to ensure proper stock handling
                            record_with_context.button_mark_done()
                        except Exception as e:
                            _logger.error(f"Failed to auto-close MO {record.name}: {str(e)}")
        
        return result


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    def button_finish(self):
        """Override work order finish to trigger production auto-close"""
        result = super(MrpWorkorder, self).button_finish()
        
        # Check if this was the last work order and trigger auto-close
        if self.production_id:
            self.production_id._auto_close_if_needed()
        
        return result 