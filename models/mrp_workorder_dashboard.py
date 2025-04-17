from odoo import models, fields, api
from odoo.tools.safe_eval import safe_eval

class MrpWorkorderDashboard(models.Model):
    _name = 'mrp.workorder.dashboard'
    _description = 'Work Order Dashboard'

    name = fields.Char('Name', required=True)
    workcenter_id = fields.Many2one('mrp.workcenter', string='Work Center', required=True)
    color = fields.Integer('Color Index')
    
    count_workorders = fields.Integer(compute='_compute_workorder_count', string='Work Orders')
    duration_expected = fields.Float(compute='_compute_workorder_count', string='Expected Duration')

    def _get_workorder_domain(self):
        return [
            '|', ('state', '=', 'progress'),
            '|', ('state', '=', 'ready'),
            '|', ('state', '=', 'waiting'),
            '&', ('state', '=', 'pending'),
            ('production_state', '!=', 'draft'),
            ('workcenter_id', '=', self.workcenter_id.id)
        ]

    @api.depends('workcenter_id')
    def _compute_workorder_count(self):
        for record in self:
            domain = record._get_workorder_domain()
            workorders = self.env['mrp.workorder'].search(domain)
            record.count_workorders = len(workorders)
            record.duration_expected = sum(workorders.mapped('duration_expected'))

    def get_workorder_action(self):
        self.ensure_one()
        action = self.env.ref('mrp.action_mrp_workorder_production').read()[0]
        action.update({
            'name': f'Work Orders - {self.workcenter_id.name}',
            'domain': self._get_workorder_domain(),
            'context': {'group_by': 'state'}
        })
        return action

    @api.model
    def get_workorder_graph_data(self):
        WorkOrder = self.env['mrp.workorder']
        domain = [
            '|', ('state', '=', 'progress'),
            '|', ('state', '=', 'ready'),
            '|', ('state', '=', 'waiting'),
            '&', ('state', '=', 'pending'),
            ('production_state', '!=', 'draft')
        ]
        
        result = WorkOrder.read_group(
            domain=domain,
            fields=['workcenter_id', 'duration_expected'],
            groupby=['workcenter_id']
        )
        
        return {
            'workcenters': [r['workcenter_id'][1] for r in result if r['workcenter_id']],
            'count': [r['__count'] for r in result if r['workcenter_id']],
            'duration': [r['duration_expected'] for r in result if r['workcenter_id']]
        } 