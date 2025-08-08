from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class MrpProductionMaterialOverview(models.Model):
    _inherit = 'mrp.production'

    def _get_child_manufacturing_orders(self):
        """หา MO ย่อยทั้งหมดที่ reference มา MO หลัก (with safety limits)"""
        if not self.name or self.name == '/':
            return []
            
        child_mo_ids = []
        processed_names = set()  # ป้องกัน infinite loop
        
        def find_children_recursive(mo_name, depth=0):
            # จำกัดความลึกไม่เกิน 3 ระดับ
            if depth > 3:
                return
                
            # ป้องกัน infinite loop
            if mo_name in processed_names:
                return
                
            processed_names.add(mo_name)
            
            try:
                # หา MO ที่มี origin เป็น mo_name
                direct_children = self.env['mrp.production'].search([
                    ('origin', '=', mo_name),
                    ('id', '!=', self.id)
                ], limit=20)  # จำกัดไม่เกิน 20 รายการ
                
                for child in direct_children:
                    if child.id not in child_mo_ids:
                        child_mo_ids.append(child.id)
                        # Recursive หา MO ย่อยของ MO ย่อย
                        find_children_recursive(child.name, depth + 1)
                        
            except Exception as e:
                _logger.error(f"Error in recursive child search: {str(e)}")
                
        # เริ่มค้นหาจาก MO หลัก
        find_children_recursive(self.name)
        
        return child_mo_ids
    
    def action_view_related_deliveries_overview(self):
        """แสดง Deliveries Overview แบบ Hierarchical Tree View รวมทั้ง MO ย่อย"""
        self.ensure_one()
        
        # หา MO ย่อยทั้งหมด (recursive)
        child_mo_ids = self._get_child_manufacturing_orders()
        all_mo_ids = [self.id] + child_mo_ids
        
        # สร้าง list ของ MO names สำหรับค้นหา origin
        all_mo_records = self.env['mrp.production'].browse(all_mo_ids)
        all_mo_names = all_mo_records.mapped('name')
        
        # วิธีที่ 1: หาจาก origin ใน stock.picking (รวม MO ย่อย)
        deliveries_by_origin = self.env['stock.picking'].search([
            ('origin', 'in', all_mo_names),
            ('picking_type_id.code', '=', 'outgoing'),
            ('state', '!=', 'cancel')
        ])
        
        # วิธีที่ 2: หาจาก stock.move ที่เกี่ยวข้องกับ MO ทั้งหมด
        moves_from_production = self.env['stock.move'].search([
            ('production_id', 'in', all_mo_ids),
            ('picking_id', '!=', False),
            ('state', '!=', 'cancel')
        ])
        deliveries_from_moves = moves_from_production.mapped('picking_id')
        
        # วิธีที่ 3: หาจาก finished goods moves ของ MO ทั้งหมด
        finished_moves = self.env['stock.move'].search([
            ('production_id', 'in', all_mo_ids),
            ('product_id', 'in', all_mo_records.mapped('product_id').ids),
            ('picking_id', '!=', False),
            ('state', '!=', 'cancel')
        ])
        deliveries_from_finished = finished_moves.mapped('picking_id')
        
        # รวมทุกวิธี
        all_deliveries = deliveries_by_origin | deliveries_from_moves | deliveries_from_finished
        picking_ids = all_deliveries.ids
        
        # เปิด Dashboard เสมอ ไม่ว่าจะมี Deliveries หรือไม่
        return {
            'name': f'ต้นทุนวัสดุทั้งหมด ของ {self.name} มีจำนวน Station {len(child_mo_ids)} MO ย่อย',
            'type': 'ir.actions.client',
            'tag': 'delivery_hierarchy',
            'context': {
                'delivery_ids': picking_ids,  # ถ้าไม่มีจะเป็น []
                'default_mo_id': self.id,
                'child_mo_ids': child_mo_ids,
                'all_mo_names': all_mo_names,
                'deliveries_found': len(picking_ids),  # เพิ่มข้อมูลจำนวน deliveries
                'total_mo_count': len(child_mo_ids) + 1,  # รวม MO หลัก
            },
            'target': 'new',
            'res_model': 'stock.picking',
        }

    def action_debug_deliveries(self):
        """Debug method เพื่อดูข้อมูลทั้งหมดที่เกี่ยวข้องกับ MO"""
        self.ensure_one()
        
        debug_info = []
        debug_info.append(f"=== DEBUG INFO FOR MO: {self.name} ===")
        debug_info.append(f"MO ID: {self.id}")
        debug_info.append(f"MO State: {self.state}")
        debug_info.append(f"Product: {self.product_id.name}")
        debug_info.append("")
        
        # ตรวจสอบ MO ย่อย ลบอีกที
        child_mo_ids = self._get_child_manufacturing_orders()
        debug_info.append(f"Child MO IDs: {child_mo_ids}")
        if child_mo_ids:
            child_mos = self.env['mrp.production'].browse(child_mo_ids)
            for child_mo in child_mos:
                debug_info.append(f"  - {child_mo.name} | {child_mo.state} | {child_mo.product_id.name}")
        debug_info.append("")
        
        # ตรวจสอบ stock.picking ที่มี origin = MO name ลบอีกที
        pickings = self.env['stock.picking'].search([('origin', '=', self.name)])
        debug_info.append(f"Stock Pickings with origin '{self.name}': {len(pickings)}")
        for picking in pickings:
            debug_info.append(f"  - {picking.name} | {picking.picking_type_id.name} | {picking.state}")
        debug_info.append("")
        
        # ตรวจสอบ stock.move ที่เกี่ยวข้องกับ MO ลบอีกที
        moves = self.env['stock.move'].search([('production_id', '=', self.id)])
        debug_info.append(f"Stock Moves from this MO: {len(moves)}")
        for move in moves:
            debug_info.append(f"  - {move.name} | {move.product_id.name} | {move.state} | Picking: {move.picking_id.name if move.picking_id else 'None'}")
        debug_info.append("")
        
        # ตรวจสอบ outgoing pickings ทั้งหมด
        outgoing_pickings = self.env['stock.picking'].search([
            ('picking_type_id.code', '=', 'outgoing'),
            ('state', '!=', 'cancel')
        ])
        debug_info.append(f"All Outgoing Pickings: {len(outgoing_pickings)}")
        for picking in outgoing_pickings[:10]:  # แสดงแค่ 10 รายการแรก
            debug_info.append(f"  - {picking.name} | Origin: {picking.origin} | {picking.state}")
        debug_info.append("")
        
        message = "\n".join(debug_info)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': f'Debug Info - {self.name}',
                'message': message,
                'type': 'info',
                'sticky': True,
            }
        }

    def get_mo_overview_data(self):
        """ส่งข้อมูล MO Overview แบบเดียวกับ Odoo overview"""
        self.ensure_one()
        
        try:
            # Summary data
            mo_cost = self._calculate_mo_cost()
            real_cost = self._calculate_real_cost()
            
            summary = {
                'id': self.id,
                'name': self.product_id.name,
                'mo_name': self.name,
                'quantity': self.product_qty,
                'uom_name': self.product_uom_id.name,
                'state': self.state,
                'formatted_state': self._get_formatted_state(),
                'mo_cost': mo_cost,
                'unit_cost': mo_cost / self.product_qty if self.product_qty else 0,
                'real_cost': real_cost,
                # เพิ่มข้อมูลใหม่
                'customer_name': self.customer_name or '',
                'technician_team': self.technician_team or '',
                'sales_team': self.sales_team or '',
                'total_labor_cost': self.total_labor_cost or 0,
                'shipping_cost': self.shipping_cost or 0,
            }
            
            # Components data from raw moves
            components = []
            
            if self.move_raw_ids:
                for move in self.move_raw_ids:
                    try:
                        product = move.product_id
                        
                        # ดึงข้อมูล stock อย่างปลอดภัย
                        try:
                            quants = self.env['stock.quant'].search([
                                ('product_id', '=', product.id),
                                ('location_id.usage', '=', 'internal')
                            ])
                            quantity_on_hand = sum(quants.mapped('quantity')) if quants else 0
                        except Exception:
                            quantity_on_hand = 0
                        
                        # คำนวณต้นทุน
                        unit_cost = getattr(product, 'standard_price', 0) or 0
                        total_cost = move.product_uom_qty * unit_cost
                        
                        # สร้าง display name แบบ [REF] Product Name
                        internal_ref = getattr(product, 'default_code', '') or ''
                        if internal_ref:
                            display_name = f"[{internal_ref}] {product.name}"
                        else:
                            display_name = product.name
                        
                        # หา MO ย่อยที่เกี่ยวข้องกับ component นี้
                        sub_mos = self._get_sub_mos_for_component(product)
                        
                        component_data = {
                            'summary': {
                                'id': move.id,
                                'name': display_name,
                                'product_id': product.id,
                                'quantity': move.product_uom_qty,
                                'uom_name': getattr(move.product_uom, 'name', 'Units'),
                                'quantity_on_hand': quantity_on_hand,
                                'quantity_free': getattr(product, 'qty_available', 0),
                                'quantity_reserved': getattr(move, 'reserved_availability', 0) or 0,
                                'state': move.state,
                                'formatted_state': self._get_move_formatted_state(move.state),
                                'mo_cost': total_cost,
                                'unit_cost': unit_cost,
                                'receipt': self._get_receipt_info(move),
                                'description': getattr(product, 'description', '') or getattr(product, 'description_sale', '') or '',
                            },
                            'sub_mos': sub_mos
                        }
                        components.append(component_data)
                        
                    except Exception as e:
                        _logger.error(f"Error processing move {move.id}: {str(e)}")
                        continue
            
            # ถ้ายังไม่มี components ให้ลองดึงจาก BOM
            if not components and self.bom_id:
                try:
                    components = self._get_components_from_bom()
                except Exception as e:
                    _logger.error(f"Error getting components from BOM: {str(e)}")
                    components = []
            
            # Operations data from workorders
            operations = {
                'summary': {
                    'quantity': 0,
                    'mo_cost': 0,
                    'real_cost': 0,
                    'uom_name': 'Minutes',
                },
                'details': []
            }
            
            if self.workorder_ids:
                total_time = 0
                total_cost = 0
                total_real_time = 0
                
                for wo in self.workorder_ids:
                    try:
                        duration_expected = wo.duration_expected or 0
                        duration_real = wo.duration or 0
                        cost_hour = getattr(wo.workcenter_id, 'costs_hour', 0) or 0
                        
                        total_time += duration_expected
                        total_real_time += duration_real
                        total_cost += (duration_expected * cost_hour / 60)  # แปลงเป็นชั่วโมง
                        
                        operations['details'].append({
                            'name': wo.name,
                            'workcenter': wo.workcenter_id.name if wo.workcenter_id else 'Unknown',
                            'duration_expected': duration_expected,
                            'duration': duration_real,
                            'state': wo.state,
                        })
                        
                    except Exception as e:
                        _logger.error(f"Error processing workorder {wo.id}: {str(e)}")
                        continue
                
                operations['summary'] = {
                    'quantity': total_time,
                    'mo_cost': total_cost,
                    'real_cost': total_real_time * (cost_hour / 60) if cost_hour else 0,
                    'uom_name': 'Minutes',
                }
            
            # Labor transaction data
            labor_transactions = []
            for transaction in self.labor_transaction_ids:
                labor_transactions.append({
                    'id': transaction.id,
                    'date': transaction.transaction_date,
                    'amount': transaction.amount,
                    'description': transaction.description or '',
                    'user_name': transaction.user_id.name if transaction.user_id else '',
                })
            
            # รวม Sub MO costs
            child_mo_ids = self._get_child_manufacturing_orders() if hasattr(self, '_get_child_manufacturing_orders') else []
            sub_mo_total_labor_cost = 0
            sub_mo_total_shipping_cost = 0
            
            if child_mo_ids:
                child_mos = self.env['mrp.production'].browse(child_mo_ids)
                sub_mo_total_labor_cost = sum(child_mos.mapped('total_labor_cost'))
                sub_mo_total_shipping_cost = sum(child_mos.mapped('shipping_cost'))
            
            result = {
                'summary': summary,
                'components': components,
                'operations': operations,
                'byproducts': {'summary': {}, 'details': []},
                'labor_transactions': labor_transactions,
                'cost_summary': {
                    'material_cost': summary['mo_cost'],
                    'labor_cost': summary['total_labor_cost'],
                    'shipping_cost': summary['shipping_cost'],
                    'sub_mo_labor_cost': sub_mo_total_labor_cost,
                    'sub_mo_shipping_cost': sub_mo_total_shipping_cost,
                    'total_cost': summary['mo_cost'] + summary['total_labor_cost'] + summary['shipping_cost'] + sub_mo_total_labor_cost + sub_mo_total_shipping_cost,
                },
                'extras': {
                    'unit_mo_cost': summary['mo_cost'] / summary['quantity'] if summary['quantity'] else 0,
                    'unit_real_cost': summary['real_cost'] / summary['quantity'] if summary['quantity'] else 0,
                    'child_mo_count': len(child_mo_ids),
                }
            }
            
            return result
            
        except Exception as e:
            _logger.error(f"Critical error in get_mo_overview_data: {str(e)}")
            
            # Return minimal safe data
            return {
                'summary': {
                    'name': self.product_id.name if self.product_id else 'Unknown Product',
                    'mo_name': self.name,
                    'quantity': self.product_qty or 0,
                    'uom_name': self.product_uom_id.name if self.product_uom_id else 'Units',
                    'state': self.state,
                    'formatted_state': self._get_formatted_state(),
                    'mo_cost': 0,
                    'unit_cost': 0,
                    'real_cost': 0,
                },
                'components': [],
                'operations': {'summary': {}, 'details': []},
                'byproducts': {'summary': {}, 'details': []},
                'extras': {}
            }
    
    def _get_formatted_state(self):
        """แปลง state เป็น text ที่อ่านง่าย"""
        state_map = {
            'draft': 'Draft',
            'confirmed': 'Confirmed', 
            'progress': 'In Progress',
            'to_close': 'To Close',
            'done': 'Done',
            'cancel': 'Cancelled'
        }
        return state_map.get(self.state, self.state.title())
    
    def _get_move_formatted_state(self, state):
        """แปลง move state เป็น text"""
        state_map = {
            'draft': 'Draft',
            'waiting': 'Waiting',
            'confirmed': 'Confirmed',
            'assigned': 'Available',
            'done': 'Done',
            'cancel': 'Cancelled'
        }
        return state_map.get(state, state.title())
    
    def _calculate_mo_cost(self):
        """คำนวณต้นทุน MO แบบครอบคลุม (แก้ไขเรื่องการคำนวณซ้ำ)"""
        try:
            total_cost = 0
            
            # 1. ต้นทุนจาก raw materials (เฉพาะที่ไม่มี Sub MO)
            material_cost = 0
            child_mo_ids = self._get_child_manufacturing_orders()
            child_mo_product_ids = set()
            
            # หา product IDs ที่มี Sub MOs เพื่อไม่ให้นับซ้ำ
            if child_mo_ids:
                child_mos = self.env['mrp.production'].browse(child_mo_ids)
                child_mo_product_ids = set(child_mos.mapped('product_id.id'))
            
            for move in self.move_raw_ids:
                try:
                    # ข้ามต้นทุนของ products ที่มี Sub MOs (เพราะจะคำนวณใน Sub MO แทน)
                    if move.product_id.id in child_mo_product_ids:
                        _logger.debug(f"Skipping material cost for {move.product_id.name} - has Sub MO")
                        continue
                        
                    unit_cost = getattr(move.product_id, 'standard_price', 0) or 0
                    quantity = move.product_uom_qty or 0
                    material_cost += quantity * unit_cost
                except Exception as e:
                    _logger.warning(f"Error calculating material cost for move {move.id}: {str(e)}")
                    continue
            
            total_cost += material_cost
            
            # 2. ต้นทุนจาก operations/workorders
            operation_cost = 0
            for wo in self.workorder_ids:
                try:
                    duration = wo.duration_expected or 0  # ใช้เวลาที่คาดไว้
                    cost_per_hour = getattr(wo.workcenter_id, 'costs_hour', 0) or 0
                    # แปลงนาทีเป็นชั่วโมง
                    operation_cost += (duration / 60) * cost_per_hour
                except Exception as e:
                    _logger.warning(f"Error calculating operation cost for workorder {wo.id}: {str(e)}")
                    continue
            
            total_cost += operation_cost
            
            # 3. ต้นทุนจาก Sub MOs (ถ้ามี) - ใช้แทนต้นทุน materials ที่ข้ามไป
            sub_mo_cost = 0
            try:
                if child_mo_ids:
                    child_mos = self.env['mrp.production'].browse(child_mo_ids)
                    for child_mo in child_mos:
                        try:
                            sub_mo_cost += child_mo._calculate_mo_cost()
                        except Exception as e:
                            _logger.warning(f"Error calculating sub MO cost for {child_mo.name}: {str(e)}")
                            continue
            except Exception as e:
                _logger.warning(f"Error calculating sub MO costs: {str(e)}")
            
            total_cost += sub_mo_cost
            
            _logger.info(f"MO {self.name} cost breakdown - Materials: {material_cost}, Operations: {operation_cost}, Sub MOs: {sub_mo_cost}, Total: {total_cost}")
            
            return total_cost
            
        except Exception as e:
            _logger.error(f"Error calculating MO cost for {self.name}: {str(e)}")
            return 0

    def _calculate_real_cost(self):
        """คำนวณต้นทุนจริง (จากที่ใช้ไปแล้ว) - แก้ไขเรื่องการคำนวณซ้ำ"""
        try:
            total_real_cost = 0
            
            # 1. ต้นทุนจาก materials ที่ใช้จริง (เฉพาะที่ไม่มี Sub MO)
            real_material_cost = 0
            child_mo_ids = self._get_child_manufacturing_orders()
            child_mo_product_ids = set()
            
            # หา product IDs ที่มี Sub MOs เพื่อไม่ให้นับซ้ำ
            if child_mo_ids:
                child_mos = self.env['mrp.production'].browse(child_mo_ids)
                child_mo_product_ids = set(child_mos.mapped('product_id.id'))
            
            for move in self.move_raw_ids.filtered(lambda m: m.state == 'done'):
                try:
                    # ข้ามต้นทุนของ products ที่มี Sub MOs (เพราะจะคำนวณใน Sub MO แทน)
                    if move.product_id.id in child_mo_product_ids:
                        _logger.debug(f"Skipping real material cost for {move.product_id.name} - has Sub MO")
                        continue
                        
                    unit_cost = getattr(move.product_id, 'standard_price', 0) or 0
                    quantity_used = move.quantity or 0  # จำนวนที่ใช้จริง
                    real_material_cost += quantity_used * unit_cost
                except Exception as e:
                    _logger.warning(f"Error calculating real material cost for move {move.id}: {str(e)}")
                    continue
            
            total_real_cost += real_material_cost
            
            # 2. ต้นทุนจาก operations ที่ทำจริง
            real_operation_cost = 0
            for wo in self.workorder_ids.filtered(lambda w: w.state == 'done'):
                try:
                    duration_real = wo.duration or 0  # เวลาที่ใช้จริง
                    cost_per_hour = getattr(wo.workcenter_id, 'costs_hour', 0) or 0
                    # แปลงนาทีเป็นชั่วโมง
                    real_operation_cost += (duration_real / 60) * cost_per_hour
                except Exception as e:
                    _logger.warning(f"Error calculating real operation cost for workorder {wo.id}: {str(e)}")
                    continue
                    
            total_real_cost += real_operation_cost
            
            # 3. ต้นทุนจาก Sub MOs ที่เสร็จแล้ว - ใช้แทนต้นทุน materials ที่ข้ามไป
            real_sub_mo_cost = 0
            try:
                if child_mo_ids:
                    child_mos = self.env['mrp.production'].browse(child_mo_ids)
                    for child_mo in child_mos.filtered(lambda m: m.state == 'done'):
                        try:
                            real_sub_mo_cost += child_mo._calculate_real_cost()
                        except Exception as e:
                            _logger.warning(f"Error calculating real sub MO cost for {child_mo.name}: {str(e)}")
                            continue
            except Exception as e:
                _logger.warning(f"Error calculating real sub MO costs: {str(e)}")
                
            total_real_cost += real_sub_mo_cost
            
            _logger.info(f"MO {self.name} real cost breakdown - Materials: {real_material_cost}, Operations: {real_operation_cost}, Sub MOs: {real_sub_mo_cost}, Total: {total_real_cost}")
            
            return total_real_cost
            
        except Exception as e:
            _logger.error(f"Error calculating real MO cost for {self.name}: {str(e)}")
            return 0
    
    def _get_receipt_info(self, move):
        """ข้อมูลการรับสินค้า"""
        if move.state == 'done':
            return {
                'display': 'Received',
                'type': 'available',
                'decorator': 'success',
                'date': move.date
            }
        elif getattr(move, 'reserved_availability', 0) >= move.product_uom_qty:
            return {
                'display': 'Available',
                'type': 'available', 
                'decorator': 'success',
                'date': False
            }
        else:
            return {
                'display': 'Not Available',
                'type': 'unavailable',
                'decorator': 'danger', 
                'date': False
            }
    
    def _get_components_from_bom(self):
        """ดึงข้อมูล components จาก BOM ถ้าไม่มี raw moves"""
        components = []
        try:
            if not self.bom_id:
                return components
            
            for bom_line in self.bom_id.bom_line_ids:
                product = bom_line.product_id
                quantity_needed = bom_line.product_qty * self.product_qty
                
                # ดึงข้อมูล stock
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', product.id),
                    ('location_id.usage', '=', 'internal')
                ])
                quantity_on_hand = sum(quants.mapped('quantity'))
                
                # สร้าง display name แบบ [REF] Product Name
                internal_ref = getattr(product, 'default_code', '') or ''
                if internal_ref:
                    display_name = f"[{internal_ref}] {product.name}"
                else:
                    display_name = product.name
                
                component_data = {
                    'summary': {
                        'id': bom_line.id,
                        'name': display_name,
                        'product_id': product.id,
                        'quantity': quantity_needed,
                        'uom_name': bom_line.product_uom_id.name,
                        'quantity_on_hand': quantity_on_hand,
                        'quantity_free': product.qty_available,
                        'quantity_reserved': 0,  # BOM ยังไม่ได้ reserve
                        'state': 'draft' if quantity_on_hand >= quantity_needed else 'to_order',
                        'formatted_state': 'Available' if quantity_on_hand >= quantity_needed else 'To Order',
                        'mo_cost': quantity_needed * product.standard_price,
                        'unit_cost': product.standard_price,
                        'description': getattr(product, 'description', '') or getattr(product, 'description_sale', '') or '',
                        'receipt': {
                            'display': 'Available' if quantity_on_hand >= quantity_needed else 'Not Available',
                            'type': 'available' if quantity_on_hand >= quantity_needed else 'unavailable',
                            'decorator': 'success' if quantity_on_hand >= quantity_needed else 'danger',
                            'date': False
                        },
                    },
                    'sub_mos': self._get_sub_mos_for_component(product)
                }
                components.append(component_data)
                
        except Exception as e:
            _logger.error(f"Error getting components from BOM: {str(e)}")
            
        return components
    
    def _get_operations_from_bom(self):
        """ดึงข้อมูล operations จาก BOM ถ้าไม่มี workorders"""
        operations = {
            'summary': {
                'quantity': 0,
                'mo_cost': 0,
                'real_cost': 0,
                'uom_name': 'Minutes',
            },
            'details': []
        }
        
        try:
            if not self.bom_id:
                return operations
                
            total_time = 0
            total_cost = 0
            
            for operation in self.bom_id.operation_ids:
                time_needed = operation.time_cycle * self.product_qty
                cost_needed = time_needed * (operation.workcenter_id.costs_hour or 0) / 60  # แปลงเป็นชั่วโมง
                
                total_time += time_needed
                total_cost += cost_needed
                
                operations['details'].append({
                    'name': operation.name,
                    'workcenter': operation.workcenter_id.name,
                    'duration_expected': time_needed,
                    'duration': 0,  # ยังไม่ได้ทำ
                    'state': 'draft',
                })
                
            operations['summary'] = {
                'quantity': total_time,
                'mo_cost': total_cost,
                'real_cost': 0,
                'uom_name': 'Minutes',
            }
            
        except Exception as e:
            _logger.error(f"Error getting operations from BOM: {str(e)}")
            
        return operations

    def debug_mo_data(self):
        """Debug method เพื่อดูข้อมูล MO อย่างละเอียด"""
        self.ensure_one()
        
        debug_info = []
        debug_info.append(f"=== DEBUG MO DATA: {self.name} ===")
        debug_info.append(f"ID: {self.id}")
        debug_info.append(f"Product: {self.product_id.name} (ID: {self.product_id.id})")
        debug_info.append(f"State: {self.state}")
        debug_info.append(f"Quantity: {self.product_qty} {self.product_uom_id.name}")
        debug_info.append("")
        
        # BOM Info
        debug_info.append(f"BOM: {self.bom_id.display_name if self.bom_id else 'No BOM'}")
        if self.bom_id:
            debug_info.append(f"BOM ID: {self.bom_id.id}")
            debug_info.append(f"BOM Lines: {len(self.bom_id.bom_line_ids)}")
            for line in self.bom_id.bom_line_ids:
                debug_info.append(f"  - {line.product_id.name}: {line.product_qty} {line.product_uom_id.name}")
            debug_info.append(f"BOM Operations: {len(self.bom_id.operation_ids)}")
            for op in self.bom_id.operation_ids:
                debug_info.append(f"  - {op.name}: {op.time_cycle} min @ {op.workcenter_id.name}")
        debug_info.append("")
        
        # Raw Moves
        debug_info.append(f"Raw Moves: {len(self.move_raw_ids)}")
        for move in self.move_raw_ids:
            debug_info.append(f"  - {move.product_id.name}: {move.product_uom_qty} {move.product_uom.name} - {move.state}")
        debug_info.append("")
        
        # Workorders
        debug_info.append(f"Workorders: {len(self.workorder_ids)}")
        for wo in self.workorder_ids:
            debug_info.append(f"  - {wo.name}: {wo.duration_expected} min @ {wo.workcenter_id.name} - {wo.state}")
        debug_info.append("")
        
        # Finished Moves
        debug_info.append(f"Finished Moves: {len(self.move_finished_ids)}")
        for move in self.move_finished_ids:
            debug_info.append(f"  - {move.product_id.name}: {move.product_uom_qty} {move.product_uom.name} - {move.state}")
        
        message = "\n".join(debug_info)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': f'Debug MO Data - {self.name}',
                'message': message,
                'type': 'info',
                'sticky': True,
            }
        }

    def _get_sub_mos_for_component(self, product):
        """หา MO ย่อยที่ produce product นี้ และเกี่ยวข้องกับ MO หลักจริงๆ"""
        try:
            # หา MO ย่อยที่เกี่ยวข้องกับ MO หลักก่อน
            child_mo_ids = self._get_child_manufacturing_orders()
            
            if not child_mo_ids:
                # ถ้าไม่มี MO ย่อย ให้ return empty list
                _logger.info(f"No child MOs found for product {product.name} in MO {self.name}")
                return []
            
            # หา Sub MOs ที่ produce product นี้ และอยู่ในรายการ child MOs
            sub_mos = self.env['mrp.production'].search([
                ('id', 'in', child_mo_ids),  # เฉพาะ MO ย่อยที่เกี่ยวข้อง
                ('product_id', '=', product.id),  # ต้อง produce product นี้เท่านั้น
                ('state', 'in', ['draft', 'confirmed', 'progress', 'to_close', 'done'])
            ], limit=5)
            
            _logger.info(f"Found {len(sub_mos)} related Sub MOs for product {product.name} in MO {self.name}")
            
            result = []
            for sub_mo in sub_mos:
                # ดึงข้อมูล components ของ MO ย่อย
                sub_components = []
                
                _logger.info(f"Processing Sub MO {sub_mo.name} - has {len(sub_mo.move_raw_ids)} raw moves")
                
                # ถ้าไม่มี raw moves ให้ลองดึงจาก BOM
                if not sub_mo.move_raw_ids and sub_mo.bom_id:
                    _logger.info(f"Sub MO {sub_mo.name} has no raw moves, trying BOM with {len(sub_mo.bom_id.bom_line_ids)} lines")
                    for bom_line in sub_mo.bom_id.bom_line_ids[:10]:
                        try:
                            sub_product = bom_line.product_id
                            sub_unit_cost = getattr(sub_product, 'standard_price', 0) or 0
                            quantity_needed = bom_line.product_qty * sub_mo.product_qty
                            sub_total_cost = quantity_needed * sub_unit_cost
                            
                            # สร้าง display name แบบ [REF] Product Name สำหรับ Sub MO component
                            sub_internal_ref = getattr(sub_product, 'default_code', '') or ''
                            if sub_internal_ref:
                                sub_display_name = f"[{sub_internal_ref}] {sub_product.name}"
                            else:
                                sub_display_name = sub_product.name
                            
                            sub_component = {
                                'id': f"bom_{bom_line.id}",
                                'name': sub_display_name,
                                'product_id': sub_product.id,
                                'quantity': quantity_needed,
                                'uom_name': bom_line.product_uom_id.name,
                                'state': 'draft',
                                'formatted_state': 'From BOM',
                                'unit_cost': sub_unit_cost,
                                'total_cost': sub_total_cost,
                            }
                            sub_components.append(sub_component)
                            
                        except Exception as e:
                            _logger.warning(f"Error processing sub BOM line {bom_line.id}: {str(e)}")
                            continue
                
                # ดึงจาก raw moves (วิธีเดิม)
                for sub_move in sub_mo.move_raw_ids[:10]:  # จำกัดไม่เกิน 10 components
                    try:
                        sub_product = sub_move.product_id
                        sub_unit_cost = getattr(sub_product, 'standard_price', 0) or 0
                        sub_total_cost = sub_move.product_uom_qty * sub_unit_cost
                        
                        # สร้าง display name แบบ [REF] Product Name สำหรับ Sub MO component
                        sub_internal_ref = getattr(sub_product, 'default_code', '') or ''
                        if sub_internal_ref:
                            sub_display_name = f"[{sub_internal_ref}] {sub_product.name}"
                        else:
                            sub_display_name = sub_product.name
                        
                        sub_component = {
                            'id': sub_move.id,
                            'name': sub_display_name,
                            'product_id': sub_product.id,
                            'quantity': sub_move.product_uom_qty,
                            'uom_name': getattr(sub_move.product_uom, 'name', 'Units'),
                            'state': sub_move.state,
                            'formatted_state': self._get_move_formatted_state(sub_move.state),
                            'unit_cost': sub_unit_cost,
                            'total_cost': sub_total_cost,
                        }
                        sub_components.append(sub_component)
                        
                    except Exception as e:
                        _logger.warning(f"Error processing sub component {sub_move.id}: {str(e)}")
                        continue
                
                sub_mo_data = {
                    'id': sub_mo.id,
                    'name': sub_mo.name,
                    'product_name': sub_mo.product_id.name,
                    'quantity': sub_mo.product_qty,
                    'uom_name': sub_mo.product_uom_id.name,
                    'state': sub_mo.state,
                    'formatted_state': self._get_formatted_state_for_mo(sub_mo.state),
                    'components': sub_components,
                    'total_cost': sub_mo._calculate_mo_cost()  # ใช้ต้นทุนจริงจาก _calculate_mo_cost()
                }
                result.append(sub_mo_data)
                
                _logger.info(f"Sub MO {sub_mo.name} added with {len(sub_components)} components")
            
            return result
            
        except Exception as e:
            _logger.error(f"Error getting sub MOs for product {product.name}: {str(e)}")
            return []
    
    def _get_formatted_state_for_mo(self, state):
        """แปลง MO state เป็น text ที่อ่านง่าย"""
        state_map = {
            'draft': 'Draft',
            'confirmed': 'Confirmed',
            'progress': 'In Progress', 
            'to_close': 'To Close',
            'done': 'Done',
            'cancel': 'Cancelled'
        }
        return state_map.get(state, state.title())

    def action_export_mo_overview_excel(self):
        """Export MO Overview เป็น Excel file"""
        self.ensure_one()
        
        try:
            import xlsxwriter
            import base64
            from io import BytesIO
            from datetime import datetime
            
            # สร้าง workbook
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            
            # สร้าง formats แบบคลีนๆ
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#E7E6E6',
                'border': 1
            })
            
            # ดึงข้อมูล
            overview_data = self.get_mo_overview_data()
            
            # Sheet 1: MO Cost Summary (รวมทุกอย่าง)
            self._create_mo_cost_summary_sheet(workbook, overview_data, header_format)
            
            # Sheet 2: Labor & Operations Details
            self._create_labor_operations_sheet(workbook, overview_data, header_format)
            
            workbook.close()
            output.seek(0)
            
            # สร้าง attachment
            filename = f"MO_Overview_{self.name.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': base64.b64encode(output.read()),
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            })
            
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'new',
            }
            
        except ImportError:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Missing Library',
                    'message': 'กรุณาติดตั้ง xlsxwriter library: pip install xlsxwriter',
                    'type': 'warning',
                }
            }
        except Exception as e:
            _logger.error(f"Error exporting Excel: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Export Error',
                    'message': f'เกิดข้อผิดพลาดในการ export: {str(e)}',
                    'type': 'error',
                }
            }

    def _create_mo_cost_summary_sheet(self, workbook, overview_data, header_format):
        """สร้าง Sheet 1: MO Cost Summary - รวมทุกข้อมูลสำคัญ"""
        worksheet = workbook.add_worksheet('MO Cost Summary')
        
        # Set column widths
        worksheet.set_column('A:A', 25)  # Label
        worksheet.set_column('B:B', 20)  # Value
        worksheet.set_column('C:C', 40)  # Description
        
        row = 0
        
        # === MO Header Information ===
        worksheet.write(row, 0, 'MO INFORMATION', header_format)
        worksheet.write(row, 1, '', header_format)
        worksheet.write(row, 2, '', header_format)
        row += 1
        
        mo_info = [
            ('MO Name', overview_data['summary']['mo_name'], 'เลขที่คำสั่งผลิต'),
            ('Product', overview_data['summary']['name'], 'ชื่อสินค้า'),
            ('Quantity', f"{overview_data['summary']['quantity']} {overview_data['summary']['uom_name']}", 'จำนวนที่ผลิต'),
            ('State', overview_data['summary']['formatted_state'], 'สถานะ'),
            ('Customer', overview_data['summary']['customer_name'], 'ชื่อลูกค้า'),
            ('Sales Team', overview_data['summary']['sales_team'], 'ทีมขาย'),
            ('Technician Team', overview_data['summary']['technician_team'], 'ทีมช่าง'),
        ]
        
        for label, value, desc in mo_info:
            worksheet.write(row, 0, label)
            worksheet.write(row, 1, value)
            worksheet.write(row, 2, desc)
            row += 1
        
        row += 1  # Empty row
        
        # === COST BREAKDOWN ===
        worksheet.write(row, 0, 'COST BREAKDOWN', header_format)
        worksheet.write(row, 1, 'Amount (THB)', header_format)
        worksheet.write(row, 2, 'Description', header_format)
        row += 1
        
        cost_summary = overview_data.get('cost_summary', {})
        cost_items = [
            ('Material Cost', cost_summary.get('material_cost', 0), 'ค่าวัสดุและ Components'),
            ('Labor Cost (This MO)', cost_summary.get('labor_cost', 0), 'ค่าแรง MO หลัก'),
            ('Sub MO Labor Cost', cost_summary.get('sub_mo_labor_cost', 0), 'ค่าแรง Sub MOs'),
            ('Shipping Cost (This MO)', cost_summary.get('shipping_cost', 0), 'ค่าขนส่ง MO หลัก'),
            ('Sub MO Shipping Cost', cost_summary.get('sub_mo_shipping_cost', 0), 'ค่าขนส่ง Sub MOs'),
        ]
        
        total_cost = 0
        for label, amount, desc in cost_items:
            worksheet.write(row, 0, label)
            worksheet.write(row, 1, f"{amount:,.2f}")
            worksheet.write(row, 2, desc)
            total_cost += amount
            row += 1
        
        # Total row
        worksheet.write(row, 0, 'TOTAL COST', header_format)
        worksheet.write(row, 1, f"{total_cost:,.2f}", header_format)
        worksheet.write(row, 2, 'ต้นทุนรวมทั้งหมด', header_format)
        row += 2
        
        # === UNIT COSTS ===
        quantity = overview_data['summary']['quantity'] or 1
        worksheet.write(row, 0, 'UNIT COSTS', header_format)
        worksheet.write(row, 1, 'Per Unit (THB)', header_format)
        worksheet.write(row, 2, 'Description', header_format)
        row += 1
        
        unit_costs = [
            ('Unit Material Cost', cost_summary.get('material_cost', 0) / quantity, 'ต้นทุนวัสดุต่อหน่วย'),
            ('Unit Labor Cost', (cost_summary.get('labor_cost', 0) + cost_summary.get('sub_mo_labor_cost', 0)) / quantity, 'ต้นทุนแรงงานต่อหน่วย'),
            ('Unit Shipping Cost', (cost_summary.get('shipping_cost', 0) + cost_summary.get('sub_mo_shipping_cost', 0)) / quantity, 'ต้นทุนขนส่งต่อหน่วย'),
            ('Unit Total Cost', total_cost / quantity, 'ต้นทุนรวมต่อหน่วย'),
        ]
        
        for label, amount, desc in unit_costs:
            worksheet.write(row, 0, label)
            worksheet.write(row, 1, f"{amount:,.2f}")
            worksheet.write(row, 2, desc)
            row += 1
        
        row += 2
        
        # === LABOR TRANSACTION HISTORY ===
        labor_transactions = overview_data.get('labor_transactions', [])
        if labor_transactions:
            worksheet.write(row, 0, 'LABOR TRANSACTION HISTORY', header_format)
            worksheet.write(row, 1, '', header_format)
            worksheet.write(row, 2, '', header_format)
            row += 1
            
            # Headers for labor transactions
            worksheet.write(row, 0, 'Date', header_format)
            worksheet.write(row, 1, 'Amount (THB)', header_format)
            worksheet.write(row, 2, 'Description', header_format)
            worksheet.write(row, 3, 'By User', header_format)
            row += 1
            
            for transaction in labor_transactions:
                worksheet.write(row, 0, transaction.get('date', '').strftime('%Y-%m-%d %H:%M') if transaction.get('date') else '')
                worksheet.write(row, 1, f"{transaction.get('amount', 0):,.2f}")
                worksheet.write(row, 2, transaction.get('description', ''))
                worksheet.write(row, 3, transaction.get('user_name', ''))
                row += 1
            
            # Labor total
            labor_total = sum(t.get('amount', 0) for t in labor_transactions)
            worksheet.write(row, 0, 'LABOR TOTAL', header_format)
            worksheet.write(row, 1, f"{labor_total:,.2f}", header_format)
            worksheet.write(row, 2, 'รวมค่าแรงทั้งหมด', header_format)

    def _create_labor_operations_sheet(self, workbook, overview_data, header_format):
        """สร้าง Sheet 2: Labor & Operations Details"""
        worksheet = workbook.add_worksheet('Labor & Operations')
        
        # Set column widths
        worksheet.set_column('A:A', 30)  # Operation/Component Name
        worksheet.set_column('B:B', 20)  # Workcenter/Details
        worksheet.set_column('C:C', 15)  # Duration/Quantity
        worksheet.set_column('D:D', 15)  # Unit Cost
        worksheet.set_column('E:E', 15)  # Total Cost
        worksheet.set_column('F:F', 15)  # State
        worksheet.set_column('G:G', 40)  # Description
        
        row = 0
        
        # === WORK ORDERS ===
        operations = overview_data.get('operations', {}).get('details', [])
        if operations:
            worksheet.write(row, 0, 'WORK ORDERS', header_format)
            worksheet.write(row, 1, 'Workcenter', header_format)
            worksheet.write(row, 2, 'Duration (min)', header_format)
            worksheet.write(row, 3, 'Cost/Min (THB)', header_format)
            worksheet.write(row, 4, 'Total Cost (THB)', header_format)
            worksheet.write(row, 5, 'State', header_format)
            worksheet.write(row, 6, 'Description', header_format)
            row += 1
            
            for operation in operations:
                duration = operation.get('duration_expected', 0)
                cost_per_min = 10  # Assuming 10 THB/min
                total_cost = duration * cost_per_min
                
                worksheet.write(row, 0, operation.get('name', ''))
                worksheet.write(row, 1, operation.get('workcenter', ''))
                worksheet.write(row, 2, duration)
                worksheet.write(row, 3, f"{cost_per_min:,.2f}")
                worksheet.write(row, 4, f"{total_cost:,.2f}")
                worksheet.write(row, 5, operation.get('state', ''))
                worksheet.write(row, 6, 'Work Order Operation')
                row += 1
        
        row += 2
        
        # === COMPONENTS ===
        components = overview_data.get('components', [])
        if components:
            worksheet.write(row, 0, 'COMPONENTS', header_format)
            worksheet.write(row, 1, 'Product Code', header_format)
            worksheet.write(row, 2, 'Quantity', header_format)
            worksheet.write(row, 3, 'Unit Cost (THB)', header_format)
            worksheet.write(row, 4, 'Total Cost (THB)', header_format)
            worksheet.write(row, 5, 'State', header_format)
            worksheet.write(row, 6, 'Description', header_format)
            row += 1
            
            for component in components:
                summary = component.get('summary', {})
                quantity = summary.get('quantity', 0)
                total_cost = summary.get('mo_cost', 0)
                unit_cost = total_cost / quantity if quantity > 0 else 0
                
                worksheet.write(row, 0, summary.get('name', ''))
                worksheet.write(row, 1, summary.get('product_id', ''))
                worksheet.write(row, 2, f"{quantity} {summary.get('uom_name', '')}")
                worksheet.write(row, 3, f"{unit_cost:,.2f}")
                worksheet.write(row, 4, f"{total_cost:,.2f}")
                worksheet.write(row, 5, summary.get('formatted_state', ''))
                worksheet.write(row, 6, summary.get('description', ''))
                row += 1
                
                # Sub MOs for this component
                sub_mos = component.get('sub_mos', [])
                for sub_mo in sub_mos:
                    sub_mo_quantity = sub_mo.get('quantity', 0)
                    sub_mo_total_cost = sub_mo.get('total_cost', 0)
                    sub_mo_unit_cost = sub_mo_total_cost / sub_mo_quantity if sub_mo_quantity > 0 else 0
                    
                    worksheet.write(row, 0, f"  └─ Sub MO: {sub_mo.get('name', '')}")
                    worksheet.write(row, 1, sub_mo.get('product_name', ''))
                    worksheet.write(row, 2, f"{sub_mo_quantity} {sub_mo.get('uom_name', '')}")
                    worksheet.write(row, 3, f"{sub_mo_unit_cost:,.2f}")
                    worksheet.write(row, 4, f"{sub_mo_total_cost:,.2f}")
                    worksheet.write(row, 5, sub_mo.get('formatted_state', ''))
                    worksheet.write(row, 6, 'Sub Manufacturing Order')
                    row += 1
                    
                    # แสดง Components ของ Sub MO
                    sub_components = sub_mo.get('components', [])
                    for sub_comp in sub_components:
                        sub_comp_quantity = sub_comp.get('quantity', 0)
                        sub_comp_total_cost = sub_comp.get('total_cost', 0)
                        sub_comp_unit_cost = sub_comp_total_cost / sub_comp_quantity if sub_comp_quantity > 0 else 0
                        
                        worksheet.write(row, 0, f"      ├─ {sub_comp.get('name', '')}")
                        worksheet.write(row, 1, f"Sub Component")
                        worksheet.write(row, 2, f"{sub_comp_quantity} {sub_comp.get('uom_name', '')}")
                        worksheet.write(row, 3, f"{sub_comp_unit_cost:,.2f}")
                        worksheet.write(row, 4, f"{sub_comp_total_cost:,.2f}")
                        worksheet.write(row, 5, sub_comp.get('formatted_state', ''))
                        worksheet.write(row, 6, f"Component of {sub_mo.get('name', '')}")
                        row += 1

    def _create_components_with_submo_sheet(self, workbook, overview_data, header_format):
        """สร้าง Components + Sub MOs Sheet"""
        worksheet = workbook.add_worksheet('Components')
        
        # Set column widths
        worksheet.set_column('A:A', 45)  # Component Name (with reference)
        worksheet.set_column('B:B', 40)  # Description
        worksheet.set_column('C:C', 12)  # Quantity
        worksheet.set_column('D:D', 10)  # UOM
        worksheet.set_column('E:E', 15)  # Total Cost
        
        # Headers
        headers = ['Component Name', 'Description', 'Quantity', 'UOM', 'Total Cost']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        row = 1
        
        # เขียน MO Components
        for component in overview_data.get('components', []):
            summary = component['summary']
            
            # ดึงข้อมูล product เพิ่มเติม
            try:
                product = self.env['product.product'].browse(summary.get('product_id'))
                internal_ref = getattr(product, 'default_code', '') or ''
                description = product.description or product.description_sale or ''
                
                # สร้าง display name แบบ [REF] Product Name
                if internal_ref:
                    display_name = f"[{internal_ref}] {summary['name']}"
                else:
                    display_name = summary['name']
            except:
                display_name = summary['name']
                description = ''
            
            worksheet.write(row, 0, display_name)
            worksheet.write(row, 1, description)
            worksheet.write(row, 2, summary['quantity'])
            worksheet.write(row, 3, summary['uom_name'])
            worksheet.write(row, 4, summary['mo_cost'])
            row += 1
            
            # เขียน Sub MOs ของ component นี้
            for sub_mo in component.get('sub_mos', []):
                worksheet.write(row, 0, f"  └─ Sub MO: {sub_mo['name']} ({sub_mo['product_name']})")
                worksheet.write(row, 1, f"Sub Manufacturing Order")
                worksheet.write(row, 2, sub_mo['quantity'])
                worksheet.write(row, 3, sub_mo['uom_name'])
                worksheet.write(row, 4, sub_mo['total_cost'])
                row += 1
                
                # แสดงวัสดุของ Sub MO
                for sub_component in sub_mo.get('components', []):
                    # ดึงข้อมูล product ของ sub component
                    try:
                        sub_product = self.env['product.product'].browse(sub_component.get('product_id'))
                        sub_internal_ref = getattr(sub_product, 'default_code', '') or ''
                        sub_description = sub_product.description or sub_product.description_sale or ''
                        
                        # สร้าง display name แบบ [REF] Product Name
                        if sub_internal_ref:
                            sub_display_name = f"    ├─ [{sub_internal_ref}] {sub_component['name']}"
                        else:
                            sub_display_name = f"    ├─ {sub_component['name']}"
                    except:
                        sub_display_name = f"    ├─ {sub_component['name']}"
                        sub_description = ''
                    
                    worksheet.write(row, 0, sub_display_name)
                    worksheet.write(row, 1, sub_description)
                    worksheet.write(row, 2, sub_component['quantity'])
                    worksheet.write(row, 3, sub_component['uom_name'])
                    worksheet.write(row, 4, sub_component['total_cost'])
                    row += 1

    def _create_deliveries_simple_sheet(self, workbook, header_format):
        """สร้าง Deliveries Sheet"""
        worksheet = workbook.add_worksheet('Deliveries')
        
        # Set column widths
        worksheet.set_column('A:A', 45)  # Product (with reference)
        worksheet.set_column('B:B', 40)  # Description
        worksheet.set_column('C:C', 12)  # Quantity
        worksheet.set_column('D:D', 10)  # UOM
        worksheet.set_column('E:E', 15)  # Total Cost
        worksheet.set_column('F:F', 20)  # Origin MO
        
        # Headers
        headers = ['Product', 'Description', 'Quantity', 'UOM', 'Total Cost', 'Origin MO']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        row = 1
        
        # ดึงข้อมูล deliveries จาก MO หลักและ Sub MOs ทั้งหมด
        try:
            # หา MO ย่อยทั้งหมด (recursive)
            child_mo_ids = self._get_child_manufacturing_orders()
            all_mo_ids = [self.id] + child_mo_ids
            
            # สร้าง list ของ MO names สำหรับค้นหา origin
            all_mo_records = self.env['mrp.production'].browse(all_mo_ids)
            all_mo_names = all_mo_records.mapped('name')
            
            _logger.info(f"Searching deliveries for MOs: {all_mo_names}")
            
            # วิธีที่ 1: หาจาก origin ใน stock.picking (รวม MO ย่อย)
            deliveries_by_origin = self.env['stock.picking'].search([
                ('origin', 'in', all_mo_names),
                ('picking_type_id.code', '=', 'outgoing'),
                ('state', '!=', 'cancel')
            ])
            
            # วิธีที่ 2: หาจาก stock.move ที่เกี่ยวข้องกับ MO ทั้งหมด
            moves_from_production = self.env['stock.move'].search([
                ('production_id', 'in', all_mo_ids),
                ('picking_id', '!=', False),
                ('state', '!=', 'cancel')
            ])
            deliveries_from_moves = moves_from_production.mapped('picking_id')
            
            # วิธีที่ 3: หาจาก finished goods moves ของ MO ทั้งหมด
            finished_moves = self.env['stock.move'].search([
                ('production_id', 'in', all_mo_ids),
                ('product_id', 'in', all_mo_records.mapped('product_id').ids),
                ('picking_id', '!=', False),
                ('state', '!=', 'cancel')
            ])
            deliveries_from_finished = finished_moves.mapped('picking_id')
            
            # รวมทุกวิธี
            all_deliveries = deliveries_by_origin | deliveries_from_moves | deliveries_from_finished
            
            _logger.info(f"Found {len(all_deliveries)} deliveries for export")
            
            # เขียนข้อมูลลง Excel
            for delivery in all_deliveries:
                for move in delivery.move_ids:
                    if move.state != 'cancel':
                        product = move.product_id
                        internal_ref = getattr(product, 'default_code', '') or ''
                        description = product.description or product.description_sale or ''
                        
                        # สร้าง display name แบบ [REF] Product Name
                        if internal_ref:
                            display_name = f"[{internal_ref}] {product.name}"
                        else:
                            display_name = product.name
                        
                        worksheet.write(row, 0, display_name)
                        worksheet.write(row, 1, description)
                        worksheet.write(row, 2, move.product_uom_qty)
                        worksheet.write(row, 3, move.product_uom.name if move.product_uom else '')
                        worksheet.write(row, 4, move.product_uom_qty * product.standard_price)
                        worksheet.write(row, 5, delivery.origin or delivery.name)
                        row += 1
            
            # ถ้าไม่มีข้อมูล ให้เขียน message
            if row == 1:
                worksheet.write(row, 0, 'No delivery data found')
                worksheet.write(row, 1, '')
                worksheet.write(row, 2, '')
                worksheet.write(row, 3, '')
                worksheet.write(row, 4, '')
                worksheet.write(row, 5, f'Searched in {len(all_mo_names)} MOs')
                
        except Exception as e:
            _logger.error(f"Error creating deliveries sheet: {str(e)}")
            worksheet.write(row, 0, f'Error: {str(e)}')
            worksheet.write(row, 1, '')
            worksheet.write(row, 2, '')
            worksheet.write(row, 3, '')
            worksheet.write(row, 4, '')
            worksheet.write(row, 5, '')

    def _create_operations_simple_sheet(self, workbook, overview_data, header_format):
        """สร้าง Operations Sheet"""
        worksheet = workbook.add_worksheet('Operations')
        
        # Set column widths
        worksheet.set_column('A:A', 30)  # Operation Name
        worksheet.set_column('B:B', 20)  # Workcenter
        worksheet.set_column('C:C', 15)  # Duration
        worksheet.set_column('D:D', 10)  # State
        
        # Headers
        headers = ['Operation Name', 'Workcenter', 'Duration (min)', 'State']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        row = 1
        for operation in overview_data.get('operations', {}).get('details', []):
            worksheet.write(row, 0, operation['name'])
            worksheet.write(row, 1, operation['workcenter'])
            worksheet.write(row, 2, operation['duration_expected'])
            worksheet.write(row, 3, operation['state'])
            row += 1 