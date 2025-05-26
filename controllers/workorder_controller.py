# -*- coding: utf-8 -*-

import logging
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, UserError, ValidationError
from datetime import datetime
import pytz

_logger = logging.getLogger(__name__)


class WorkOrderController(http.Controller):
    
    def _get_scan_context(self, workorder, action_type):
        """Helper method to prepare context data for templates"""
        # Get current user
        user = request.env.user
        
        # Get current datetime in user's timezone
        user_tz = pytz.timezone(user.tz or 'UTC')
        now_utc = datetime.now(pytz.UTC)
        now_user_tz = now_utc.astimezone(user_tz)
        
        return {
            'user_name': user.name,
            'user_login': user.login,
            'workorder_id': workorder.id,
            'workorder_name': workorder.name,
            'scan_date': now_user_tz.strftime('%d/%m/%Y'),
            'scan_time': now_user_tz.strftime('%H:%M:%S'),
            'action_type': action_type,
        }
    
    @http.route('/mrp/wo/scan_action', type='http', auth='user', methods=['GET'], csrf=False)
    def workorder_scan_action(self, workorder_id=None, **kwargs):
        """
        Controller to handle QR Code scanning for Work Orders.
        When a QR code is scanned, this will:
        1. Find the Work Order by ID
        2. Attempt to start the Work Order automatically
        3. Redirect to the Work Order form view
        """
        try:
            _logger.info("WorkOrder Scan Action called with workorder_id: %s", workorder_id)
            
            if not workorder_id:
                return request.render('need_mrp_dashboard.scan_error_template', {
                    'error_message': 'ไม่พบ Work Order ID ใน QR Code',
                    'error_details': 'กรุณาตรวจสอบ QR Code และลองใหม่อีกครั้ง'
                })
            
            # Convert workorder_id to integer
            try:
                wo_id = int(workorder_id)
            except (ValueError, TypeError):
                return request.render('need_mrp_dashboard.scan_error_template', {
                    'error_message': 'Work Order ID ไม่ถูกต้อง',
                    'error_details': f'ID ที่ได้รับ: {workorder_id}'
                })
            
            # Find the Work Order
            workorder = request.env['mrp.workorder'].browse(wo_id)
            if not workorder.exists():
                return request.render('need_mrp_dashboard.scan_error_template', {
                    'error_message': 'ไม่พบ Work Order',
                    'error_details': f'Work Order ID {wo_id} ไม่มีอยู่ในระบบ'
                })
            
            _logger.info("Found Work Order: %s (State: %s)", workorder.name, workorder.state)
            
            # Check if Work Order can be started or finished
            if workorder.state in ['progress']:
                # Already in progress, finish the Work Order (second scan)
                try:
                    workorder.button_finish()
                    _logger.info("Successfully finished Work Order: %s", workorder.name)
                    
                    context = self._get_scan_context(workorder, 'finish')
                    context.update({
                        'success_message': f'เสร็จสิ้นการทำงาน Work Order {workorder.name}',
                        'success_details': f'การจับเวลาได้หยุดลงแล้ว และ Work Order ได้เปลี่ยนสถานะเป็น "เสร็จสิ้น"',
                    })
                    return request.render('need_mrp_dashboard.scan_success_template', context)
                    
                except (AccessError, UserError, ValidationError) as e:
                    _logger.error("Failed to finish Work Order %s: %s", workorder.name, str(e))
                    return request.render('need_mrp_dashboard.scan_error_template', {
                        'error_message': 'ไม่สามารถเสร็จสิ้นการทำงานได้',
                        'error_details': f'Work Order: {workorder.name}\nเหตุผล: {str(e)}'
                    })
            elif workorder.state in ['ready', 'pending', 'waiting']:
                # Try to start the Work Order (first scan)
                try:
                    workorder.button_start()
                    _logger.info("Successfully started Work Order: %s", workorder.name)
                    
                    context = self._get_scan_context(workorder, 'start')
                    context.update({
                        'success_message': f'เริ่มการทำงาน Work Order {workorder.name}',
                        'success_details': f'การจับเวลาได้เริ่มต้นแล้ว สแกน QR Code อีกครั้งเพื่อเสร็จสิ้นการทำงาน',
                    })
                    return request.render('need_mrp_dashboard.scan_success_template', context)
                    
                except (AccessError, UserError, ValidationError) as e:
                    _logger.error("Failed to start Work Order %s: %s", workorder.name, str(e))
                    return request.render('need_mrp_dashboard.scan_error_template', {
                        'error_message': 'ไม่สามารถเริ่มการทำงานได้',
                        'error_details': f'Work Order: {workorder.name}\nเหตุผล: {str(e)}'
                    })
            elif workorder.state in ['done']:
                # Work Order is already finished
                _logger.info("Work Order %s is already finished", workorder.name)
                
                context = self._get_scan_context(workorder, 'finish')
                context.update({
                    'success_message': f'Work Order {workorder.name} เสร็จสิ้นแล้ว',
                    'success_details': f'Work Order นี้ได้เสร็จสิ้นการทำงานไปแล้ว',
                })
                return request.render('need_mrp_dashboard.scan_success_template', context)
            else:
                # Work Order is in a state that cannot be started or finished
                _logger.warning("Work Order %s is in state '%s' and cannot be processed", workorder.name, workorder.state)
                return request.render('need_mrp_dashboard.scan_error_template', {
                    'error_message': f'ไม่สามารถดำเนินการได้',
                    'error_details': f'Work Order: {workorder.name}\nสถานะปัจจุบัน: {workorder.state}\nไม่สามารถเริ่มหรือเสร็จสิ้นการทำงานได้'
                })
            
            # This line should not be reached, but kept for safety
            return request.redirect(f'/web#id={wo_id}&model=mrp.workorder&view_type=form')
            
        except Exception as e:
            _logger.exception("Unexpected error in workorder_scan_action: %s", str(e))
            return request.render('need_mrp_dashboard.scan_error_template', {
                'error_message': 'เกิดข้อผิดพลาดที่ไม่คาดคิด',
                'error_details': str(e)
            })
    
    @http.route('/mrp/wo/scan_action_public', type='http', auth='public', methods=['GET'], csrf=False)
    def workorder_scan_action_public(self, workorder_id=None, **kwargs):
        """
        Public version of the scan action for cases where users might not be logged in.
        This will redirect to login first, then to the scan action.
        """
        if not request.session.uid:
            # User not logged in, redirect to login with return URL
            return_url = f'/mrp/wo/scan_action?workorder_id={workorder_id}' if workorder_id else '/mrp/wo/scan_action'
            login_url = f'/web/login?redirect={return_url}'
            return request.redirect(login_url)
        else:
            # User is logged in, redirect to the main scan action
            return request.redirect(f'/mrp/wo/scan_action?workorder_id={workorder_id}') 