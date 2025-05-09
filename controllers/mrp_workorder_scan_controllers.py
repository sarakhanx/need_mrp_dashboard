from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, UserError
import logging

_logger = logging.getLogger(__name__)

class MRPWorkorderScanController(http.Controller):

    @http.route('/mrp/wo/scan_action', type='http', auth='user', website=False, methods=['GET'])
    def workorder_scan_action(self, workorder_id=None, action_type=None, **kwargs):
        if not workorder_id or not action_type:
            # อาจจะ redirect ไปหน้า error หรือหน้าหลัก
            return request.redirect('/web')

        try:
            wo_id = int(workorder_id)
            workorder = request.env['mrp.workorder'].sudo().browse(wo_id) # ใช้ sudo ก่อนเพื่อ browse
            if not workorder.exists():
                _logger.warning(f"Work Order Scan Action: Work Order ID {wo_id} not found.")
                # อาจจะ redirect ไปหน้า error หรือแจ้งผู้ใช้
                return request.redirect('/web')

            # ตรวจสอบสิทธิ์การเข้าถึง (สำคัญมาก!)
            # นี่เป็นตัวอย่างการตรวจสอบสิทธิ์เบื้องต้น อาจจะต้องปรับปรุงให้เหมาะสมกับความต้องการ
            # ปกติ Odoo จะจัดการเรื่อง access rights ผ่าน record rules และ access model
            # การเรียก method ของ model โดยตรง อาจจะต้องมั่นใจว่า user ที่ request.env['mrp.workorder'] ผูกอยู่มีสิทธิ์
            # หรือถ้าจำเป็นจริงๆ อาจจะต้อง .sudo(user=request.session.uid) แล้วค่อยเช็ค permission อีกที
            # แต่การใช้ sudo() โดยไม่ระบุ user (ใช้ uid ของ superuser) ควรทำด้วยความระมัดระวัง

            # ลองให้ user ปัจจุบันพยายามอ่าน workorder ดูก่อน ถ้าไม่ได้ก็ไม่มีสิทธิ์
            try:
                workorder.with_user(request.session.uid).check_access_rights('write', raise_exception=True) # หรือ 'read' ถ้าแค่จะดูก่อน
                workorder.with_user(request.session.uid).check_access_rule('write') # 'write' เพราะ button_start คือการเขียน
            except (AccessError, UserError) as e:
                _logger.error(f"Work Order Scan Action: User {request.session.uid} does not have access to WO {wo_id}. Error: {e}")
                # แสดงหน้า error หรือ redirect
                # ตัวอย่าง: return request.render("need_mrp_dashboard.access_denied_page_template_name")
                return request.make_response("Access Denied. You do not have permission to perform this action on the work order.", status=403)

            _logger.info("CONTROLLER_DEBUG: User from request.env.user: %s (ID: %s)", request.env.user.name, request.env.user.id)
            if action_type == 'start':
                if workorder.state in ('ready', 'pending', 'progress', 'waiting'): # เพิ่ม 'waiting'
                    _logger.info(f"Work Order Scan Action: Attempting to start WO {wo_id} by user {request.session.uid}")
                    workorder.with_user(request.session.uid).button_start() # เรียก method ด้วย user ปัจจุบัน
                    _logger.info(f"Work Order Scan Action: WO {wo_id} started successfully.")
                else:
                    _logger.warning(f"Work Order Scan Action: WO {wo_id} is in state {workorder.state}, cannot start.")
            # TODO: เพิ่ม elif action_type == 'finish':
            # elif action_type == 'finish':
            #     if workorder.state == 'progress': # ตรวจสอบสถานะที่สามารถ finish ได้
            #         _logger.info(f"Work Order Scan Action: Attempting to finish WO {wo_id} by user {request.session.uid}")
            #         # Odoo 17 อาจจะไม่มี button_finish โดยตรง อาจจะต้องเรียก action_done หรือ record_production()
            #         # workorder.with_user(request.session.uid).record_production() # หรือ action_done()
            #         _logger.info(f"Work Order Scan Action: WO {wo_id} finished successfully.")
            #     else:
            #         _logger.warning(f"Work Order Scan Action: WO {wo_id} is in state {workorder.state}, cannot finish.")
            else:
                _logger.warning(f"Work Order Scan Action: Unknown action_type '{action_type}' for WO {wo_id}.")
                # อาจจะ redirect ไปหน้า error หรือแจ้งผู้ใช้

        except ValueError:
            _logger.warning(f"Work Order Scan Action: Invalid Work Order ID '{workorder_id}'.")
            return request.redirect('/web') # หรือหน้า error
        except Exception as e:
            _logger.error(f"Work Order Scan Action: Error processing WO {workorder_id} for action {action_type}. Error: {e}", exc_info=True)
            # แสดงหน้า error หรือ redirect
            # ตัวอย่าง: return request.render("need_mrp_dashboard.generic_error_page_template_name", {'error_message': str(e)})
            return request.make_response(f"An error occurred: {str(e)}", status=500)


        # Redirect ไปยังหน้า form view ของ work order นั้นๆ
        # เราต้องสร้าง URL สำหรับ redirect ให้ถูกต้อง
        # หมายเหตุ: request.redirect() โดยทั่วไปใช้กับ internal path
        # ถ้าจะ redirect ไป full URL อาจจะต้องสร้าง response เอง
        # แต่ในที่นี้เราจะ redirect ไปยัง action window ของ Odoo
        try:
            action = request.env.ref('mrp.action_mrp_workorder_production') # ลองใช้ Action นี้ดูก่อน
            if action:
                url = "/web#id=%s&model=mrp.workorder&view_type=form&action=%s" % (wo_id, action.id)
                return request.redirect(url)
        except ValueError:
            _logger.error(f"Work Order Scan Action: Could not find redirect action 'mrp.action_mrp_workorder_production' for WO {wo_id}. Fallback redirect.")
        
        # Fallback redirect ถ้าหา action ไม่เจอ หรือมีปัญหา
        return request.redirect(f'/web#id={wo_id}&model=mrp.workorder&view_type=form') 