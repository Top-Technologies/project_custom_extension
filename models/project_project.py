from odoo import fields, models

class ProjectBusinessSector(models.Model):
    _name = 'project.business.sector'
    _description = 'Project Business Sector'

    name = fields.Char(string='Name', required=True, translate=True)


class Project(models.Model):
    _inherit = 'project.project'

    business_sector_ids = fields.Many2many(
        'project.business.sector',
        string='Business Sectors',
        help="The business sectors the client is in."
    )
