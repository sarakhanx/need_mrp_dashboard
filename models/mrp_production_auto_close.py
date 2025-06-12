from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

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