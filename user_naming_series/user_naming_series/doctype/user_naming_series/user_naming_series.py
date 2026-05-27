import frappe
from frappe.model.document import Document


class UserNamingSeries(Document):
	def validate(self):
		from user_naming_series.user_series import validate_settings_doc

		validate_settings_doc(self)
