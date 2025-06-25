from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class BomMaterialsReportParser(models.AbstractModel):
    _name = 'report.need_mrp_dashboard.report_mrp_bom_materials'
    _description = 'BOM Materials Report Parser'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Override to track report printing"""
        
        # Get the manufacturing orders
        docs = self.env['mrp.production'].browse(docids)
        
        # Mark all selected MOs as having BOM Materials Report printed
        for mo in docs:
            mo.mark_bom_materials_printed()
            _logger.info(f"Marked BOM Materials Report as printed for MO: {mo.name}")
        
        # Get materials data (existing logic from your current report)
        materials = self._get_materials_data(docs)
        
        return {
            'doc_ids': docids,
            'doc_model': 'mrp.production',
            'docs': docs,
            'materials': materials,
        }
    
    def _get_materials_data(self, docs):
        """Get materials data for the report (existing logic)"""
        materials = {}
        
        for mo in docs:
            if not mo.bom_id:
                continue
                
            # Process BOM components
            for line in mo.bom_id.bom_line_ids:
                product = line.product_id
                key = product.id
                
                if key not in materials:
                    materials[key] = {
                        'product': product,
                        'qty': 0.0,
                        'reserved_qty': 0.0,
                        'uom': line.product_uom_id,
                        'is_subcomponent': False,
                        'parents': [],
                    }
                
                # Calculate quantity needed
                qty_needed = (line.product_qty / mo.bom_id.product_qty) * mo.product_qty
                materials[key]['qty'] += qty_needed
                
                # Get reserved quantity from stock moves - using correct field for Odoo 17
                reserved_qty = sum(
                    move.quantity for move in mo.move_raw_ids
                    if move.product_id.id == product.id and move.state in ('assigned', 'partially_available')
                )
                materials[key]['reserved_qty'] += reserved_qty
                
                # Process sub-components if any
                self._process_subcomponents(product, qty_needed, materials, [key])
        
        return materials
    
    def _process_subcomponents(self, product, parent_qty, materials, parent_ids):
        """Process sub-components recursively"""
        # Find BOM for this product
        bom = self.env['mrp.bom'].search([
            ('product_id', '=', product.id),
            ('type', '=', 'normal')
        ], limit=1)
        
        if not bom:
            return
            
        for line in bom.bom_line_ids:
            subproduct = line.product_id
            key = subproduct.id
            
            if key not in materials:
                materials[key] = {
                    'product': subproduct,
                    'qty': 0.0,
                    'reserved_qty': 0.0,
                    'uom': line.product_uom_id,
                    'is_subcomponent': True,
                    'parents': parent_ids.copy(),
                }
            else:
                # Add parent to existing entry
                for parent_id in parent_ids:
                    if parent_id not in materials[key]['parents']:
                        materials[key]['parents'].append(parent_id)
            
            # Calculate sub-component quantity
            sub_qty = (line.product_qty / bom.product_qty) * parent_qty
            materials[key]['qty'] += sub_qty
            
            # Recursively process sub-sub-components
            self._process_subcomponents(subproduct, sub_qty, materials, parent_ids + [key]) 