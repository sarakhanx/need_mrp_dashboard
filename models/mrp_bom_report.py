import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

class MrpBomReport(models.AbstractModel):
    _name = 'report.need_mrp_dashboard.report_mrp_bom_materials'
    _description = 'BOM Materials Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        _logger.info(f"Generating BOM Materials report for MO IDs: {docids}")
        docs = self.env['mrp.production'].browse(docids)
        materials = {}
        
        for mo in docs:
            _logger.info(f"Processing MO: {mo.name}")
            for component in mo.move_raw_ids.filtered(lambda m: m.state not in ['cancel']):
                # Get quantities based on move state
                to_consume = component.product_uom_qty  # จำนวนที่ต้องใช้ตามแผน
                reserved_qty = 0.0
                component_state = component.state

                if component_state == 'assigned':
                    # If move is fully assigned, reserved quantity equals demand
                    reserved_qty = component.product_uom_qty
                elif component_state == 'partially_available':
                    # If partially available, sum reserved quantities from move lines
                    reserved_qty = sum(line.quantity for line in component.move_line_ids)
                # For other states (confirmed, waiting, available), reserved_qty remains 0

                _logger.info(f"  Component: {component.product_id.name}, State: {component_state}, Demand: {to_consume}, Calculated Reserved: {reserved_qty}")

                # Process main components
                comp_key = str(component.product_id.id)
                if comp_key not in materials:
                    materials[comp_key] = {
                        'product': component.product_id,
                        'uom': component.product_uom,
                        'qty': to_consume,  # จำนวนที่ต้องใช้
                        'reserved_qty': reserved_qty,  # จำนวนที่จองแล้ว
                        'subcomponents': {}
                    }
                else:
                    materials[comp_key]['qty'] += to_consume
                    materials[comp_key]['reserved_qty'] += reserved_qty

                # Process subcomponents if BOM exists
                bom = component.product_id.bom_ids and component.product_id.bom_ids[0] or False
                if bom:
                    _logger.info(f"    Processing BOM for {component.product_id.name}")
                    for subcomp in bom.bom_line_ids:
                        subcomp_key = str(subcomp.product_id.id)
                        subcomp_qty = subcomp.product_qty * to_consume
                        
                        # Get reserved quantity for subcomponent from stock moves
                        subcomp_moves = self.env['stock.move'].search([
                            ('product_id', '=', subcomp.product_id.id),
                            ('raw_material_production_id', '=', mo.id),
                            ('state', 'not in', ['cancel', 'draft'])
                        ])
                        
                        # Sum up reserved quantities based on move state
                        subcomp_reserved = 0.0
                        for move in subcomp_moves:
                            move_state = move.state
                            move_reserved = 0.0
                            if move_state == 'assigned':
                                move_reserved = move.product_uom_qty
                            elif move_state == 'partially_available':
                                move_reserved = sum(line.quantity for line in move.move_line_ids)
                            subcomp_reserved += move_reserved
                            _logger.info(f"      SubComp Move: {move.product_id.name}, State: {move_state}, Sub Reserved Calc: {move_reserved}")
                            
                        _logger.info(f"    SubComp: {subcomp.product_id.name}, Total Sub Reserved: {subcomp_reserved}")
                        
                        if subcomp_key not in materials:
                            materials[subcomp_key] = {
                                'product': subcomp.product_id,
                                'uom': subcomp.product_uom_id,
                                'qty': subcomp_qty,
                                'reserved_qty': subcomp_reserved,
                                'subcomponents': {},
                                'is_subcomponent': True,
                                'parent_components': [comp_key]
                            }
                        else:
                            materials[subcomp_key]['qty'] += subcomp_qty
                            materials[subcomp_key]['reserved_qty'] += subcomp_reserved
                            if comp_key not in materials[subcomp_key].get('parent_components', []):
                                materials[subcomp_key]['parent_components'].append(comp_key)

        _logger.info(f"Final materials data for report: {materials}")
        return {
            'doc_ids': docids,
            'doc_model': 'mrp.production',
            'docs': docs,
            'materials': materials,
        } 