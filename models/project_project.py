from odoo import fields, models

class Project(models.Model):
    _inherit = 'project.project'

    business_sector = fields.Selection([
        ('manufacturing', 'Manufacturing'),
        ('textile', 'Textile'),
        ('beverage', 'Beverage'),
        ('construction', 'Construction'),
        ('it', 'Information Technology'),
        ('services', 'Services'),
        ('retail', 'Retail'),
        ('other', 'Other'),
    ], string='Business Sector', help="The business sector the client is in.")
