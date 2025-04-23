import logging
from odoo import models, api, _
from odoo.tools import float_round

_logger = logging.getLogger(__name__)

class MrpBomReport(models.AbstractModel):
    _name = 'report.need_mrp_dashboard.report_mrp_bom_materials'
    _description = 'BOM Materials Report with Multi-Level & MTO Support'

    def _process_component_recursive(self, product, required_qty, uom, current_mo, materials_dict, processed_mo_ids, parent_key=None, level=0, is_top_level_of_context_mo=True, max_level=10):
        """
        Recursively processes a component and its sub-components,
        handling MTO components by processing their triggered Sub-MOs.

        :param product: product.product recordset for the component
        :param required_qty: float quantity required for this component at this level
        :param uom: uom.uom recordset for the required_qty
        :param current_mo: mrp.production recordset - the MO whose requirements we are currently processing
        :param materials_dict: dict - the main dictionary aggregating all materials
        :param processed_mo_ids: set - IDs of MOs already processed in this report run to prevent loops
        :param parent_key: str - product ID of the parent component
        :param level: int - current recursion depth
        :param is_top_level_of_context_mo: bool - True if this product is a direct raw material of current_mo
        :param max_level: int - maximum recursion depth
        """
        if level > max_level:
            _logger.warning(f"Reached max recursion level ({max_level}) for product {product.name} in MO {current_mo.name}. Skipping further BOM explosion.")
            return

        comp_key = str(product.id)
        _logger.debug(f"{'  ' * level}Processing Level {level} (MO: {current_mo.name}): Product {product.name}, Required Qty: {required_qty} {uom.name}, Parent: {parent_key}, Is Top Level: {is_top_level_of_context_mo}")

        # --- Find the specific stock move for this product as a raw material of current_mo ---
        current_move = None
        if is_top_level_of_context_mo:
            current_move = self.env['stock.move'].search([
                ('product_id', '=', product.id),
                ('raw_material_production_id', '=', current_mo.id),
                ('state', 'not in', ['cancel', 'draft'])
            ], limit=1)
            if not current_move:
                 _logger.debug(f"{'  ' * level}No direct stock move found for {product.name} in MO {current_mo.name}")

        # --- Aggregate Quantities and Handle Reservation ---
        if comp_key not in materials_dict:
            materials_dict[comp_key] = {
                'product': product,
                'uom': uom,
                'qty': required_qty,
                'reserved_qty': 0.0,
                'level': level,
                'parents': set([parent_key]) if parent_key else set(),
                'required_by_mo': {current_mo.id: {'req': required_qty, 'res': 0.0}},
                'is_subcomponent': level > 0
            }
        else:
            materials_dict[comp_key]['qty'] += required_qty
            materials_dict[comp_key]['level'] = min(materials_dict[comp_key]['level'], level)
            if parent_key:
                materials_dict[comp_key]['parents'].add(parent_key)

        # --- Store MO-specific requirement and reservation data ---
        mo_id_key = current_mo.id
        if mo_id_key not in materials_dict[comp_key]['required_by_mo']:
             materials_dict[comp_key]['required_by_mo'][mo_id_key] = {'req': 0.0, 'res': 0.0, 'state': 'N/A'}

        materials_dict[comp_key]['required_by_mo'][mo_id_key]['req'] += required_qty

        current_reservation = 0.0
        current_move_state = 'N/A'
        if current_move:
             current_move_state = current_move.state
             if current_move_state == 'assigned':
                 current_reservation = current_move.product_uom_qty
             elif current_move_state == 'partially_available':
                 current_reservation = sum(line.quantity for line in current_move.move_line_ids)
             materials_dict[comp_key]['required_by_mo'][mo_id_key]['res'] += current_reservation
             materials_dict[comp_key]['required_by_mo'][mo_id_key]['state'] = current_move_state
             _logger.debug(f"{'  ' * level}  Reservation Calc (MO: {current_mo.name}): Product {product.name}, Move State: {current_move_state}, Reserved: {current_reservation}")

        materials_dict[comp_key]['reserved_qty'] = sum(mo_data['res'] for mo_data in materials_dict[comp_key]['required_by_mo'].values())

        # --- Check for MTO / Sub-MO (Using Origin Field Primarily) ---
        sub_mo_found = None
        _logger.debug(f"DEBUG: Before Sub-MO check for {product.display_name} (L{level})")
        if is_top_level_of_context_mo:
             _logger.debug(f"DEBUG: INSIDE Sub-MO check for {product.display_name} (L{level})")
             _logger.debug(f"{'  ' * level}  Checking for Sub-MO for MTO component: {product.name} (ID: {product.id}) requested by MO: {current_mo.name}")
             # --- Primary Method: Search using Origin --- 
             # Origin field usually contains the name/reference of the MO that triggered this MTO
             search_origin = current_mo.name
             if search_origin:
                  _logger.debug(f"{'  ' * level}    Searching Sub-MO via Origin: '{search_origin}', Product ID: {product.id}")
                  potential_sub_mos = self.env['mrp.production'].search([
                       ('origin', '=', search_origin),
                       ('product_id', '=', product.id),
                       ('id', '!=', current_mo.id), # Exclude self if somehow origin matches name
                       ('state', 'not in', ['cancel', 'done'])
                  ])
                  _logger.debug(f"{'  ' * level}    Found {len(potential_sub_mos)} potential Sub-MO(s) via Origin: {[mo.name for mo in potential_sub_mos]}")
                  for sub_mo in potential_sub_mos:
                       if sub_mo.id not in processed_mo_ids:
                            sub_mo_found = sub_mo
                            _logger.debug(f"{'  ' * level}    Selected potential Sub-MO via Origin: {sub_mo_found.name} (ID: {sub_mo_found.id})")
                            break
                       else:
                            _logger.debug(f"{'  ' * level}    Potential Sub-MO {sub_mo.name} (Origin) already processed. Skipping.")
             else:
                  _logger.debug(f"{'  ' * level}    Origin field is empty for MO {current_mo.name}, cannot search by Origin.")

             # --- Fallback: Search using Procurement Group (If Origin search failed) --- 
             if not sub_mo_found and current_move and current_move.group_id:
                  search_group_id = current_move.group_id.id
                  _logger.debug(f"{'  ' * level}    Searching Sub-MO via Group ID: {search_group_id}, Product ID: {product.id}, excluding MO ID: {current_mo.id}")
                  potential_sub_mos = self.env['mrp.production'].search([
                       ('procurement_group_id', '=', search_group_id),
                       ('product_id', '=', product.id),
                       ('id', '!=', current_mo.id),
                       ('state', 'not in', ['cancel', 'done'])
                  ])
                  _logger.debug(f"{'  ' * level}    Found {len(potential_sub_mos)} potential Sub-MO(s) via Group ID: {[mo.name for mo in potential_sub_mos]}")
                  for sub_mo in potential_sub_mos:
                       if sub_mo.id not in processed_mo_ids:
                            sub_mo_found = sub_mo
                            _logger.debug(f"{'  ' * level}    Selected potential Sub-MO via Group ID: {sub_mo_found.name} (ID: {sub_mo_found.id})")
                            break
                       else:
                            _logger.debug(f"{'  ' * level}    Potential Sub-MO {sub_mo.name} (Group ID) already processed. Skipping.")
             elif not current_move or not current_move.group_id:
                 _logger.debug(f"{'  ' * level}    Skipping Group ID search: No current_move or no Group ID on move {current_move.id if current_move else 'N/A'}.")

             # --- Fallback: Check destination moves (If other methods failed) ---
             if not sub_mo_found and current_move:
                 _logger.debug(f"{'  ' * level}    Searching Sub-MO via Dest Moves of Move ID: {current_move.id} (Dest IDs: {[m.id for m in current_move.move_dest_ids]})")
                 for dest_move in current_move.move_dest_ids:
                      _logger.debug(f"{'  ' * level}      Checking Dest Move ID: {dest_move.id}, Production ID: {dest_move.production_id.id if dest_move.production_id else 'None'}")
                      if dest_move.production_id and dest_move.production_id != current_mo:
                           if dest_move.production_id.id not in processed_mo_ids:
                                sub_mo_found = dest_move.production_id
                                _logger.debug(f"{'  ' * level}    Selected potential Sub-MO via Dest Move ID {dest_move.id}: {sub_mo_found.name} (ID: {sub_mo_found.id})")
                                break
                           else:
                                _logger.debug(f"{'  ' * level}    Potential Sub-MO {dest_move.production_id.name} (Dest Move) already processed. Skipping.")
                      else:
                            _logger.debug(f"{'  ' * level}      Dest Move {dest_move.id} has no Production ID or matches current MO.")
                 if not sub_mo_found:
                      _logger.debug(f"{'  ' * level}    No suitable Sub-MO found via Dest Moves.")
        
        # --- Process Sub-MO if found --- 
        if sub_mo_found:
            _logger.info(f"{'  ' * (level + 1)}>>> Switching context to Sub-MO {sub_mo_found.name} for MTO component {product.name}")
            processed_mo_ids.add(sub_mo_found.id)

            for sub_mo_move in sub_mo_found.move_raw_ids.filtered(lambda m: m.state not in ['cancel']):
                 # Calculate proportional qty - Needs careful review if this ratio is always correct
                 if current_move and current_move.product_uom_qty:
                      ratio = required_qty / current_move.product_uom_qty 
                 else:
                      # If no move or zero qty, can we reliably determine ratio? Fallback to 1?
                      ratio = 1.0 
                      _logger.warning(f"Could not determine ratio for Sub-MO {sub_mo_found.name} raw material {sub_mo_move.product_id.name}. Defaulting to 1.0.")
                 sub_mo_raw_material_qty = sub_mo_move.product_uom_qty * ratio

                 self._process_component_recursive(
                     sub_mo_move.product_id,
                     sub_mo_raw_material_qty,
                     sub_mo_move.product_uom,
                     sub_mo_found, # Context MO is now the Sub-MO
                     materials_dict,
                     processed_mo_ids,
                     parent_key=comp_key,
                     level=level + 1,
                     is_top_level_of_context_mo=True, # These are top level for the Sub-MO
                     max_level=max_level
                 )
            return # Stop processing current MTO component's BOM

        # --- If not MTO or no Sub-MO found/processed, proceed with normal BOM explosion ---
        # (Keep the BOM explosion logic as before)
        bom_dict = self.env['mrp.bom']._bom_find(products=product, company_id=current_mo.company_id.id, bom_type='normal')
        bom = bom_dict.get(product)

        if bom:
            _logger.debug(f"{'  ' * (level+1)}Found BOM: {bom.display_name} for {product.name} (within MO: {current_mo.name})")
            component_uom_at_this_level = uom
            if bom.product_uom_id != component_uom_at_this_level:
                 qty_in_bom_uom = component_uom_at_this_level._compute_quantity(required_qty, bom.product_uom_id)
            else:
                 qty_in_bom_uom = required_qty

            bqty = bom.product_qty
            bom_factor = float_round(qty_in_bom_uom / bqty, precision_rounding=bom.product_uom_id.rounding) if bqty else 0.0

            for line in bom.bom_line_ids:
                 sub_qty = line.product_qty * bom_factor
                 self._process_component_recursive(
                     line.product_id,
                     sub_qty,
                     line.product_uom_id,
                     current_mo,
                     materials_dict,
                     processed_mo_ids,
                     parent_key=comp_key,
                     level=level + 1,
                     is_top_level_of_context_mo=False,
                     max_level=max_level
                 )
        else:
             _logger.debug(f"{'  ' * (level+1)}No BOM found for {product.name} (within MO: {current_mo.name})")

    @api.model
    def _get_report_values(self, docids, data=None):
        _logger.info(f"Generating Advanced Multi-Level BOM Materials report for MO IDs: {docids}")
        initial_docs = self.env['mrp.production'].browse(docids)
        materials = {}
        processed_mo_ids = set(docids)

        for mo in initial_docs:
            _logger.info(f"Processing Top-Level MO: {mo.name} (ID: {mo.id})")
            for component_move in mo.move_raw_ids.filtered(lambda m: m.state not in ['cancel']):
                _logger.info(f"  Starting recursion for Top-Level Component: {component_move.product_id.name}, Demand: {component_move.product_uom_qty} {component_move.product_uom.name}")
                self._process_component_recursive(
                    component_move.product_id,
                    component_move.product_uom_qty,
                    component_move.product_uom,
                    mo,
                    materials,
                    processed_mo_ids,
                    parent_key=None,
                    level=0,
                    is_top_level_of_context_mo=True
                )

        for data_val in materials.values():
            data_val.pop('required_by_mo', None)
            data_val['parents'] = list(data_val.get('parents', set()))

        _logger.info(f"Final materials data for report: {materials}")

        # --- TEMPORARY TEST ---
        # if '503' in materials: # Assuming 503 is โครงเหล็ก
        #     materials['503']['reserved_qty'] = 99.99
        #     _logger.warning("TEMPORARY TEST: Hardcoded reserved_qty for product 503 to 99.99")
        # --- END TEMPORARY TEST ---

        return {
            'doc_ids': docids,
            'doc_model': 'mrp.production',
            'docs': initial_docs,
            'materials': materials,
        } 