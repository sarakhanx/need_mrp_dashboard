from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, UserError
import logging

_logger = logging.getLogger(__name__)

class MRPWorkorderScanController(http.Controller):

    @http.route('/mrp/wo/scan_action', type='http', auth='user', website=False, methods=['GET'])
    def workorder_scan_action(self, workorder_id=None, **kwargs):
        if not workorder_id:
            _logger.warning("Work Order Scan Action: Missing workorder_id.")
            return request.redirect('/web')

        try:
            wo_id = int(workorder_id)
            workorder = request.env['mrp.workorder'].sudo().browse(wo_id)
            if not workorder.exists():
                _logger.warning(f"Work Order Scan Action: Work Order ID {wo_id} not found.")
                return request.redirect('/web')

            try:
                workorder.with_user(request.session.uid).check_access_rights('write', raise_exception=True)
                workorder.with_user(request.session.uid).check_access_rule('write')
            except (AccessError, UserError) as e:
                _logger.error(f"Work Order Scan Action: User {request.session.uid} does not have access to WO {wo_id}. Error: {e}")
                return request.make_response("Access Denied. You do not have permission to perform this action on the work order.", status=403)

            _logger.info(f"CONTROLLER_DEBUG: User {request.env.user.name} (ID: {request.env.user.id}) scanning WO {wo_id} with state '{workorder.state}'")

            if workorder.state in ('ready', 'pending', 'waiting'):
                _logger.info(f"Work Order Scan Action: Attempting to start WO {wo_id} (current state: {workorder.state}) by user {request.session.uid}")
                workorder.with_user(request.session.uid).button_start()
                _logger.info(f"Work Order Scan Action: WO {wo_id} started successfully.")
            elif workorder.state == 'progress':
                _logger.info(f"Work Order Scan Action: Attempting to finish WO {wo_id} (current state: {workorder.state}) by user {request.session.uid}")
                workorder.with_user(request.session.uid).button_finish()
                _logger.info(f"Work Order Scan Action: WO {wo_id} finished successfully.")
            else:
                _logger.warning(f"Work Order Scan Action: WO {wo_id} is in state '{workorder.state}'. No action performed (scan is only for start/finish).")

        except ValueError:
            _logger.warning(f"Work Order Scan Action: Invalid Work Order ID '{workorder_id}'.")
            return request.redirect('/web')
        except Exception as e:
            _logger.error(f"Work Order Scan Action: Error processing WO {workorder_id}. Error: {e}", exc_info=True)
            return request.make_response(f"An error occurred: {str(e)}", status=500)

        try:
            action = request.env.ref('mrp.action_mrp_workorder_production')
            if action:
                url = "/web#id=%s&model=mrp.workorder&view_type=form&action=%s" % (wo_id, action.id)
                return request.redirect(url)
        except ValueError:
            _logger.error(f"Work Order Scan Action: Could not find redirect action 'mrp.action_mrp_workorder_production' for WO {wo_id}. Fallback redirect.")
        
        return request.redirect(f'/web#id={wo_id}&model=mrp.workorder&view_type=form') 